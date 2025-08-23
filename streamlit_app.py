import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from datetime import date, timedelta

# --- Ayarlar ve API Key ---
NEWSAPI_KEY = st.secrets.get("newsapi_key", "aa6e3b9181e8404bbad288b01e73e19f")

# --- Yardımcı Fonksiyonlar ---
def parse_tickers(raw: str):
    parts = [p.strip().upper() for p in raw.replace("\n", ",").replace(";", ",").split(",")]
    return [p for p in parts if p]

@st.cache_data(ttl=3600)
def fetch_data(ticker, start_dt, end_dt, interval):
    df = yf.download(ticker, start=start_dt, end=end_dt + timedelta(days=1), interval=interval, progress=False)
    if not df.empty:
        df = df.rename(columns={
            "Open": "Açılış", "High": "Yüksek", "Low": "Düşük",
            "Close": "Kapanış", "Adj Close": "Düzeltilmiş Kapanış", "Volume": "Hacim"
        })
        df.index.name = "Tarih"
    return df

def build_stats(df):
    out = pd.DataFrame()
    if df.empty or "Kapanış" not in df:
        return out
    prices = df["Kapanış"].dropna()
    if prices.empty:
        return out
    returns = prices.pct_change().dropna()
    summary = {
        "Gözlem": len(prices),
        "Başlangıç": float(prices.iloc[0]),
        "Bitiş": float(prices.iloc[-1]),
        "Toplam Getiri %": (prices.iloc[-1] / prices.iloc[0] - 1.0) * 100.0,
        "Günlük Ortalama %": returns.mean() * 100.0,
        "Günlük Std %": returns.std() * 100.0,
        "Yıllık Vol %": (returns.std() * (252 ** 0.5)) * 100.0 if len(returns) > 1 else None,
        "Maks. Düşüş %": ((prices / prices.cummax()).min() - 1.0) * 100.0,
    }
    out = pd.DataFrame([summary])
    return out.round(3)

def get_news_newsapi(query, from_date, to_date, language="tr", page_size=5):
    if not NEWSAPI_KEY:
        return []
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "from": from_date,
        "to": to_date,
        "language": language,
        "sortBy": "publishedAt",
        "pageSize": page_size,
        "apiKey": NEWSAPI_KEY,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        articles = resp.json().get("articles", [])
        news = []
        for item in articles:
            news.append({
                "title": item.get("title"),
                "desc": item.get("description"),
                "url": item.get("url"),
                "date": item.get("publishedAt"),
                "source": item.get("source", {}).get("name", ""),
            })
        return news
    except Exception:
        return []

# --- Streamlit Arayüzü ---
st.set_page_config(page_title="Global Borsa Takip", page_icon="📈", layout="wide")
st.title("📈 Global Borsa Takip Uygulaması")
st.caption("Yahoo Finance fiyat verileri ve NewsAPI ile haberler.")

with st.sidebar:
    st.header("Sembol ve Tarih")
    tickers_str = st.text_area("İzlenecek Semboller", value="THYAO.IS, ASELS.IS\nAAPL, MSFT", height=80)
    start_dt = st.date_input("Başlangıç", value=date.today() - timedelta(days=180))
    end_dt = st.date_input("Bitiş", value=date.today())
    interval = st.selectbox("Zaman aralığı", ["1d", "1wk", "1mo"], index=0)
    run = st.button("Verileri Getir", type="primary")

tickers = parse_tickers(tickers_str)
if not tickers:
    st.info("Lütfen en az bir sembol girin.")
    st.stop()

if run:
    st.subheader("Sonuçlar")
    for t in tickers[:3]:  # ilk 3 sembol için
        st.markdown(f"### {t}")
        try:
            df = fetch_data(t, start_dt, end_dt, interval)
            if df.empty:
                st.warning("Veri bulunamadı veya sembol geçersiz olabilir.")
                continue
            st.dataframe(df)
            stats = build_stats(df)
            if not stats.empty:
                st.markdown("**Özet İstatistikler**")
                st.dataframe(stats)
        except Exception as e:
            st.error(f"Veri çekme hatası: {e}")

        # Haberler
        st.markdown("**İlgili Haberler**")
        try:
            news = get_news_newsapi(t, str(start_dt), str(end_dt))
            if news:
                for n in news:
                    st.write(f"[{n['title']}]({n['url']}) ({n['source']} - {n['date']})")
                    st.caption(n['desc'])
            else:
                st.info("Haber bulunamadı veya API anahtarı girilmedi.")
        except Exception as e:
            st.error(f"Haber çekme hatası: {e}")

st.caption("Veriler Yahoo Finance ve NewsAPI üzerinden sağlanır. Yatırım tavsiyesi değildir.")
