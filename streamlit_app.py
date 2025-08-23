import streamlit as st
import yfinance as yf
import requests

FINNHUB_API_KEY = "d2kqkchr01qs23a3e2ug"

def search_symbols(query):
    url = f"https://finnhub.io/api/v1/search?q={query}&token={FINNHUB_API_KEY}"
    r = requests.get(url)
    if r.status_code == 200:
        return r.json().get("result", [])
    return []

st.sidebar.header("Arama")
company_query = st.sidebar.text_input("Şirket adı veya sembol yazın (örn: ASELSAN, APPLE, TESLA):")

selected_symbols = []

if st.sidebar.button("Ara"):
    if st.sidebar.button("Ara"):
    results = search_symbols(company_query)
    if results:
        st.subheader("Eşleşen Semboller")
        
        # Checkbox listesi
        selected_symbols = []
        for res in results:
            symbol = res.get("symbol")
            desc = res.get("description")
            if st.checkbox(f"{symbol} — {desc}"):
                selected_symbols.append(symbol)

        # Eğer seçim yapıldıysa verileri getir
        if selected_symbols:
            st.success(f"Seçilen semboller: {', '.join(selected_symbols)}")
            for sym in selected_symbols:
                try:
                    ticker = yf.Ticker(sym)
                    info = ticker.info
                    st.markdown(f"### {sym}")
                    st.write(f"**Fiyat:** {info.get('currentPrice', 'N/A')}")
                    st.write(f"**Para Birimi:** {info.get('currency', 'N/A')}")
                    st.write(f"**Borsa:** {info.get('exchange', 'N/A')}")
                    hist = ticker.history(period="6mo", interval="1d")
                    st.line_chart(hist["Close"])
                except Exception as e:
                    st.error(f"{sym} için veri alınamadı: {e}")
        else:
            st.info("Sembol seçmek için kutucukları işaretleyin.")
    else:
        st.warning("Sonuç bulunamadı.")

    results = search_symbols(company_query)
    if results:
        st.subheader("Eşleşen Semboller")
        for res in results:
            symbol = res.get("symbol")
            desc = res.get("description")
            if st.checkbox(f"{symbol} — {desc}"):
                selected_symbols.append(symbol)
    else:
        st.warning("Sonuç bulunamadı.")

# Seçilen semboller için veri göster
if selected_symbols:
    for sym in selected_symbols:
        try:
            ticker = yf.Ticker(sym)
            info = ticker.info
            st.markdown(f"### {sym}")
            st.write(f"**Fiyat:** {info.get('currentPrice', 'N/A')}")
            st.write(f"**Para Birimi:** {info.get('currency', 'N/A')}")
            st.write(f"**Borsa:** {info.get('exchange', 'N/A')}")
            hist = ticker.history(period="1y", interval="1mo")
            st.line_chart(hist["Close"])
        except Exception as e:
            st.error(f"{sym} için veri alınamadı: {e}")

import time
import requests
import pandas as pd
import streamlit as st
import yfinance as yf

# =========================
# API Keys
# =========================
FINNHUB_API_KEY = "d2kqkchr01qs23a3e2ug"  # senin verdiğin key

# =========================
# Search Providers
# =========================
class YahooSearchProvider:
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
            results.append({
                "symbol": it.get("symbol", ""),
                "name": it.get("shortname") or it.get("longname") or it.get("name", ""),
                "exchange": it.get("exchDisp", ""),
            })
        return results

class FinnhubSearchProvider:
    URL = "https://finnhub.io/api/v1/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str):
        if not self.api_key:
            return []
        params = {"q": query, "token": self.api_key}
        r = requests.get(self.URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        results = []
        for it in data.get("result", []):
            results.append({
                "symbol": it.get("symbol", ""),
                "name": it.get("description", ""),
                "exchange": it.get("type", ""),
            })
        return results

# Sağlayıcı listesi
SEARCH_PROVIDERS = [YahooSearchProvider()]
if FINNHUB_API_KEY:
    SEARCH_PROVIDERS.append(FinnhubSearchProvider(FINNHUB_API_KEY))

# =========================
# Fiyat ve Tarihsel Veri
# =========================
def get_overview(symbol: str):
    tk = yf.Ticker(symbol)
    out = {"last": None, "change": None, "change_pct": None, "currency": "", "exchange": ""}
    try:
        fi = tk.fast_info
        out["last"] = float(fi.get("last_price", None))
        out["currency"] = fi.get("currency", "")
        out["exchange"] = fi.get("exchange", "")
    except Exception:
        pass
    try:
        h = tk.history(period="5d", interval="1d")
        if not h.empty:
            out["last"] = float(h["Close"].iloc[-1])
            prev = float(h["Close"].iloc[-2]) if len(h) > 1 else None
            if prev:
                out["change"] = out["last"] - prev
                out["change_pct"] = (out["change"] / prev) * 100
    except Exception:
        pass
    return out

def get_monthly(symbol: str, period="1y"):
    df = yf.download(symbol, period=period, interval="1mo", auto_adjust=False, progress=False)
    return df

# =========================
# Streamlit UI
# =========================
st.set_page_config(page_title="Küresel Sembol Arama", page_icon="🌍", layout="wide")
st.title("🌍 Küresel Sembol Arama — Aylık Görünüm")

with st.sidebar:
    query = st.text_input("Şirket adı veya sembol yazın (örn: ASELSAN, ASELS.IS, AAPL):")

tab_results, tab_view = st.tabs(["🔎 Sonuçlar", "📈 Görünüm"])

if "current_symbol" not in st.session_state:
    st.session_state.current_symbol = ""

# =========================
# TAB: Sonuçlar
# =========================
with tab_results:
    if st.button("Ara", type="primary", use_container_width=True):
        if not query.strip():
            st.warning("Bir şey yazın.")
        else:
            # Doğrudan sembol gibi görünüyorsa
            if "." in query.strip() or query.strip().isupper():
                st.session_state.current_symbol = query.strip()
                st.success(f"{query.strip()} seçildi. Görünüm sekmesine geçin.")
            else:
                with st.spinner("Aranıyor..."):
                    results = []
                    for prov in SEARCH_PROVIDERS:
                        try:
                            r = prov.search(query)
                            if r:
                                results.extend(r)
                        except Exception as e:
                            st.write(f"{prov.__class__.__name__} hata: {e}")
                            continue

                if results:
                    df = pd.DataFrame(results).drop_duplicates(subset=["symbol"])
                    for _, row in df.iterrows():
                        c1, c2 = st.columns([6,2])
                        with c1:
                            st.write(f"**{row['symbol']}** — {row['name']} ({row['exchange']})")
                        with c2:
                            if st.button("Seç", key=row['symbol']):
                                st.session_state.current_symbol = row['symbol']
                                st.success(f"{row['symbol']} seçildi. Görünüm sekmesine geçin.")
                else:
                    st.warning("Sonuç bulunamadı.")
    else:
        st.info("Aramak için 'Ara'ya basın.")

# =========================
# TAB: Görünüm
# =========================
with tab_view:
    symbol = st.session_state.current_symbol
    if not symbol:
        st.info("Henüz sembol seçmediniz.")
    else:
        st.subheader(f"Sembol: {symbol}")
        period = st.radio("Dönem (Aylık)", ["1y","3y","5y","max"], horizontal=True)

        if st.button("Verileri Getir", type="primary"):
            with st.spinner("Veriler getiriliyor..."):
                ov = get_overview(symbol)
                hist = get_monthly(symbol, period)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Sembol", symbol)
            c2.metric("Son Fiyat", f"{ov['last']:.2f}" if ov['last'] else "—")
            if ov["change"] is not None:
                c3.metric("Değişim", f"{ov['change']:+.2f} ({ov['change_pct']:+.2f}%)")
            else:
                c3.metric("Değişim", "—")
            c4.metric("Borsa", f"{ov['currency']} / {ov['exchange']}")

            if hist is not None and not hist.empty:
                st.line_chart(hist["Close"].dropna())
            else:
                st.warning("Veri bulunamadı.")
