import streamlit as st
import yfinance as yf
import requests

# -------------------------------
# Finnhub API Key
FINNHUB_API_KEY = "d2kqkchr01qs23a3e2ug"

# -------------------------------
# Sembol arama fonksiyonu
def search_symbols(query):
    try:
        url = f"https://finnhub.io/api/v1/search?q={query}&token={FINNHUB_API_KEY}"
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", [])
    except Exception as e:
        st.error(f"Hata: {e}")
        return []

# -------------------------------
# Streamlit UI
st.set_page_config(page_title="📈 Küresel Sembol Arama", layout="wide")

st.title("🌍 Küresel Sembol Arama — Aylık Görünüm")

# Sol menü
st.sidebar.header("Arama")
company_query = st.sidebar.text_input(
    "Şirket adı veya sembol yazın (örm: ASELSAN, APPLE, TESLA):"
)

if st.sidebar.button("Ara"):
    results = search_symbols(company_query)
    if results:
        st.subheader("🔍 Eşleşen Semboller")
        selected_symbols = []
        for res in results:
            symbol = res.get("symbol")
            desc = res.get("description")
            if st.checkbox(f"{symbol} — {desc}"):
                selected_symbols.append(symbol)

        if selected_symbols:
            st.success(f"Seçilen semboller: {', '.join(selected_symbols)}")

            # Verileri getir ve göster
            for sym in selected_symbols:
                try:
                    ticker = yf.Ticker(sym)
                    info = ticker.info

                    st.markdown(f"### {sym}")
                    st.write(f"**Fiyat:** {info.get('currentPrice', 'N/A')}")
                    st.write(f"**Para Birimi:** {info.get('currency', 'N/A')}")
                    st.write(f"**Borsa:** {info.get('exchange', 'N/A')}")

                    # Grafik (6 ay)
                    hist = ticker.history(period="6mo", interval="1d")
                    if not hist.empty:
                        st.line_chart(hist["Close"])
                    else:
                        st.warning(f"{sym} için fiyat geçmişi bulunamadı.")

                except Exception as e:
                    st.error(f"{sym} için veri alınamadı: {e}")
        else:
            st.info("Sembol seçmek için kutucukları işaretleyin.")
    else:
        st.warning("Sonuç bulunamadı. Farklı bir ifade deneyin.")
