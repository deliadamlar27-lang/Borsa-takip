import requests
import pandas as pd
import streamlit as st
import yfinance as yf
import time

# -------------------
# Arama Sağlayıcı
# -------------------
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

SEARCH = YahooSearchProvider()

# -------------------
# Fiyat Bilgisi
# -------------------
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

# -------------------
# Streamlit UI
# -------------------
st.set_page_config(page_title="Küresel Sembol Arama", page_icon="🌍", layout="wide")
st.title("🌍 Küresel Sembol Arama — Aylık Görünüm")

with st.sidebar:
    query = st.text_input("Şirket adı veya sembol yazın (örn: ASELSAN, ASELS.IS, AAPL):")

tab_results, tab_view = st.tabs(["🔎 Sonuçlar", "📈 Görünüm"])

if "current_symbol" not in st.session_state:
    st.session_state.current_symbol = ""

# -------------------
# TAB: Sonuçlar
# -------------------
with tab_results:
    if st.button("Ara", type="primary", use_container_width=True):
        if not query.strip():
            st.warning("Bir şey yazın.")
        else:
            # Eğer doğrudan sembol gibi görünüyorsa (örn ASELS.IS, AAPL)
            if "." in query or query.isupper():
                st.session_state.current_symbol = query.strip()
                st.success(f"{query.strip()} seçildi. Görünüm sekmesine geçin.")
            else:
                with st.spinner("Aranıyor..."):
                    results = SEARCH.search(query)
                if results:
                    for r in results:
                        c1, c2 = st.columns([6,2])
                        with c1:
                            st.write(f"**{r['symbol']}** — {r['name']} ({r['exchange']})")
                        with c2:
                            if st.button("Seç", key=r['symbol']):
                                st.session_state.current_symbol = r['symbol']
                                st.success(f"{r['symbol']} seçildi. Görünüm sekmesine geçin.")
                else:
                    st.warning("Sonuç bulunamadı.")

    else:
        st.info("Aramak için 'Ara'ya basın.")

# -------------------
# TAB: Görünüm
# -------------------
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
