streamlit_app.py

import io import math from datetime import date, timedelta from typing import List, Dict

import numpy as np import pandas as pd import yfinance as yf import streamlit as st

st.set_page_config(page_title="Küresel Borsa Takip", layout="wide")

-------------------- Yardımcılar --------------------

@st.cache_data(show_spinner=False) def load_prices(tickers: List[str], start: date, end: date, interval: str) -> pd.DataFrame: """Tickers -> Çoklu sütun (Close, Open, High, Low, Volume) DataFrame döndürür.""" df = yf.download( tickers=tickers, start=start, end=end + timedelta(days=1),  # end dahil olsun diye +1 interval=interval, auto_adjust=False, group_by="ticker", threads=True, progress=False, ) # yfinance farklı şekillerde dönebilir; normalize edelim if isinstance(df.columns, pd.MultiIndex): # Çoklu ticker return df else: # Tek ticker -> çoklu index oluştur df = pd.concat({tickers[0]: df}, axis=1) return df

def compute_indicators(px: pd.DataFrame, close_col: str = "Close") -> pd.DataFrame: """Kapanış fiyatından temel indikatörleri hesaplar.""" s = px[close_col].copy() out = pd.DataFrame(index=px.index) out["Close"] = s # Günlük/periodik getiri out["Return"] = s.pct_change() out["CumReturn"] = (1 + out["Return"]).cumprod() - 1 # Basit hareketli ortalama out["SMA20"] = s.rolling(20).mean() out["SMA50"] = s.rolling(50).mean() # Üstel hareketli ortalama out["EMA20"] = s.ewm(span=20, adjust=False).mean() # Volatilite (yıllık varsayımsal) – dönemsel std * sqrt(252) out["Volatility"] = out["Return"].rolling(20).std() * math.sqrt(252) # RSI(14) delta = s.diff() up = np.where(delta > 0, delta, 0.0) down = np.where(delta < 0, -delta, 0.0) roll_up = pd.Series(up, index=s.index).rolling(14).mean() roll_down = pd.Series(down, index=s.index).rolling(14).mean() rs = roll_up / roll_down out["RSI14"] = 100 - (100 / (1 + rs)) # Bollinger(20, 2) ma20 = s.rolling(20).mean() std20 = s.rolling(20).std() out["BB_MA20"] = ma20 out["BB_Upper"] = ma20 + 2 * std20 out["BB_Lower"] = ma20 - 2 * std20 return out

def filter_columns(df: pd.DataFrame, selected: List[str]) -> pd.DataFrame: keep = [c for c in df.columns if c in selected] return df[keep]

def build_excel(prices: pd.DataFrame, selections: Dict[str, List[str]]) -> bytes: """Her ticker için ayrı sayfa + Özet sayfası ile bir Excel dosyası üretir.""" output = io.BytesIO() with pd.ExcelWriter(output, engine="xlsxwriter") as writer: summary_rows = [] # Çoklu index: (Field, Ticker) veya (Ticker, Field) olabilir; normalize edelim # Beklenen: prices[ticker][field] for ticker in selections.keys(): if ticker not in prices.columns.get_level_values(0): continue df_t = prices[ticker].copy() # İndikatör seti ind = compute_indicators(df_t) # Birleştir (OHLCV + ind) merged = df_t.join(ind, how="left") # Seçime göre filtrele cols = selections[ticker] if cols: merged = filter_columns(merged, cols) merged.to_excel(writer, sheet_name=ticker[:31]) # Özet satırı (son değerler) last = merged.dropna().iloc[-1:] if not last.empty: row = { "Ticker": ticker, "LastClose": float(last.get("Close", pd.Series([np.nan])).values[0]) if "Close" in last.columns else np.nan, "CumReturn": float(last.get("CumReturn", pd.Series([np.nan])).values[0]) if "CumReturn" in last.columns else np.nan, "Volatility": float(last.get("Volatility", pd.Series([np.nan])).values[0]) if "Volatility" in last.columns else np.nan, "RSI14": float(last.get("RSI14", pd.Series([np.nan])).values[0]) if "RSI14" in last.columns else np.nan, } summary_rows.append(row) # Summary if summary_rows: pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False) return output.getvalue()

-------------------- UI --------------------

st.title("📈 Küresel Borsa Takip Uygulaması") st.caption( "Dünya borsalarından hisseleri takip edin, istediğiniz aralıkta indikatörleri hesaplayın ve Excel olarak indirin." )

with st.sidebar: st.header("Ayarlar") tickers_raw = st.text_area( "Ticker listesi (virgülle ayırın)", help=( "Örnekler: AAPL, MSFT, TSLA (NASDAQ); 7203.T (TSE); RACE.MI (Borsa Italiana); " "BIST için örn: THYAO.IS, ASELS.IS. Endeksler için ^XU100, ^GSPC gibi." ), placeholder="AAPL, MSFT, THYAO.IS, ^XU100", ) c1, c2 = st.columns(2) with c1: start_date = st.date_input("Başlangıç", value=date.today() - timedelta(days=365)) with c2: end_date = st.date_input("Bitiş", value=date.today())

interval = st.selectbox(
    "Veri aralığı (interval)",
    options=["1d", "1wk", "1mo", "1h", "30m", "15m", "5m", "1m"],
    index=0,
    help="Dakikalık aralıklar için son 30 gün sınırı olabilir.",
)

st.markdown("---")
st.subheader("Excel'e Dahil Edilecek Sütunlar")
default_cols = [
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "Return",
    "CumReturn",
    "SMA20",
    "SMA50",
    "EMA20",
    "Volatility",
    "RSI14",
    "BB_MA20",
    "BB_Upper",
    "BB_Lower",
]
chosen_cols = st.multiselect(
    "Seçiniz",
    options=default_cols,
    default=["Close", "Return", "CumReturn", "SMA20", "RSI14", "Volatility"],
)

st.markdown("---")
st.caption(
    "İpucu: Farklı borsalardaki hisseleri aynı listede takip edebilirsiniz. Doğru ticker yazımı için ilgili borsa soneki kullanın (örn. BIST: .IS)."
)

Ana alan

if tickers_raw: tickers = [t.strip() for t in tickers_raw.split(",") if t.strip()] try: data = load_prices(tickers, start_date, end_date, interval) except Exception as e: st.error(f"Veri indirilirken hata oluştu: {e}") st.stop()

# Önizleme sekmeleri
tabs = st.tabs([f"📊 {t}" for t in tickers])
for t, tab in zip(tickers, tabs):
    with tab:
        if t in data.columns.get_level_values(0):
            df_t = data[t].copy()
            ind = compute_indicators(df_t)
            merged = df_t.join(ind, how="left")
            st.dataframe(merged.tail(200), use_container_width=True)
            # Basit grafik
            st.line_chart(merged[["Close", "SMA20", "SMA50"]].dropna())
        else:
            st.warning(f"{t} için veri bulunamadı.")

# Excel oluşturma
selections = {t: chosen_cols for t in tickers}
excel_bytes = build_excel(data, selections)
st.download_button(
    label="📥 Excel Olarak İndir",
    data=excel_bytes,
    file_name="borsa_takip.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

else: st.info("Başlamak için sol taraftan en az bir ticker girin.")

-------------------- Alt Bilgi --------------------

st.markdown( """ Notlar
- Veri kaynağı: Yahoo Finance (yfinance). Tüm dünya borsalarının büyük bir kısmını destekler.
- İnterval kısıtları: 1m/5m gibi dakikalık verilerde Yahoo sınırlamaları olabilir.
- İhracat dosyası: Her hisse için ayrı bir Excel sayfası ve "Summary" sayfası içerir.
- İstatistikler: SMA/EMA, RSI, Bollinger, volatilite, getiriler dahil.
- Geliştirme: İsterseniz ek indikatörler, alarm/uyarılar, canlı veri ve portföy PnL modülü eklenebilir. """ )

