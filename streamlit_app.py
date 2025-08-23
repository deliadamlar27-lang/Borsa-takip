import streamlit as st
import pandas as pd
from difflib import get_close_matches

# Örnek sembol/firma listesi dosyası
SYMBOL_FILE = "symbols.csv"

def load_symbols(filepath=SYMBOL_FILE):
    try:
        df = pd.read_csv(filepath)
        # Beklenen kolonlar: symbol, company, exchange
        return df
    except Exception as e:
        st.error(f"Kısaltma/Firma listesi yüklenemedi: {e}")
        return pd.DataFrame(columns=["symbol", "company", "exchange"])

def fuzzy_search(df, query, n=10, cutoff=0.6):
    # Sembol ve firma adında yakın eşleşenleri bul
    symbols = df["symbol"].tolist()
    companies = df["company"].tolist()
    symbol_matches = get_close_matches(query.upper(), symbols, n=n, cutoff=cutoff)
    company_matches = get_close_matches(query.lower(), [c.lower() for c in companies], n=n, cutoff=cutoff)
    matched_rows = pd.DataFrame()
    if symbol_matches:
        matched_rows = pd.concat([matched_rows, df[df["symbol"].isin(symbol_matches)]])
    if company_matches:
        matched_rows = pd.concat([matched_rows, df[df["company"].str.lower().isin(company_matches)]])
    # Tekrarları sil
    return matched_rows.drop_duplicates().reset_index(drop=True)

st.set_page_config(page_title="Kısaltma/Firma Arama & Takip", page_icon="🔎", layout="wide")
st.title("🔎 Kısaltma ve Firma Arama - Takip Listesi")

with st.sidebar:
    st.subheader("Arama Yap")
    query = st.text_input("Aramak istediğiniz firma veya kısaltma (örn: aselsan, ASELS, apple, AAPL)")
    st.markdown("---")
    st.subheader("Takip Listeniz")
    if "selected" not in st.session_state:
        st.session_state.selected = []
    # Takipteki sembolleri göster
    if st.session_state.selected:
        takip_df = load_symbols()
        takip_rows = takip_df[takip_df["symbol"].isin(st.session_state.selected)]
        st.dataframe(takip_rows, use_container_width=True)
        # Çıkar tuşu
        remove_symbol = st.selectbox("Takip listesinden çıkar:", [""] + st.session_state.selected)
        if remove_symbol and st.button("Çıkar"):
            st.session_state.selected.remove(remove_symbol)
    else:
        st.info("Henüz sembol eklemediniz.")

symbols_df = load_symbols()

st.subheader("Tüm Semboller Tablosu")
st.dataframe(symbols_df, use_container_width=True)

st.subheader("Arama Sonuçları (Yakın Eşleşmeler dahil)")
if query:
    results_df = fuzzy_search(symbols_df, query)
    if not results_df.empty:
        for idx, row in results_df.iterrows():
            cols = st.columns([4,1])
            with cols[0]:
                st.write(f"**{row['symbol']}** | {row['company']} | {row['exchange']}")
            with cols[1]:
                if row['symbol'] in st.session_state.selected:
                    st.button("Takipte", key=f"exist_{row['symbol']}_{idx}", disabled=True)
                else:
                    if st.button("Takibe Ekle", key=f"add_{row['symbol']}_{idx}"):
                        st.session_state.selected.append(row['symbol'])
    else:
        st.warning("Aramaya uygun kısaltma veya firma bulunamadı.")
else:
    st.info("Arama kutusuna firma veya kısaltma yazın.")

st.caption(
    "Bu uygulamada kısaltma (sembol) ile firma adı yan yana görünür ve arama yaptığınızda en yakın eşleşmeler önerilir. Takip listenizi kolayca oluşturabilirsiniz."
)
