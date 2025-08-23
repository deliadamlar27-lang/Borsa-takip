import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
import requests

def yahoo_finance_multi_symbol_search(query: str, limit=20):
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
    try:
        resp = requests.get(url, timeout=7)
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
    except Exception:
        return []

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
    df = df.sort_index()
    df["Ay"] = df.index.strftime("%Y-%m")
    df["Aylık Değişim (%)"] = df["Kapanış"].pct_change().multiply(100).round(2)
    return df[["Ay", "Kapanış", "Aylık Değişim (%)"]].dropna()

st.set_page_config(page_title="Aylık Getiri", page_icon="📈", layout="wide")
st.title("📈 Hisse Senedi Aylık Getiri Takibi")

with st.sidebar:
    st.subheader("İzlenecek Semboller")
    if "auto_tickers" not in st.session_state:
        st.session_state.auto_tickers = []
    auto_tickers = st.session_state.auto_tickers

    tickers_str = st.text_area("İzlenecek Semboller (manuel veya otomatik eklenir)", value=", ".join(auto_tickers), height=80)
    st.markdown("---")
    st.subheader("Dünya çapında sembol ara & ekle")
    search_query = st.text_input("Anahtar kelime ile sembol ara (örn: apple, turk, bank, istanbul, tesla, germany, etf, vs.)")
    
    search_results = []
    if search_query:
        search_results = yahoo_finance_multi_symbol_search(search_query)
        if search_results:
            st.markdown(f"**{search_query}** için bulunan ilk {len(search_results)} sembol:")
            for idx, item in enumerate(search_results):
                col1, col2 = st.columns([4,1])
                with col1:
                    st.write(f"**{item['symbol']}** | {item['shortname']} | {item['exchange']} | {item['type']}")
                with col2:
                    if st.button(f"Ekle ({item['symbol']})", key=f"add_{item['symbol']}_{idx}"):
                        if item['symbol'] not in auto_tickers:
                            auto_tickers.append(item['symbol'])
                        st.success(f"'{item['symbol']}' sembolü eklendi!")
        else:
            st.warning("Hiç sembol bulunamadı. Daha genel bir anahtar kelime deneyin.")
    st.markdown("---")
    start_dt = st.date_input("Başlangıç", value=date.today() - timedelta(days=365))
    end_dt = st.date_input("Bitiş", value=date.today())
    run = st.button("Verileri Getir", type="primary")

tickers = parse_tickers(", ".join(st.session_state.get("auto_tickers", [])))
if tickers_str:
    tickers += [t for t in parse_tickers(tickers_str) if t not in tickers]
tickers = list(dict.fromkeys(tickers))

if not tickers:
    st.info("Lütfen en az bir sembol girin veya arama yapıp ekleyin.")
    st.stop()

if run:
    if start_dt >= end_dt:
        st.error("Başlangıç tarihi bitiş tarihinden önce olmalı!")
        st.stop()

    st.subheader("Sonuçlar")
    for t in tickers[:10]:
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
    "Dünyadaki tüm sembolleri bulmak için üstteki anahtar kelime arama alanını kullanabilirsiniz. Sembol bulma işlemi Yahoo Finance arama API'si ile yapılır."
)
