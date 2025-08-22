import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

st.set_page_config(page_title="Borsa Takip", layout="wide")

st.title("Borsa Takip Uygulaması")

# Şirket ismi arama kutusu
company_input = st.text_input("Şirket ismi veya sembolü giriniz (örn: AAPL, MSFT, THYAO):", value="AAPL")

# Tarih aralığı seçici
today = datetime.today()
default_start = today - timedelta(days=30)
start_date = st.date_input("Başlangıç tarihi", default_start)
end_date = st.date_input("Bitiş tarihi", today)

if company_input:
    # Verileri çek
    try:
        df = yf.download(company_input, start=start_date, end=end_date)
        if not df.empty:
            st.subheader(f"{company_input} için {start_date} - {end_date} tarihleri arası veri")
            st.dataframe(df)
            
            # Excel indirme butonu
            csv = df.to_csv().encode('utf-8')
            st.download_button(
                label="Veriyi Excel olarak indir",
                data=csv,
                file_name=f'{company_input}_{start_date}_{end_date}.csv',
                mime='text/csv'
            )
        else:
            st.warning("Girilen şirket için seçilen tarihlerde veri bulunamadı.")
    except Exception as e:
        st.error(f"Veri çekilirken hata oluştu: {e}")
else:
    st.info("Lütfen bir şirket ismi/sembolü girin.")

st.markdown("---")
st.write("Bu uygulama ile bir şirket ve tarih aralığı seçerek tablodan verileri inceleyebilir veya Excel olarak indirebilirsiniz.")
