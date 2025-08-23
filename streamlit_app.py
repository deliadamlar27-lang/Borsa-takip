import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from datetime import date, timedelta

def yahoo_finance_multi_symbol_search(query: str, limit=50):
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        results = []
        for item in data.get("quotes", []):
            if item.get("quoteType") in ["EQUITY", "ETF"]:
                results.append({
                    "symbol": item.get("symbol"),
                    "shortname": item.get("shortname", ""),
                    "exchange": item.get("exchange", ""),
                    "type": item.get("quoteType", ""),
                    "score": item.get("score", 0)
                })
            if len(results) >= limit:
                break
        return results
    except Exception as e:
        return []

def parse_tickers(tickers):
    return [t.strip().upper() for t in tickers if t.strip()]

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

st.set_page_config(page_title="Kısaltma Listesi ve Takip", page_icon="📈", layout="wide")
st.title("📈 Tüm Dünya Hisse/ETF Kısaltmaları Listesi ve Takip")

# Session state: seçili semboller ve arama sonuçları
if "selected_symbols" not in st.session_state:
    st.session_state.selected_symbols = []
if "symbol_search_results" not in st.session_state:
    st.session_state.symbol_search_results = []

with st.sidebar:
    st.subheader("Dünya çapında sembol ara ve yönet")
    search_query = st.text_input("Anahtar kelime ile sembol ara (örn: apple, bank, istanbul, tesla, germany, etf, vs.)", key="search_query")
    search_limit = st.number_input("Gösterilecek maksimum sembol sayısı (örn: 50)", min_value=5, max_value=100, value=30, step=1)

    # Güncelle butonu ile arama sonuçları yenilenir
    if st.button("🔄 Güncelle / Yenile", key="update_search"):
        if search_query:
            st.session_state.symbol_search_results = yahoo_finance_multi_symbol_search(search_query, search_limit)
        else:
            st.session_state.symbol_search_results = []
    
    # Arama sonuçlarını göster ve sembol ekleme/çıkarma imkanı ver
    if st.session_state.symbol_search_results:
        st.write(f"**{search_query}** için bulunan semboller:")
        for item in st.session_state.symbol_search_results:
            symbol = item['symbol']
            label = f"{symbol} | {item['shortname']} | {item['exchange']} | {item['type']}"
            # Ekli ise çıkar butonu, ekli değilse ekle butonu
            cols = st.columns([5,1])
            with cols[0]:
                st.write(label)
            with cols[1]:
                if symbol in st.session_state.selected_symbols:
                    if st.button(f"Çıkar ({symbol})", key=f"remove_{symbol}"):
                        st.session_state.selected_symbols.remove(symbol)
                else:
                    if st.button(f"Ekle ({symbol})", key=f"add_{symbol}"):
                        st.session_state.selected_symbols.append(symbol)
    else:
        st.info("Yeni sembol araması için anahtar kelime girip 'Güncelle / Yenile' butonuna basın.")

    st.markdown("---")
    st.subheader("Takip Listeniz")
    if st.session_state.selected_symbols:
        st.write(", ".join(st.session_state.selected_symbols))
    else:
        st.info("Henüz bir sembol eklemediniz.")
    st.markdown("---")
    start_dt = st.date_input("Başlangıç", value=date.today() - timedelta(days=365))
    end_dt = st.date_input("Bitiş", value=date.today())
    run = st.button("Verileri Getir", type="primary")

# Seçili sembollerin verileri
tickers = st.session_state.selected_symbols

if run:
    if not tickers:
        st.warning("Takip listeniz boş. Lütfen en az bir sembol ekleyin.")
    elif start_dt >= end_dt:
        st.error("Başlangıç tarihi bitiş tarihinden önce olmalı!")
    else:
        st.subheader("Seçilen Sembollerin Sonuçları")
        for t in tickers:
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
    "Sembol arama işlemi Yahoo Finance arama API'si ile yapılır. Takip listenizdeki sembollerin verilerini topluca görebilirsiniz."
)
