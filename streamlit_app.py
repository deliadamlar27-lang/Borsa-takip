import os
import json
import time
import requests
import pandas as pd
import streamlit as st
import yfinance as yf
from typing import List, Dict, Optional

# =========================
# Konfig & Sağlayıcı Seçimi
# =========================

# İsteğe bağlı API anahtarları (yoksa sadece Yahoo+yfinance kullanır)
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "")

# Hangi sağlayıcılar aktif?
USE_YAHOO = True  # anahtarsız, her zaman açık
USE_FINNHUB = bool(FINNHUB_API_KEY)
USE_TWELVEDATA = bool(TWELVEDATA_API_KEY)

# =========================
# Yardımcı: Güvenli Metin
# =========================
def safe_str(x):
    if x is None:
        return ""
    return str(x)

# =========================
# Sembol Arama Sağlayıcıları
# =========================

class BaseSearchProvider:
    name: str = "base"
    def search(self, query: str) -> List[Dict]:
        return []

class YahooSearchProvider(BaseSearchProvider):
    """Yahoo Finance arama (anahtarsız). Küresel borsaları döndürür."""
    name = "yahoo"
    URL = "https://query2.finance.yahoo.com/v1/finance/search"

    def search(self, query: str) -> List[Dict]:
        params = {"q": query, "lang": "en-US", "region": "US"}
        r = requests.get(self.URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        items = data.get("quotes", []) or []
        results = []
        for it in items:
            # Ör: symbol="THYAO.IS", shortname="Turk Hava Yollari...", exchDisp="Istanbul"
            sym = safe_str(it.get("symbol"))
            shortname = safe_str(it.get("shortname") or it.get("longname") or it.get("name"))
            exch = safe_str(it.get("exchDisp"))
            qtype = safe_str(it.get("quoteType"))
            results.append({
                "provider": self.name,
                "symbol": sym,
                "displayName": shortname,
                "exchangeDisp": exch,
                "quoteType": qtype,
                "country": "",   # Yahoo aramada yok; gerekirse ek sağlayıcıdan zenginleşir
                "currency": "",  # fiyat tarafında dolduracağız
            })
        return results

class FinnhubSearchProvider(BaseSearchProvider):
    """Finnhub sembol arama (anahtarlı)."""
    name = "finnhub"
    URL = "https://finnhub.io/api/v1/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str) -> List[Dict]:
        if not self.api_key:
            return []
        params = {"q": query, "token": self.api_key}
        r = requests.get(self.URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        items = data.get("result", []) or []
        results = []
        for it in items:
            # Ör: symbol="AAPL", description="Apple Inc", type="Common Stock", displaySymbol
            sym = safe_str(it.get("symbol") or it.get("displaySymbol"))
            desc = safe_str(it.get("description"))
            results.append({
                "provider": self.name,
                "symbol": sym,
                "displayName": desc,
                "exchangeDisp": "",  # bu endpointte yok; istenirse /stock/exchange ile genişletebilirsin
                "quoteType": "",
                "country": "",
                "currency": "",
            })
        return results

class TwelveDataSearchProvider(BaseSearchProvider):
    """Twelve Data sembol arama (anahtarlı)."""
    name = "twelvedata"
    URL = "https://api.twelvedata.com/symbol_search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str) -> List[Dict]:
        if not self.api_key:
            return []
        params = {"symbol": query, "outputsize": 20, "apikey": self.api_key}
        r = requests.get(self.URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        items = data.get("data", []) or []
        results = []
        for it in items:
            # Ör: symbol="THYAO", exchange="BIST", instrument_name="Turk Hava Yollari A.O."
            sym = safe_str(it.get("symbol"))
            name = safe_str(it.get("instrument_name"))
            exch = safe_str(it.get("exchange"))
            country = safe_str(it.get("country"))
            currency = safe_str(it.get("currency"))
            # Not: TwelveData’da BIST formatı genelde "THYAO:BIST" şeklinde istekte kullanılır.
            results.append({
                "provider": self.name,
                "symbol": sym,
                "displayName": name,
                "exchangeDisp": exch,
                "quoteType": "",
                "country": country,
                "currency": currency,
            })
        return results

# Aktif sağlayıcıları sırala: Yahoo her zaman; diğerleri varsa eklenecek
SEARCH_PROVIDERS: List[BaseSearchProvider] = [YahooSearchProvider()]
if USE_FINNHUB:
    SEARCH_PROVIDERS.append(FinnhubSearchProvider(FINNHUB_API_KEY))
if USE_TWELVEDATA:
    SEARCH_PROVIDERS.append(TwelveDataSearchProvider(TWELVEDATA_API_KEY))

# =========================
# Fiyat & Tarihsel Veri
# =========================

def get_realtime_overview_yfinance(symbol: str) -> Dict:
    """
    yfinance ile son fiyat, değişim ve para birimi bilgisi.
    Mümkünse fast_info; yoksa fallback olarak son kapanış.
    """
    tk = yf.Ticker(symbol)
    out = {"last": None, "change": None, "change_pct": None, "currency": "", "exchange": ""}

    # exchange/currency denemeleri
    try:
        fi = tk.fast_info  # bazı alanlar: last_price, currency, exchange
        out["currency"] = safe_str(getattr(fi, "currency", "") or fi.get("currency", ""))
        out["exchange"] = safe_str(getattr(fi, "exchange", "") or fi.get("exchange", ""))
        last = getattr(fi, "last_price", None) or fi.get("last_price", None)
        if last is not None:
            out["last"] = float(last)
    except Exception:
        pass

    # Son fiyat yoksa history ile doldur
    if out["last"] is None:
        try:
            h = tk.history(period="5d", interval="1d", auto_adjust=False)
            if not h.empty:
                out["last"] = float(h["Close"].iloc[-1])
                prev = float(h["Close"].iloc[-2]) if len(h) > 1 else None
                if prev is not None:
                    out["change"] = out["last"] - prev
                    out["change_pct"] = (out["change"] / prev) * 100 if prev else None
        except Exception:
            pass

    # Değişimi hesapla (fast_info ile)
    if out["change"] is None:
        try:
            prev_close = getattr(fi, "previous_close", None) if 'fi' in locals() else None
            if prev_close is None and 'tk' in locals():
                info = tk.history(period="2d", interval="1d")
                if len(info) >= 2:
                    prev_close = float(info["Close"].iloc[-2])
            if prev_close and out["last"]:
                out["change"] = out["last"] - float(prev_close)
                out["change_pct"] = (out["change"] / float(prev_close)) * 100
        except Exception:
            pass

    return out

def get_monthly_history(symbol: str, period_key: str = "1y") -> pd.DataFrame:
    """
    symbol için aylık veri (OHLC) döndürür.
    period_key: "1y" | "3y" | "5y" | "max"
    """
    period_map = {"1y": "1y", "3y": "3y", "5y": "5y", "max": "max"}
    per = period_map.get(period_key, "1y")
    # yfinance aylık için interval="1mo"
    df = yf.download(symbol, period=per, interval="1mo", auto_adjust=False, progress=False)
    # Bazı semboller için boş dönebilir
    return df

# =========================
# UI
# =========================

st.set_page_config(page_title="Küresel Sembol Arama (Aylık Grafik)", page_icon="🌍", layout="wide")
st.title("🌍 Küresel Sembol Arama — Aylık Görünüm")

with st.sidebar:
    st.markdown("**Arama**")
    query = st.text_input("Şirket adı veya sembol yazın (örn: ASELSAN, THYAO, Apple, AAPL, BMW):", value="")
    st.caption("Not: CSV yok; sonuçlar canlı aranır. Dünya borsaları (BIST dahil) desteklenir.")

tab_results, tab_view = st.tabs(["🔎 Sonuçlar", "📈 Görünüm"])

# Takip listesi opsiyonel (varsayılan: boş)
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

def add_to_watchlist(sym):
    if sym not in st.session_state.watchlist:
        st.session_state.watchlist.append(sym)

with tab_results:
    if query.strip():
        all_hits: List[Dict] = []
        errors = []
        for prov in SEARCH_PROVIDERS:
            try:
                hits = prov.search(query.strip())
                all_hits.extend(hits)
            except Exception as e:
                errors.append(f"{prov.name}: {e}")
                continue

        # Normalizasyon & grupla (Exchange'e göre)
        df = pd.DataFrame(all_hits)
        if not df.empty:
            # Aynı sembol birden çok sağlayıcıdan gelebilir: benzersiz liste
            df = df.drop_duplicates(subset=["symbol", "provider", "displayName", "exchangeDisp"])
            # Kullanıcıya okunur liste
            st.success(f"{len(df)} sonuç bulundu.")
            # Borsa gruplaması
            for exch, g in df.groupby(df["exchangeDisp"].fillna("").replace("", "Other / Unknown")):
                with st.expander(f"**{exch}** — {len(g)} sonuç"):
                    for _, row in g.iterrows():
                        c1, c2, c3 = st.columns([6,2,2])
                        with c1:
                            st.write(f"**{row['symbol']}** — {row['displayName']}")
                            meta = []
                            if safe_str(row.get("provider")):
                                meta.append(f"sağlayıcı: {row['provider']}")
                            if safe_str(row.get("country")):
                                meta.append(f"ülke: {row['country']}")
                            st.caption(" | ".join(meta) if meta else " ")
                        with c2:
                            if st.button("Görüntüle", key=f"view_{row['symbol']}"):
                                st.session_state["current_symbol"] = row["symbol"]
                                st.switch_page("app.py") if hasattr(st, "switch_page") else None
                        with c3:
                            if st.button("Takibe Al", key=f"add_{row['symbol']}"):
                                add_to_watchlist(row["symbol"])
        else:
            st.warning("Sonuç bulunamadı. Farklı bir ifade deneyin.")
        if errors:
            with st.expander("Uyarılar / Sağlayıcı Hataları"):
                for e in errors:
                    st.code(e)
    else:
        st.info("Aramak için sol üstte metin girin.")

with tab_view:
    st.subheader("Seçili Sembol")
    symbol = st.text_input("Sembol (Yahoo biçimi; örn: THYAO.IS, AAPL, BMW.DE)", value=st.session_state.get("current_symbol", ""))
    cols = st.columns([2,2,2,2,2])
    with cols[0]:
        period_key = st.radio("Dönem (Aylık)", options=["1y","3y","5y","max"], horizontal=True, index=0)

    if st.button("Verileri Getir", type="primary"):
        if not symbol.strip():
            st.warning("Önce bir sembol girin ya da sonuçlar sekmesinden 'Görüntüle'ye basın.")
        else:
            with st.spinner("Veriler getiriliyor..."):
                # Özet
                overview = get_realtime_overview_yfinance(symbol.strip())
                # Tarihsel (aylık)
                hist = get_monthly_history(symbol.strip(), period_key=period_key)

            # Özet kutuları
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Sembol", symbol)
            with c2:
                last_text = f"{overview['last']:.4f}" if overview["last"] is not None else "—"
                st.metric("Son Fiyat", last_text)
            with c3:
                ch = overview.get("change")
                ch_pct = overview.get("change_pct")
                ch_text = "—"
                if ch is not None and ch_pct is not None:
                    ch_text = f"{ch:+.4f} ({ch_pct:+.2f}%)"
                st.metric("Gün İçi Değişim", ch_text)
            with c4:
                cur = overview.get("currency") or "—"
                ex = overview.get("exchange") or "—"
                st.metric("Para Birimi / Borsa", f"{cur} / {ex}")

            # Aylık grafik
            st.subheader("Aylık Fiyat (Close)")
            if hist is not None and not hist.empty:
                # Bazı sembollerde sütun adları çoklu olabilir: ('Close', 'AAPL') gibi; düzleştir
                if isinstance(hist.columns, pd.MultiIndex):
                    hist.columns = ["_".join([c for c in col if c]) for col in hist.columns.values]
                close_col = None
                for cand in ["Close", "Adj Close", "Close_AAPL"]:  # worst-case fallback denemesi
                    if cand in hist.columns:
                        close_col = cand
                        break
                if close_col is None:
                    # otomatik seç
                    close_col = hist.columns[-1]

                # Sadece aylık kapanış serisi
                s = hist[close_col].dropna()
                st.line_chart(s)

            else:
                st.warning("Bu dönem için aylık veri bulunamadı.")

    # Watchlist'i göster (opsiyonel)
    if st.session_state.watchlist:
        st.markdown("---")
        st.subheader("Takip Listem (opsiyonel)")
        st.write(", ".join(st.session_state.watchlist))
