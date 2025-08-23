import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
import requests

# Manuel eşleme: BIST ve yaygın yabancı hisseler
MANUAL_SYMBOLS = {
    "aselsan": "ASELS.IS",
    "türk hava yolları": "THYAO.IS",
    "garanti": "GARAN.IS",
    "akbank": "AKBNK.IS",
    "koç holding": "KCHOL.IS",
    "apple": "AAPL",
    "microsoft": "MSFT",
    "ford": "F",
    "tesla": "TSLA",
    "amazon": "AMZN",
    # İstediğin kadar ekleyebilirsin!
}

def parse_tickers(raw: str):
    parts = [p.strip().upper() for p in raw.replace("\n", ",").replace(";", ",").split(",")]
    return [p for p in parts if p]

def yahoo_finance_symbol_search(company_name: str):
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={company_name}"
    try:
        resp = requests.get(url, timeout=7)
        data = resp.json()
        for item in data.get("quotes", []):
            if item.get("quoteType") in ["EQUITY", "ETF"]:
                return item.get("symbol")
        return None
    except Exception:
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
    if "auto_tickers" not in st.session_state:
        st.session_state.auto_tickers = []
    auto_tickers = st.session_state.auto_tickers

    tickers_str = st.text_area("İzlenecek Semboller (manuel veya otomatik eklenir)", value=", ".join(auto_tickers), height=80)
    st.markdown("---")
    st.subheader("Firma isminden sembol bul ve ekle")

    company_names_raw = st.text_area(
        "Firma adları (ör: Türk Hava Yolları, Apple)\nBirden fazla firma için: satır başı veya virgül ile ayırabilirsiniz."
    )

    names = [n.strip().lower() for n in company_names_raw.replace("\n", ",").split(",") if n.strip()]
    for idx, name in enumerate(names):
        if name:
            symbol = yahoo_finance_symbol_search(name)
            if not symbol:
                symbol = MANUAL_SYMBOLS.get(name)
            if symbol:
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.info(f"**{name.title()}** için sembol olarak '{symbol}' mu demek istediniz?")
                with col2:
                    if st.button(f"Ekle ({symbol})", key=f"add_{symbol}_{idx}"):
                        if symbol not in auto_tickers:
                            auto_tickers.append(symbol)
                        st.success(f"'{symbol}' sembolü eklendi!")
            else:
                st.warning(f"{name.title()} için sembol bulunamadı.")
    st.markdown("---")
    start_dt = st.date_input("Başlangıç", value=date.today() - timedelta(days=365))
    end_dt = st.date_input("Bitiş", value=date.today())
    run = st.button("Verileri Getir", type="primary")

tickers = parse_tickers(", ".join(st.session_state.get("auto_tickers", [])))
if tickers_str:
    tickers += [t for t in parse_tickers(tickers_str) if t not in tickers]
tickers = list(dict.fromkeys(tickers))

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

st.caption(
    "Veriler Yahoo Finance'dan aylık olarak çekilir. Sadece kapanış fiyatı ve aylık değişim yüzdesi gösterilir. "
    "Firma adına göre sembol bulmak için üstteki alanı kullanabilirsiniz. Sembol bulma işlemi Yahoo Finance arama API'si ve manuel eşleme ile yapılır."
)
