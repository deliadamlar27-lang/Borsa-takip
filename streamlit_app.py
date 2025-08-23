import os
import requests
import pandas as pd
import streamlit as st
import yfinance as yf
import time

# =========================
# Yardımcı
# =========================
def safe_str(x):
    return "" if x is None else str(x)

# =========================
# Yahoo Arama Sağlayıcı
# =========================
class YahooSearchProvider:
    name = "yahoo"
    URL = "https://query2.finance.yahoo.com/v1/finance/search"

    def search(self, query: str):
        params = {"q": query, "lang": "en-US", "region": "US"}
        for attempt in range(2):
            r = requests.get(self.URL, params=params, timeout=10)
            if r.status_code == 429 and attempt == 0:
                time.sleep(1.5)
                continue
            r.raise_for_status()
            break
        data = r.json()
        items = data.get("quotes", []) or []
        results = []
        for it in items:
            sym = safe_str(it.get("symbol"))
            shortname = safe_str(it.get("shortname") or it.get("longname") or it.get("name"))
            exch = safe_str(it.get("exchDisp"))
            results.append({
                "provider": self.name,
                "symbol": sym,
                "displayName": shortname,
                "exchangeDisp": exch,
            })
        return results

SEARCH_PROVIDERS = [YahooSearchProvider()]

# =========================
# Cache’li Arama
# =========================
@st.cache_data(ttl=3600, show_spinner=False)
def run_search(query: str) -> pd.DataFrame:
    all_hits = []
    for prov in SEARCH_PROVIDERS:
        try:
            all_hits += prov.search(query.strip())
        except Exception as e:
            all_hits += [{"provider": prov.name, "error": str(e)}]
    return pd.DataFrame(all_hits)

# =========================
# Fiyat & Tarihsel Veri
# =========================
def get_realtime_overview(symbol: str):
    tk = yf.Ticker(symbol)
    out = {"last": None, "change": None, "change_pct": None, "currency": "", "exchange": ""}

    try:
        fi = tk.fast_info
        out["currency"] = safe_str(getattr(fi, "currency", "") or fi.get("currency", ""))
        out["exchange"] = safe_str(getattr(fi, "exchange", "") or fi.get("exchange", ""))
        last = getattr(fi, "last_price", None) or fi.get("last_price", None)
        if last is not None:
            out["last"] = float(last)
    except Exception:
        pass

    try:
        h = tk.history(period="5d", interval="1d", auto_adjust=False)
        if not h.empty:
            out["last"] = float(h["Close"].iloc[-1])
            prev = float(h["Close"].iloc[-2]) if len(h) > 1 else None
            if prev is not None:
                out["change"] = out["last"] - prev
                out["change_pct"] = (out["change"] / prev) * 100
    except Exception:
        pass

    return out

def get_monthly_history(symbol: str, period_key: str = "1y"):
    period_map = {"1y": "1y", "3y": "3y", "5y": "5y", "max": "max"}
    per = period_map.get(period_key, "1y")
    df = yf.download(symbol, period=per, interval="1mo", auto_adjust=False, progress=False)
    return df

# =========================
# Streamlit UI
# =========================
st.set_page_config(page_title="Küresel Sembol Arama", page_icon="🌍", layout="wide")
st.title("🌍 Küresel Sembol Arama — Aylık Görünüm")

with st.sidebar:
    st.markdown("**Arama**")
    query = st.text_input("Şirket adı veya sembol (örn: ASELSAN, THYAO, Apple, AAPL, BMW):")
    st.caption("Not: Sonuçlar canlı aranır (BIST dahil).")

tab_results, tab_view = st.tabs(["🔎 Sonuçlar", "📈 Görünüm"])

if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

def add_to_watchlist(sym):
    if sym not in st.session_state.watchlist:
        st.session_state.watchlist.append(sym)

# =========================
# TAB: Sonuçlar
# =========================
with tab_results:
    with tab_results:
    search_clicked = st.button("Ara", type="primary", use_container_width=True)

    # Eğer kullanıcı sembol formatında girdiyse (örn ASELS.IS, AAPL, BMW.DE)
    if search_clicked and query.strip():
        if "." in query.strip() or query.strip().isupper():
            # Direkt sembol gibi kabul et
            st.session_state["current_symbol"] = query.strip()
            st.success(f"{query.strip()} sembolü seçildi. Görünüm sekmesine geçin.")
        else:
            # Normal isim araması
            with st.spinner("Aranıyor..."):
                df = run_search(query)
            ...

    search_clicked = st.button("Ara", type="primary", use_container_width=True)

    if search_clicked:
        if not query.strip():
            st.warning("Bir arama terimi girin.")
        else:
            with st.spinner("Aranıyor..."):
                df = run_search(query)

            if not df.empty and "error" in df.columns:
                errs = df[df["error"].notna()]
                if not errs.empty:
                    with st.expander("Uyarılar / Sağlayıcı Hataları"):
                        for _, r in errs.iterrows():
                            st.code(f"{r.get('provider','')}: {r['error']}")
                df = df[df["error"].isna()]

            if not df.empty:
                df = df.drop_duplicates(subset=["symbol","provider","displayName","exchangeDisp"])
                st.success(f"{len(df)} sonuç bulundu.")
                for exch, g in df.groupby(df["exchangeDisp"].fillna("").replace("", "Other / Unknown")):
                    with st.expander(f"**{exch}** — {len(g)} sonuç"):
                        for _, row in g.iterrows():
                            c1, c2, c3 = st.columns([6,2,2])
                            with c1:
                                st.write(f"**{row['symbol']}** — {row['displayName']}")
                            with c2:
                                if st.button("Görüntüle", key=f"view_{row['symbol']}"):
                                    st.session_state["current_symbol"] = row["symbol"]
                            with c3:
                                if st.button("Takibe Al", key=f"add_{row['symbol']}"):
                                    add_to_watchlist(row["symbol"])
            else:
                st.warning("Sonuç bulunamadı. Farklı bir ifade deneyin.")
    else:
        st.info("Aramak için 'Ara' butonuna basın.")

# =========================
# TAB: Görünüm
# =========================
with tab_view:
    st.subheader("Seçili Sembol")
    symbol = st.text_input("Sembol (örn: THYAO.IS, AAPL, BMW.DE)", value=st.session_state.get("current_symbol", ""))

    cols = st.columns([2,2,2,2])
    with cols[0]:
        period_key = st.radio("Dönem (Aylık)", options=["1y","3y","5y","max"], horizontal=True, index=0)

    if st.button("Verileri Getir", type="primary"):
        if not symbol.strip():
            st.warning("Önce bir sembol seçin veya girin.")
        else:
            with st.spinner("Veriler getiriliyor..."):
                overview = get_realtime_overview(symbol.strip())
                hist = get_monthly_history(symbol.strip(), period_key=period_key)

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Sembol", symbol)
            with c2:
                st.metric("Son Fiyat", f"{overview['last']:.4f}" if overview["last"] else "—")
            with c3:
                if overview["change"] is not None:
                    st.metric("Değişim", f"{overview['change']:+.4f} ({overview['change_pct']:+.2f}%)")
                else:
                    st.metric("Değişim", "—")
            with c4:
                st.metric("Borsa", f"{overview['currency']} / {overview['exchange']}")

            st.subheader("Aylık Grafik")
            if hist is not None and not hist.empty:
                if isinstance(hist.columns, pd.MultiIndex):
                    hist.columns = ["_".join([c for c in col if c]) for col in hist.columns.values]
                close_col = "Close" if "Close" in hist.columns else hist.columns[-1]
                st.line_chart(hist[close_col].dropna())
            else:
                st.warning("Bu dönem için veri bulunamadı.")

    if st.session_state.watchlist:
        st.markdown("---")
        st.subheader("Takip Listem")
        st.write(", ".join(st.session_state.watchlist))
