"""
Global Borsa Takip Uygulaması (Streamlit)
=========================================

Nasıl çalıştırılır?
-------------------
1) Python 3.10+ kurulu olmalı
2) Aşağıdaki kütüphaneleri yükleyin:
   pip install -U streamlit yfinance pandas numpy plotly XlsxWriter
3) Bu dosyayı kaydedin (ör: app.py) ve çalıştırın:
   streamlit run app.py

Notlar
-----
- Yahoo Finance sembol kurallarıyla tüm dünyadaki bir çok borsadan veri çekebilirsiniz.
  * BIST (İstanbul): THYAO.IS, ASELS.IS, AKBNK.IS gibi
  * NYSE/Nasdaq (ABD): AAPL, MSFT, TSLA
  * LSE (Londra): HSBA.L, BP.L
  * XETRA (Almanya): SAP.DE, BMW.DE
  * TSE (Tokyo): 7203.T (Toyota)
  * HKEX (Hong Kong): 0700.HK (Tencent)
  * NSE/BSE (Hindistan): RELIANCE.NS, TCS.NS
- 1 dakikalık (1m) gibi kısa aralıklar Yahoo Finance tarafından son ~30 günle sınırlı olabilir.
- Bu uygulama Excel’e (XLSX) çoklu sayfa olarak (her sembol ayrı sayfa) dışa aktarma yapar.
- Ayarlarınızı JSON olarak indirip daha sonra tekrar yükleyerek kolayca revize edebilirsiniz.

Lisans
------
Bu örnek eğitim amaçlıdır; yatırım tavsiyesi değildir.
"""

from __future__ import annotations
import io
from datetime import date, timedelta
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# -----------------------------
# Yardımcı Fonksiyonlar
# -----------------------------

def parse_tickers(raw: str) -> List[str]:
    parts = [p.strip().upper() for p in raw.replace("\n", ",").replace(";", ",").split(",")]
    return [p for p in parts if p]

@st.cache_data(show_spinner=False, ttl=60 * 60)
def fetch_data(ticker: str, start_dt: date, end_dt: date, interval: str) -> pd.DataFrame:
    df = yf.download(ticker, start=start_dt, end=end_dt + timedelta(days=1), interval=interval, progress=False, auto_adjust=False)
    # Kolon adlarını standardize edelim
    if not df.empty:
        df = df.rename(columns={
            "Open": "Açılış",
            "High": "Yüksek",
            "Low": "Düşük",
            "Close": "Kapanış",
            "Adj Close": "Düzeltilmiş Kapanış",
            "Volume": "Hacim",
        })
        df.index.name = "Tarih"
    return df

def allowed_interval_and_range(interval: str, start_dt: date, end_dt: date) -> Tuple[bool, str]:
    days = (end_dt - start_dt).days
    if interval == "1m" and days > 30:
        return False, "1 dakikalık veri yalnızca ~30 gün için kullanılabilir. Lütfen daha kısa bir tarih aralığı seçin veya daha uzun aralık seçin."
    if interval in {"2m", "5m", "15m", "30m", "60m", "90m"} and days > 60:
        return False, "Dakikalık veriler genellikle son ~60 gün ile sınırlıdır. Lütfen tarih aralığını daraltın veya günlük/haftalık/aylık aralık kullanın."
    return True, ""

def build_stats(df: pd.DataFrame) -> pd.DataFrame:
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
        "Yıllıklaştırılmış Vol %": (returns.std() * np.sqrt(252)) * 100.0 if len(returns) > 1 else np.nan,
        "Maks. Düşüş %": ( (prices / prices.cummax()).min() - 1.0) * 100.0,
    }
    out = pd.DataFrame([summary])
    return out.round(3)

# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title="Global Borsa Takibi", page_icon="📈", layout="wide")

st.title("📈 Global Borsa Takip Uygulaması")
st.caption("Yahoo Finance verileri kullanılarak çoklu borsalardan sembol takibi, grafikleme ve Excel'e aktarım.")

with st.sidebar:
    st.header("Ayarlar")

    # Örnek semboller
    with st.expander("Sembol örnekleri / borsa son ekleri"):
        st.markdown(
            """
            - **BIST**: `THYAO.IS`, `ASELS.IS`, `AKBNK.IS`
            - **ABD**: `AAPL`, `MSFT`, `TSLA`
            - **Londra**: `HSBA.L`, `BP.L`
            - **Almanya (XETRA)**: `SAP.DE`, `BMW.DE`
            - **Tokyo**: `7203.T` (Toyota)
            - **Hong Kong**: `0700.HK` (Tencent)
            - **Hindistan**: `RELIANCE.NS`, `TCS.NS`
            """
        )

    tickers_str = st.text_area(
        "Semboller (virgül / satır ile ayırın)",
        value="THYAO.IS, ASELS.IS\nAAPL, MSFT",
        height=90,
        help="Birden fazla sembol girebilirsiniz. Örn: THYAO.IS, AAPL, HSBA.L"
    )

    col_a, col_b = st.columns(2)
    with col_a:
        start_dt = st.date_input("Başlangıç", value=date.today() - timedelta(days=180))
    with col_b:
        end_dt = st.date_input("Bitiş", value=date.today())

    interval = st.selectbox(
        "Zaman aralığı",
        options=["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "1wk", "1mo", "3mo"],
        index=10,
        help="Dakikalık aralıklar kısa tarih aralığı gerektirir."
    )

    what_to_show = st.multiselect(
        "Grafikte gösterilecek seriler",
        options=["Kapanış", "Düzeltilmiş Kapanış", "Hacim", "Mum (OHLC)"],
        default=["Kapanış"],
    )

    st.divider()
    st.subheader("Ayarları Dışa/İçe Aktar")
    cfg_name = st.text_input("Ayar adı", value="varsayilan")
    cfg_download = {
        "tickers": parse_tickers(tickers_str),
        "start": str(start_dt),
        "end": str(end_dt),
        "interval": interval,
        "show": what_to_show,
        "name": cfg_name,
    }
    st.download_button("Ayarları indir (JSON)", data=pd.Series(cfg_download).to_json(), file_name=f"ayar_{cfg_name}.json")
    uploaded_cfg = st.file_uploader("Ayar yükle (JSON)", type=["json"])
    if uploaded_cfg is not None:
        try:
            loaded = pd.read_json(uploaded_cfg)
            # loaded burada pandas Series olarak gelebilir
            if isinstance(loaded, pd.Series):
                loaded = loaded.to_dict()
            elif isinstance(loaded, pd.DataFrame) and loaded.shape == (1, len(loaded.columns)):
                loaded = loaded.iloc[0].to_dict()
            st.session_state["loaded_cfg"] = loaded
            st.success("Ayar yüklendi. Sol taraftaki alanları manuel olarak güncelleyebilirsiniz.")
        except Exception as e:
            st.error(f"Ayar dosyası okunamadı: {e}")

    st.divider()
    run = st.button("Verileri Getir", type="primary")

# Yüklenen ayarları UI'ya otomatik uygulamak yerine kullanıcıya bilgi verdik (yan etkiden kaçınmak için).

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

    for t in tickers:
        with st.container(border=True):
            st.markdown(f"### {t}")
            try:
                df = fetch_data(t, start_dt, end_dt, interval)
                if df.empty:
                    st.warning("Veri bulunamadı veya sembol geçersiz olabilir.")
                    continue
                all_dfs[t] = df

                # Grafik
                if "Mum (OHLC)" in what_to_show and {"Açılış", "Yüksek", "Düşük", "Kapanış"}.issubset(df.columns):
                    fig = go.Figure(data=[go.Candlestick(
                        x=df.index,
                        open=df["Açılış"],
                        high=df["Yüksek"],
                        low=df["Düşük"],
                        close=df["Kapanış"],
                        name="Mum"
                    )])
                    fig.update_layout(height=400, margin=dict(l=0, r=0, t=20, b=0))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    # Çizgi grafikleri bir arada göstermek için
                    fig = go.Figure()
                    for col in [c for c in ["Kapanış", "Düzeltilmiş Kapanış", "Hacim"] if c in what_to_show and c in df.columns]:
                        fig.add_trace(go.Scatter(x=df.index, y=df[col], mode="lines", name=col))
                    fig.update_layout(height=360, margin=dict(l=0, r=0, t=20, b=0))
                    if len(fig.data) > 0:
                        st.plotly_chart(fig, use_container_width=True)

                with st.expander("Tabloyu göster"):
                    st.dataframe(df)

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

    # Birleşik istatistik tablosu
    if stats_list:
        st.markdown("### Birleşik İstatistikler")
        combined = pd.concat(stats_list, ignore_index=True)
        st.dataframe(combined)

    # Excel dışa aktarım
    if all_dfs:
        st.markdown("### Excel'e Aktar")
        fname = st.text_input("Dosya adı", value="borsa_veri.xlsx")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            # Her sembol için ayrı sayfa
            for sym, df in all_dfs.items():
                # Excel sayfa adlarında uygunsuz karakterleri düzeltelim
                sheet = sym[:31].replace("/", "-")
                df.to_excel(writer, sheet_name=sheet)
            # Özet istatistikler sayfası
            if stats_list:
                combined.to_excel(writer, sheet_name="Özet")
            writer.close()
        st.download_button("Excel indir", data=buffer.getvalue(), file_name=fname, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Alt bilgi
st.caption("Veriler Yahoo Finance üzerinden sağlanır ve gecikmeli olabilir. Yatırım kararları için tek kaynak olarak kullanmayın.")
