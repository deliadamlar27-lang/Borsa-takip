import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta

def parse_tickers(raw: str):
    parts = [p.strip().upper() for p in raw.replace("\n", ",").replace(";", ",").split(",")]
    return [p for p in parts if p]

@st.cache_data(ttl=3600)
def fetch_monthly_data(ticker, start_dt, end_dt):
    df = yf.download(ticker, start=start_dt, end=end_dt + timedelta(days=1), interval="1mo", progress=False)
    if not df.empty:
        df.index = pd.to_datetime(df.index)
        df = df.rename(columns={"Close": "Kapanış"})
        df = df[["Kapanış"]]
    return df

def calc_monthly_changes(df):
    if df.empty or len(df) < 2:
        return pd.DataFrame()
    # Sıralama ve resetleme
    df = df.sort_index()
    df["Ay"] = df.index.strftime("%Y-%m")
    df["Aylık Değişim (%)"] = df["Kapanış"].pct_change().multiply(100).round(2)
    # İlk satırı (NaN) atla, geri kalanı göster
    return df[["Ay", "Kapanış", "Aylık Değişim (%)"]].dropna()

st.set_page_config(page_title="Aylık Getiri", page_icon="📈", layout="wide")
st.title("📈 Hisse Senedi Aylık Getiri Takibi")

with st.sidebar:
    tickers_str = st.text_area("İzlenecek Semboller", value="THYAO.IS, ASELS.IS\nAAPL, MSFT", height=80)
    start_dt = st.date_input("Başlangıç", value=date.today() - timedelta(days=365))
    end_dt = st.date_input("Bitiş", value=date.today())
    run = st.button("Verileri Getir", type="primary")

tickers = parse_tickers(tickers_str)
if not tickers:
    st.info("Lütfen en az bir sembol girin.")
    st.stop()

if run:
    if start_dt >= end_dt:
        st.error("Başlangıç tarihi bitiş tarihinden önce olmalı!")
        st.stop()

    st.subheader("Sonuçlar")
    for t in tickers[:3]:
        st.markdown(f"### {t}")
        try:
            df = fetch_monthly_data(t, start_dt, end_dt)
            changes = calc_monthly_changes(df)
            if not changes.empty:
                st.dataframe(changes, use_container_width=True)
            else:
                st.info("Yeterli veri yok, lütfen tarih aralığını genişletin veya başka sembol deneyin.")
        except Exception as e:
            st.error(f"Veri çekme hatası: {e}")

st.caption("Veriler Yahoo Finance'dan aylık olarak çekilir. Sadece kapanış fiyatı ve aylık değişim yüzdesi gösterilir.")
