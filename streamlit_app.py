import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
import requests

def parse_tickers(raw: str):
    parts = [p.strip().upper() for p in raw.replace("\n", ",").replace(";", ",").split(",")]
    return [p for p in parts if p]

def yahoo_finance_symbol_search(company_name: str):
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={company_name}"
    try:
        resp = requests.get(url, timeout=7)
        data = resp.json()
        # Sonuçlardan uygun olan ilk sembolü bul
        for item in data.get("quotes", []):
            # Eğer hisse ise (ör: equity), sembolü döndür
            if item.get("quoteType") in ["EQUITY", "ETF"]:
                return item.get("symbol")
        return None
    except Exception as e:
        return None

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
    df = df.sort_index()
    df["Ay"] = df.index.strftime("%Y-%m")
    df["Aylık Değişim (%)"] = df["Kapanış"].pct_change().multiply(100).round(2)
    return df[["Ay", "Kapanış", "Aylık Değişim (%)"]].dropna()

st.set_page_config(page_title="Aylık Getiri", page_icon="📈", layout="wide")
st.title("📈 Hisse Senedi Aylık Getiri Takibi")

with st.sidebar:
    st.subheader("Sembol ile sorgu")
    # Otomatik eklenen semboller burada tutulur
    if "auto_tickers" not in st.session_state:
        st.session_state.auto_tickers = []
    auto_tickers = st.session_state.auto_tickers

    tickers_str = st.text_area("İzlenecek Semboller (manuel veya otomatik eklenir)", value=", ".join(auto_tickers), height=80)
    st.markdown("---")
    st.subheader("Firma isminden sembol bul ve ekle")
    company_names_raw = st.text_area("Firma adları (ör: Türk Hava Yolları, Apple)\nBirden fazla firma için: satır başı veya virgül ile ayırabilirsiniz.")
    ekle = st.button("EKLE")
    if ekle and company_names_raw:
        names = [n.strip() for n in company_names_raw.replace("\n", ",").split(",") if n.strip()]
        eklenenler = []
        bulunamayanlar = []
        for name in names:
            symbol = yahoo_finance_symbol_search(name)
            if symbol:
                eklenenler.append(f"{name} → {symbol}")
                # Sembol zaten listede yoksa ekle
                if symbol not in auto_tickers:
                    auto_tickers.append(symbol)
            else:
                bulunamayanlar.append(name)
        if eklenenler:
            st.success("Eklenenler:\n" + "\n".join(eklenenler))
        if bulunamayanlar:
            st.warning("Sembol bulunamayanlar:\n" + ", ".join(bulunamayanlar))
        # TextArea'yı güncelle
        st.session_state.auto_tickers = auto_tickers
    st.markdown("---")
    start_dt = st.date_input("Başlangıç", value=date.today() - timedelta(days=365))
    end_dt = st.date_input("Bitiş", value=date.today())
    run = st.button("Verileri Getir", type="primary")

# Son sembol listesini hazırla
tickers = parse_tickers(", ".join(st.session_state.get("auto_tickers", [])))
if tickers_str:
    # Manuel eklemeden gelenleri de ekle
    tickers += [t for t in parse_tickers(tickers_str) if t not in tickers]
tickers = list(dict.fromkeys(tickers)) # Tekrarları sil

if not tickers:
    st.info("Lütfen en az bir sembol girin veya firma adı ile ekleyin.")
    st.stop()

if run:
    if start_dt >= end_dt:
        st.error("Başlangıç tarihi bitiş tarihinden önce olmalı!")
        st.stop()

    st.subheader("Sonuçlar")
    for t in tickers[:5]:
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

st.caption("Veriler Yahoo Finance'dan aylık olarak çekilir. Sadece kapanış fiyatı ve aylık değişim yüzdesi gösterilir.\nFirma adına göre sembol bulmak için üstteki alanı kullanabilirsiniz. Sembol bulma işlemi Yahoo Finance arama API'si ile yapılır.")
