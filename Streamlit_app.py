# streamlit_app.py

import io
import math
from datetime import date, timedelta
from typing import List, Dict

import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st

st.set_page_config(page_title="Küresel Borsa Takip", layout="wide")

# -------------------- Yardımcı Fonksiyonlar --------------------

@st.cache_data(show_spinner=False)
def load_prices(tickers: List[str], start: date, end: date, interval: str) -> pd.DataFrame:
    """
    Çoklu ticker indirir. Çoklu-seviyeli kolonlar: [ticker -> (Open, High, Low, Close, Volume, ...)]
    """
    df = yf.download(
        tickers=tickers,
        start=start,
        end=end + timedelta(days=1),  # bitiş dahil
        interval=interval,
        auto_adjust=False,
        group_by="ticker",
        threads=True,
        progress=False,
    )
    if isinstance(df.columns, pd.MultiIndex):
        return df
    else:
        # Tek ticker durumunda kolonları çoklu-index haline getir
        return pd.concat({tickers[0]: df}, axis=1)

def compute_indicators(ohlcv: pd.DataFrame, close_col: str = "Close") -> pd.DataFrame:
    """
    Kapanış fiyatından temel indikatörleri hesaplar.
    """
    s = ohlcv[close_col].copy()
    out = pd.DataFrame(index=ohlcv.index)
    out["Close"] = s

    # Getiri ve kümülatif getiri
    ret = s.pct_change()
    out["Return"] = ret
    out["CumReturn"] = (1 + ret).cumprod() - 1

    # SMA / EMA
    out["SMA20"] = s.rolling(20).mean()
    out["SMA50"] = s.rolling(50).mean()
    out["EMA20"] = s.ewm(span=20, adjust=False).mean()

    # Yıllıklaştırılmış volatilite ~ 20 günlük std * sqrt(252)
    out["Volatility"] = ret.rolling(20).std() * math.sqrt(252)

    # RSI(14)
    delta = s.diff()
    up = np.where(delta > 0, delta, 0.0)
    down = np.where(delta < 0, -delta, 0.0)
    roll_up = pd.Series(up, index=s.index).rolling(14).mean()
    roll_down = pd.Series(down, index=s.index).rolling(14).mean()
    rs = roll_up / roll_down
    out["RSI14"] = 100 - (100 / (1 + rs))

    # Bollinger(20, 2)
    ma20 = s.rolling(20).mean()
    std20 = s.rolling(20).std()
    out["BB_MA20"] = ma20
    out["BB_Upper"] = ma20 + 2 * std20
    out["BB_Lower"] = ma20 - 2 * std20

    return out

def filter_columns(df: pd.DataFrame, selected: List[str]) -> pd.DataFrame:
    keep = [c for c in df.columns if c in selected]
    return df[keep] if keep else df

def build_excel(prices: pd.DataFrame, selections: Dict[str, List[str]]) -> bytes:
    """
    Her ticker için ayrı sayfa + Summary sayfasıyla Excel çıktısı üretir.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        summary_rows = []

        # prices çoklu indexli: level 0 -> ticker, level 1 -> OHLCV alanları
        tickers = sorted(set(prices.columns.get_level_values(0)))

        for ticker in tickers:
            if ticker not in selections:
                continue

            df_t = prices[ticker].copy()
            ind = compute_indicators(df_t)
            merged = df_t.join(ind, how="left")

            cols = selections[ticker]
            if cols:
                merged = filter_columns(merged, cols)

            merged.to_excel(writer, sheet_name=ticker[:31])

            last = merged.dropna().iloc[-1:] if not merged.empty else pd.DataFrame()
            if not last.empty:
                def _get(col):
                    return float(last[col].values[0]) if col in last.columns else np.nan

                summary_rows.append({
                    "Ticker": ticker,
                    "LastClose": _get("Close"),
                    "CumReturn": _get("CumReturn"),
                    "Volatility": _get("Volatility"),
                    "RSI14": _get("RSI14"),
                })

        if summary_rows:
            pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

    return output.getvalue()

# -------------------- Arayüz --------------------

st.title("📈 Küresel Borsa Takip Uygulaması")
st.caption("Dünya borsalarından hisseleri seç, aralığı belirle, indikatörleri hesapla ve Excel indir.")

with st.sidebar:
    st.header("Ayarlar")

    tickers_raw = st.text_area(
        "Ticker listesi (virgülle ayırın)",
        placeholder="AAPL, MSFT, THYAO.IS, ^XU100, 7203.T, RACE.MI",
        help=(
            "BIST için .IS soneki kullan: ASELS.IS, THYAO.IS. "
            "Japonya için .T (örn. 7203.T), İtalya için .MI (RACE.MI), "
            "endeksler ^XU100, ^GSPC gibi."
        ),
    )

    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Başlangıç", value=date.today() - timedelta(days=365))
    with c2:
        end_date = st.date_input("Bitiş", value=date.today())

    interval = st.selectbox(
        "Veri aralığı (interval)",
        options=["1d", "1wk", "1mo", "1h", "30m", "15m", "5m", "1m"],
        index=0,
        help="Dakikalık aralıklarda Yahoo kısıtları olabilir (son 30 gün vb.).",
    )

    st.markdown("---")
    st.subheader("Excel'e Dahil Edilecek Sütunlar")
    default_cols = [
        "Open", "High", "Low", "Close", "Volume",
        "Return", "CumReturn", "SMA20", "SMA50", "EMA20",
        "Volatility", "RSI14", "BB_MA20", "BB_Upper", "BB_Lower",
    ]
    chosen_cols = st.multiselect(
        "Seçiniz",
        options=default_cols,
        default=["Close", "Return", "CumReturn", "SMA20", "RSI14", "Volatility"],
    )

    st.markdown("---")
    st.caption("İpucu: Farklı borsalardan hisseleri birlikte takip edebilirsin. Doğru sonekleri kullanmayı unutma.")

if tickers_raw:
    tickers = [t.strip() for t in tickers_raw.split(",") if t.strip()]
    try:
        data = load_prices(tickers, start_date, end_date, interval)
    except Exception as e:
        st.error(f"Veri indirilirken hata: {e}")
        st.stop()

    tabs = st.tabs([f"📊 {t}" for t in tickers])
    for t, tab in zip(tickers, tabs):
        with tab:
            if t in data.columns.get_level_values(0):
                df_t = data[t].copy()
                ind = compute_indicators(df_t)
                merged = df_t.join(ind, how="left")

                st.dataframe(merged.tail(200), use_container_width=True)
                with st.container(border=True):
                    st.line_chart(merged[["Close", "SMA20", "SMA50"]].dropna())
            else:
                st.warning(f"{t} için veri bulunamadı.")

    selections = {t: chosen_cols for t in tickers}
    excel_bytes = build_excel(data, selections)
    st.download_button(
        label="📥 Excel Olarak İndir",
        data=excel_bytes,
        file_name="borsa_takip.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
else:
    st.info("Başlamak için sol taraftaki alana en az bir ticker gir.")

# -------------------- Alt Bilgi --------------------
st.markdown(
    """
**Notlar**
- Veri kaynağı: Yahoo Finance (yfinance).
- Dakikalık verilerde tarih aralığı sınırlı olabilir.
- Excel çıktısı: Her hisse ayrı sayfa + “Summary”.
- İndikatörler: SMA/EMA, RSI, Bollinger, volatilite, getiriler.
"""
)
