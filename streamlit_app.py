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
BING_API_KEY = st.secrets.get("bing_key", "")  # streamlit secrets ile veya direkt olarak yazabilirsiniz
OPENAI_API_KEY = st.secrets.get("openai_key", "")

# -----------------------------
# Yardımcı Fonksiyonlar
# -----------------------------

def parse_tickers(raw: str) -> List[str]:
    parts = [p.strip().upper() for p in raw.replace("\n", ",").replace(";", ",").split(",")]
    return [p for p in parts if p]

@st.cache_data(show_spinner=False, ttl=60 * 60)
def fetch_data(ticker: str, start_dt: date, end_dt: date, interval: str) -> pd.DataFrame:
    df = yf.download(ticker, start=start_dt, end=end_dt + timedelta(days=1), interval=interval, progress=False, auto_adjust=False)
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

def search_symbols(query: str) -> List[Dict]:
    # Yahoo Finance autocomplete endpoint
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        items = data.get("quotes", [])
        results = []
        for item in items:
            results.append({
                "symbol": item.get("symbol"),
                "name": item.get("shortname", item.get("longname", "")),
                "exchange": item.get("exchange", ""),
                "score": item.get("score", 0),
            })
        return results
    except Exception:
        return []

def get_news_bing(query: str, startdate: str, enddate: str, market="en-US", count=5) -> List[Dict]:
    # Bing News Search API
    if not BING_API_KEY:
        return []
    headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
    params = {
        "q": query,
        "count": count,
        "mkt": market,
        "freshness": "week",  # son haftanın haberleri
        "sortBy": "Date"
    }
    url = "https://api.bing.microsoft.com/v7.0/news/search"
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        results = resp.json().get("value", [])
        news = []
        for item in results:
            news.append({
                "title": item.get("name"),
                "desc": item.get("description"),
                "url": item.get("url"),
                "date": item.get("datePublished"),
                "source": item.get("provider", [{}])[0].get("name", ""),
            })
        return news
    except Exception:
        return []

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
# UI
# -----------------------------
st.set_page_config(page_title="Global Borsa Takibi", page_icon="📈", layout="wide")
st.title("📈 Global Borsa Takip Uygulaması")
st.caption("Yahoo Finance verileri, haberler ve ChatGPT ile istatistik tartışma.")

with st.sidebar:
    st.header("Sembol Arama")
    search_text = st.text_input("Şirket adı veya sembol ara", value="", help="Şirket adı veya sembol girin (örn: Apple, ASELS)")
    if search_text:
        results = search_symbols(search_text)
        if results:
            st.markdown("### Arama Sonuçları")
            for res in results[:10]:
                st.write(f"**{res['symbol']}** - {res['name']} ({res['exchange']})")
        else:
            st.info("Sonuç bulunamadı.")

    tickers_str = st.text_area(
        "İzlenecek Semboller (virgül / satır ile ayırın)",
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

            # 2. Haberler
            st.markdown("**İlgili Haberler**")
            try:
                news = get_news_bing(t, str(start_dt), str(end_dt))
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
            for sym, df in all_dfs.items():
                sheet = sym[:31].replace("/", "-")
                df.to_excel(writer, sheet_name=sheet)
            if stats_list:
                combined.to_excel(writer, sheet_name="Özet")
            writer.close()
        st.download_button("Excel indir", data=buffer.getvalue(), file_name=fname, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Alt bilgi
st.caption("Veriler Yahoo Finance ve Bing News üzerinden sağlanır ve gecikmeli olabilir. Yatırım kararları için tek kaynak olarak kullanmayın. ChatGPT ile tartışmalar öneridir, yatırım tavsiyesi değildir.")
