import io
from datetime import date, timedelta
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
import requests

# -----------------------------
# API Anahtarlarını ekleyin!
# -----------------------------
NEWSAPI_KEY = st.secrets.get("aa6e3b9181e8404bbad288b01e73e19f", "")  # streamlit secrets ile veya direkt olarak yazabilirsiniz
OPENAI_API_KEY = st.secrets.get("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", "")

# -----------------------------
# Haber Fonksiyonu (NewsAPI)
# -----------------------------
def get_news_newsapi(query: str, from_date: str, to_date: str, language="tr", page_size=5) -> List[Dict]:
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

# -----------------------------
# Yardımcı Fonksiyonlar
# -----------------------------
# ... (Diğer yardımcı fonksiyonlar aynı kalabilir.)

def chatgpt_summary(context: str, stats: Dict, news: List[Dict]):
    if not OPENAI_API_KEY:
        return "ChatGPT API anahtarı eklenmedi!"
    import openai
    openai.api_key = OPENAI_API_KEY
    prompt = (
        "Aşağıdaki şirketin finansal verileri ve haberleri verildi. "
        "Lütfen fiyat değişimi istatistiklerini ve haberlerle olası bağlantıları tartış: "
        f"\nİstatistikler: {stats}"
        f"\nHaberler: {[n['title']+': '+n['desc'] for n in news]}"
        f"\nKullanıcı notu: {context}"
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ChatGPT isteği başarısız: {e}"

# -----------------------------
# UI ve Akış
# -----------------------------
st.set_page_config(page_title="Global Borsa Takibi", page_icon="📈", layout="wide")
st.title("📈 Global Borsa Takip Uygulaması")
st.caption("Yahoo Finance verileri, haberler ve ChatGPT ile istatistik tartışma.")

# ... (Sidebar vs. kodlar aynı.)

# -----------------------------
# Veri Alma ve Görselleştirme
# -----------------------------
tickers = parse_tickers(tickers_str)
if not tickers:
    st.info("Lütfen en az bir sembol girin.")
    st.stop()

ok, msg = allowed_interval_and_range(interval, start_dt, end_dt)
if not ok:
    st.warning(msg)

if run:
    st.subheader("Sonuçlar")
    all_dfs: Dict[str, pd.DataFrame] = {}
    stats_list: List[pd.DataFrame] = []
    news_dict = {}

    for t in tickers[:3]:  # 3 sembole kadar haber çekilecek
        with st.container(border=True):
            st.markdown(f"### {t}")

            # 1. Fiyat ve istatistikler
            try:
                df = fetch_data(t, start_dt, end_dt, interval)
                if df.empty:
                    st.warning("Veri bulunamadı veya sembol geçersiz olabilir.")
                    continue
                all_dfs[t] = df

                # ... (Grafik ve tablo kodları aynı.)

                # İstatistikler
                st.markdown("**Özet İstatistikler**")
                sdf = build_stats(df)
                if not sdf.empty:
                    sdf.insert(0, "Sembol", t)
                    stats_list.append(sdf)
                    st.dataframe(sdf)
                else:
                    st.info("İstatistik üretmek için yeterli veri yok.")
            except Exception as e:
                st.error(f"{t} için hata: {e}")

            # 2. Haberler (NewsAPI ile)
            st.markdown("**İlgili Haberler**")
            try:
                news = get_news_newsapi(t, str(start_dt), str(end_dt))
                news_dict[t] = news
                if news:
                    for n in news:
                        st.write(f"[{n['title']}]({n['url']}) ({n['source']} - {n['date']})")
                        st.caption(n['desc'])
                else:
                    st.info("Haber bulunamadı veya API anahtarı girilmedi.")
            except Exception as e:
                st.error(f"Haberler çekilemedi: {e}")

            # 3. ChatGPT ile tartışma
            st.markdown("**ChatGPT ile Tartışma**")
            user_note = st.text_area(f"{t} için Chat'e not yaz (isteğe bağlı)", value="", key=f"note_{t}")
            if st.button(f"{t} için GPT ile analiz et", key=f"gpt_{t}"):
                summary = chatgpt_summary(user_note, sdf.to_dict() if not sdf.empty else {}, news)
                st.info(summary)

    # ... (Birleşik istatistikler ve Excel aktarma aynı.)

st.caption("Veriler Yahoo Finance ve NewsAPI üzerinden sağlanır ve gecikmeli olabilir. Yatırım kararları için tek kaynak olarak kullanmayın. ChatGPT ile tartışmalar öneridir, yatırım tavsiyesi değildir.")
