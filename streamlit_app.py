import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from datetime import date, timedelta

# Sembol listesini dosyadan yükle
def load_symbols(filepath="bist_symbols.csv"):
    try:
        df = pd.read_csv(filepath)
        # Kolonlar: symbol, company, exchange (örnek: ASELS.IS, Aselsan, BIST)
        return df
    except Exception:
        return pd.DataFrame(columns=["symbol", "company", "exchange"])

# Yahoo Finance ile yeni sembolleri çek ve listeye ekle
def update_symbols_from_yahoo(query, filepath="bist_symbols.csv"):
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        new_rows = []
        for item in data.get("quotes", []):
            if item.get("quoteType") in ["EQUITY", "ETF"]:
                new_rows.append({
                    "symbol": item.get("symbol"),
                    "company": item.get("shortname", ""),
                    "exchange": item.get("exchange", "")
                })
        # Yeni sembolleri dosyaya ekle
        if new_rows:
            df_old = load_symbols(filepath)
            df_new = pd.DataFrame(new_rows)
            df_combined = pd.concat([df_old, df_new]).drop_duplicates(subset=["symbol"]).reset_index(drop=True)
            df_combined.to_csv(filepath, index=False)
            return df_combined
        else:
            return load_symbols(filepath)
    except Exception:
        return load_symbols(filepath)

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

# Uygulama arayüzü
st.set_page_config(page_title="Kısaltma Listesi ve Takip", page_icon="📈", layout="wide")
st.title("📈 Kısaltma Listesiyle Hisse/ETF Takip")

if "selected_symbols" not in st.session_state:
    st.session_state.selected_symbols = []

with st.sidebar:
    st.subheader("Kısaltma Ara & Ekle")
    symbol_df = load_symbols()
    search_query = st.text_input("Firma adı veya sembol ara (örn: aselsan, apple, akbank, aapl, msft)")
    if search_query:
        # Hem company hem symbol'da arama
        results = symbol_df[symbol_df.apply(lambda row: search_query.lower() in row["company"].lower() or search_query.lower() in row["symbol"].lower(), axis=1)]
        if not results.empty:
            for idx, row in results.iterrows():
                cols = st.columns([4,1])
                with cols[0]:
                    st.write(f"**{row['symbol']}** | {row['company']} | {row['exchange']}")
                with cols[1]:
                    if row['symbol'] in st.session_state.selected_symbols:
                        if st.button(f"Çıkar ({row['symbol']})", key=f"remove_{row['symbol']}"):
                            st.session_state.selected_symbols.remove(row['symbol'])
                    else:
                        if st.button(f"Ekle ({row['symbol']})", key=f"add_{row['symbol']}"):
                            st.session_state.selected_symbols.append(row['symbol'])
        else:
            st.warning("Hiç sembol bulunamadı. 'Güncelle' ile yeni arama ekleyebilirsiniz.")
    # Sembol listesini güncelle
    if st.button("🔄 Güncelle", key="update_symbols") and search_query:
        symbol_df = update_symbols_from_yahoo(search_query)
        st.success("Kısaltma listesi güncellendi!")

    st.markdown("---")
    st.subheader("Takip Listeniz")
    if st.session_state.selected_symbols:
        st.write(", ".join(st.session_state.selected_symbols))
    else:
        st.info("Henüz bir sembol eklemediniz.")
    start_dt = st.date_input("Başlangıç", value=date.today() - timedelta(days=365))
    end_dt = st.date_input("Bitiş", value=date.today())
    run = st.button("Verileri Getir", type="primary")

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
    "Sembol arama işlemi önce yerel kısaltma listesinden yapılır, istenirse Yahoo Finance'dan yeni semboller eklenebilir."
)
