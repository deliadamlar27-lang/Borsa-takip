# pages/01_Sembol_Evreni.py
import os
import pandas as pd
import streamlit as st
from providers import (
    fetch_us_listings, fetch_eodhd_listings, fetch_fmp_listings,
    merge_user_csv, normalize, EXPECTED_COLS
)

SYMBOL_FILE = "symbols.csv"

st.set_page_config(page_title="Sembol Evreni Oluştur", page_icon="🌍", layout="wide")
st.title("🌍 Sembol Evreni Oluştur / Güncelle")

st.markdown("""
Bu sayfa **tek tıkla** `symbols.csv` üretir:
- **Ücretsiz**: ABD borsaları (NASDAQ/NYSE/AMEX)
- **Opsiyonel**: EODHD / FMP anahtarıyla **global** kapsam
- **Ek olarak**: Kendi CSV’ni yükleyip birleştirebilirsin (ör. BIST resmi listesi)
""")

with st.sidebar:
    st.subheader("Kaynaklar")
    use_us = st.checkbox("ABD (ücretsiz, Nasdaq Trader)", value=True)
    use_eodhd = st.checkbox("EODHD (global, API key gerekir)", value=False)
    use_fmp = st.checkbox("FMP (geniş, API key gerekir)", value=False)

    st.markdown("---")
    eodhd_key = st.text_input("EODHD_API_KEY", type="password")
    fmp_key = st.text_input("FMP_API_KEY", type="password")
    eodhd_exchanges = st.text_input("EODHD Borsa Kodları (opsiyonel, virgüllü)", placeholder="BIST,US,OTC,TSX,XETRA,HKEX...")

    st.markdown("---")
    user_csv = st.file_uploader("Kendi CSV dosyan (symbol,company,exchange)", type=["csv"])

col1, col2 = st.columns([1,1], gap="large")

with col1:
    if st.button("🚀 Evreni Oluştur / Güncelle"):
        frames = []

        if use_us:
            with st.spinner("ABD listeleri çekiliyor..."):
                try:
                    frames.append(fetch_us_listings())
                except Exception as e:
                    st.error(f"ABD listeleri alınamadı: {e}")

        if use_eodhd and eodhd_key:
            with st.spinner("EODHD (global) listeleri çekiliyor... Bu biraz sürebilir."):
                try:
                    exchs = [x.strip() for x in eodhd_exchanges.split(",") if x.strip()] if eodhd_exchanges else None
                    frames.append(fetch_eodhd_listings(eodhd_key, exchanges=exchs))
                except Exception as e:
                    st.error(f"EODHD hata: {e}")

        if use_fmp and fmp_key:
            with st.spinner("FMP listesi çekiliyor..."):
                try:
                    frames.append(fetch_fmp_listings(fmp_key))
                except Exception as e:
                    st.error(f"FMP hata: {e}")

        if not frames and not user_csv:
            st.warning("Hiç kaynak seçmediniz. En az birini işaretleyin veya CSV yükleyin.")
        else:
            base = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=EXPECTED_COLS)
            # Kullanıcı CSV'yi birleştir
            if user_csv is not None:
                try:
                    import io
                    user_df = pd.read_csv(io.BytesIO(user_csv.read()), dtype=str)
                    user_df = normalize(user_df)
                    base = pd.concat([base, user_df], ignore_index=True)
                except Exception as e:
                    st.error(f"Kullanıcı CSV okunamadı: {e}")

            # Temizlik
            base = base.drop_duplicates(subset=["symbol","exchange"]).sort_values(["exchange","symbol"]).reset_index(drop=True)

            # Kaydet
            base.to_csv(SYMBOL_FILE, index=False)
            st.success(f"`{SYMBOL_FILE}` kaydedildi. Toplam kayıt: {len(base):,}")
            st.dataframe(base.head(200), use_container_width=True)

with col2:
    st.subheader("Mevcut symbols.csv")
    if os.path.exists(SYMBOL_FILE):
        try:
            df = pd.read_csv(SYMBOL_FILE, dtype=str)
            st.write(f"Toplam: **{len(df):,}** kayıt")
            st.dataframe(df.head(200), use_container_width=True)
        except Exception as e:
            st.error(f"symbols.csv okunamadı: {e}")
    else:
        st.info("Henüz symbols.csv oluşturulmamış.")
