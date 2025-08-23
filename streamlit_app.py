# streamlit_app.py
import time
import requests
import pandas as pd
import streamlit as st
import yfinance as yf

# ==============================
# AYARLAR
# ==============================
FINNHUB_API_KEY = "d2kqkchr01qs23a3e2t0d2kqkchr01qs23a3e2tg"  # senin verdiğin anahtar

# ==============================
# YARDIMCI FONKSİYONLAR
# ==============================
def is_symbol_like(text: str) -> bool:
    """Kullanıcının girdiğinin sembole benzer olup olmadığını kaba şekilde anlar."""
    t = (text or "").strip()
    if not t:
        return False
    # AAPL, ASELS.IS, BMW.DE, BTC-USD gibi formatları yakalar
    return t.isupper() or "." in t or "-" in t or ":" in t

def search_symbols_finnhub(query: str):
    """Finnhub symbol search (isimden sembol)."""
    try:
        url = "https://finnhub.io/api/v1/search"
        params = {"q": query.strip(), "token": FINNHUB_API_KEY}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json() or {}
        return data.get("result", []) or []
    except Exception as e:
        st.warning(f"Finnhub arama hatası: {e}")
        return []

def get_overview_yf(symbol: str) -> dict:
    """Son fiyat, değişim %, para birimi, borsa adı."""
    out = {"last": None, "change": None, "change_pct": None, "currency": "", "exchange": ""}
    try:
        tk = yf.Ticker(symbol)
        # Hızlı bilgiler
        try:
            fi = tk.fast_info  # dict benzeri
            out["currency"] = (fi.get("currency") if isinstance(fi, dict) else getattr(fi, "currency", "")) or ""
            out["exchange"] = (fi.get("exchange") if isinstance(fi, dict) else getattr(fi, "exchange", "")) or ""
            last_fast = (fi.get("last_price") if isinstance(fi, dict) else getattr(fi, "last_price", None))
            if last_fast is not None:
                out["last"] = float(last_fast)
        except Exception:
            pass

        # Değişim hesabı için son 2 kapanış
        try:
            h = tk.history(period="5d", interval="1d", auto_adjust=False)
            if not h.empty:
                last = float(h["Close"].iloc[-1])
                out["last"] = last
                if len(h) > 1:
                    prev = float(h["Close"].iloc[-2])
                    out["change"] = last - prev
                    if prev:
                        out["change_pct"] = (out["change"] / prev) * 100.0
        except Exception:
            pass
    except Exception as e:
        st.error(f"{symbol} özet hatası: {e}")
    return out

def get_monthly_history(symbol: str, period_key: str = "1y") -> pd.DataFrame:
    """Aylık kapanış datası."""
    per = {"1y": "1y", "3y": "3y", "5y": "5y", "max": "max"}.get(period_key, "1y")
    df = yf.download(symbol, period=per, interval="1mo", auto_adjust=False, progress=False)
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame()

# ==============================
# STREAMLIT UYGULAMA
# ==============================
st.set_page_config(page_title="📈 Küresel Sembol Arama", page_icon="🌍", layout="wide")
st.title("🌍 Küresel Sembol Arama — Aylık Görünüm")

# Session state başlangıçları
if "search_results" not in st.session_state:
    st.session_state.search_results = []  # [{symbol, description, type}]
if "selected_symbols" not in st.session_state:
    st.session_state.selected_symbols = []  # çoklu seçim listesi

# ------------------ Sol Panel: Arama ------------------
st.sidebar.header("Arama")
with st.sidebar.form("search_form"):
    query = st.text_input("Şirket adı veya sembol yazın (örn: ASELSAN, APPLE, AAPL, ASELS.IS)")
    submit = st.form_submit_button("Ara")

# Arama tetiklendiğinde
if submit:
    q = (query or "").strip()
    if not q:
        st.warning("Bir şey yazın.")
    else:
        # Sembol gibi görünüyorsa doğrudan tek sonuç olarak listele
        if is_symbol_like(q):
            st.session_state.search_results = [{"symbol": q, "description": "Direct input", "type": "symbol"}]
        else:
            # Finnhub araması
            hits = search_symbols_finnhub(q)
            # Basit normalize
            st.session_state.search_results = [
                {
                    "symbol": item.get("symbol", ""),
                    "description": item.get("description", ""),
                    "type": item.get("type", ""),
                }
                for item in hits if item.get("symbol")
            ]

# ------------------ Ana Alan: Eşleşenler + Seçim ------------------
if st.session_state.search_results:
    st.subheader("🔍 Eşleşen Semboller (tik ile çoklu seç)")
    # Checkbox'lar – anahtarlar sabit olsun ki seçimler korunabilsin
    for row in st.session_state.search_results:
        sym = row["symbol"]
        desc = row["description"]
        chk_key = f"chk_{sym}"
        # Checkbox göster
        st.checkbox(f"{sym} — {desc}", key=chk_key, value=False)

    cols = st.columns([1, 1, 4])
    with cols[0]:
        if st.button("Seçilenleri Ekle"):
            added = 0
            for row in st.session_state.search_results:
                sym = row["symbol"]
                chk_key = f"chk_{sym}"
                if st.session_state.get(chk_key):
                    if sym not in st.session_state.selected_symbols:
                        st.session_state.selected_symbols.append(sym)
                        added += 1
            if added:
                st.success(f"{added} sembol eklendi.")
            else:
                st.info("Herhangi bir seçim yapılmadı.")
    with cols[1]:
        if st.button("Seçimi Temizle"):
            # Checkbox’ları sıfırla
            for row in st.session_state.search_results:
                st.session_state[f"chk_{row['symbol']}"] = False
            st.info("Seçimler temizlendi.")

# ------------------ Seçilenler ve Veri Gösterimi ------------------
st.markdown("---")
st.subheader("✅ Seçilen Semboller")
if st.session_state.selected_symbols:
    st.write(", ".join(st.session_state.selected_symbols))
else:
    st.info("Henüz sembol seçmediniz.")

st.markdown("### Görünüm")
period = st.radio("Dönem (Aylık)", ["1y", "3y", "5y", "max"], horizontal=True, index=0)

if st.button("Verileri Getir", type="primary", use_container_width=False):
    if not st.session_state.selected_symbols:
        st.warning("Önce sembol seçin (tik atıp 'Seçilenleri Ekle'ye basın).")
    else:
        for sym in st.session_state.selected_symbols:
            with st.spinner(f"{sym} verileri getiriliyor..."):
                ov = get_overview_yf(sym)
                hist = get_monthly_history(sym, period)

            st.markdown(f"#### {sym}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Son Fiyat", f"{ov['last']:.4f}" if ov["last"] is not None else "—")
            if ov["change"] is not None and ov["change_pct"] is not None:
                m2.metric("Değişim", f"{ov['change']:+.4f} ({ov['change_pct']:+.2f}%)")
            else:
                m2.metric("Değişim", "—")
            m3.metric("Para Birimi", ov.get("currency") or "—")
            m4.metric("Borsa", ov.get("exchange") or "—")

            if hist is not None and not hist.empty:
                # MultiIndex kolonları düzleştir
                if isinstance(hist.columns, pd.MultiIndex):
                    hist.columns = ["_".join([c for c in col if c]) for col in hist.columns.values]
                close_col = "Close" if "Close" in hist.columns else hist.columns[-1]
                st.line_chart(hist[close_col].dropna())
            else:
                st.warning("Aylık veri bulunamadı.")
