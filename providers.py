# providers.py
import os
import io
import zipfile
import requests
import pandas as pd

EXPECTED_COLS = ["symbol", "company", "exchange"]

def normalize(df: pd.DataFrame) -> pd.DataFrame:
    # Kolonları normalize et ve zorunluları sağla
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    rename_map = {
        "ticker": "symbol", "name": "company", "market": "exchange",
        "companyname": "company", "securityname": "company",
        "symbol": "symbol", "exchange": "exchange"
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    for col in EXPECTED_COLS:
        if col not in df.columns:
            df[col] = ""
    df = df[EXPECTED_COLS].fillna("")
    # Boş sembol veya çok kısa semboller elensin
    df = df[df["symbol"].astype(str).str.len() >= 1]
    # Çiftleri temizle
    df = df.drop_duplicates(subset=["symbol","exchange"]).reset_index(drop=True)
    return df

# ------- ÜCRETSİZ: ABD (NASDAQ/NYSE/AMEX) - Nasdaq Trader ----------
def fetch_us_listings() -> pd.DataFrame:
    """
    NASDAQ Trader listeleri:
      - nasdaqlisted.txt (NASDAQ)
      - otherlisted.txt (NYSE, AMEX vb.)
    """
    base = "https://ftp.nasdaqtrader.com/dynamic/SymSymbolDirectory/"
    urls = {
        "NASDAQ": base + "nasdaqlisted.txt",
        "OTHER":  base + "otherlisted.txt",
    }
    frames = []
    for exch, url in urls.items():
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        # Dosyalar | pipe ayraçlı; son satırda "File Creation Time" var, atıyoruz
        df = pd.read_csv(io.StringIO(r.text), sep="|", dtype=str)
        df = df.iloc[:-1]  # son bilgi satırını at
        # Kolonlar: Symbol, Security Name, Exchange (otherlisted), Market Category (nasdaqlisted) vb.
        if "Symbol" in df.columns and "Security Name" in df.columns:
            df["symbol"] = df["Symbol"]
            df["company"] = df["Security Name"]
            if "Exchange" in df.columns:
                df["exchange"] = df["Exchange"]
            else:
                # NASDAQ dosyasında Exchange kolon yok; "NASDAQ" verelim
                df["exchange"] = "NASDAQ"
            frames.append(df[["symbol","company","exchange"]])
    out = pd.concat(frames, ignore_index=True)
    out["exchange"] = out["exchange"].replace({"N":"NYSE","A":"AMEX"})  # otherlisted’de kısaltmalar gelebilir
    return normalize(out)

# ------- OPSİYONEL: EODHD (neredeyse tüm dünyayı kapsar) ----------
def fetch_eodhd_listings(api_key: str, exchanges: list[str] | None = None) -> pd.DataFrame:
    """
    EOD Historical Data: https://eodhistoricaldata.com/
    - Ücretli plan gerekebilir.
    - exchanges=None ise tüm borsaları çekmeye çalışır (çok büyük veri).
    """
    if not api_key:
        raise ValueError("EODHD_API_KEY boş.")
    sess = requests.Session()
    # Borsa kodlarını çek
    r = sess.get("https://eodhistoricaldata.com/api/exchanges-list/?fmt=json&api_token="+api_key, timeout=60)
    r.raise_for_status()
    exch_df = pd.DataFrame(r.json())
    if exchanges:
        exch_df = exch_df[exch_df["Code"].isin(exchanges)]
    frames = []
    for code in exch_df["Code"].tolist():
        url = f"https://eodhistoricaldata.com/api/exchange-symbol-list/{code}?api_token={api_key}&fmt=json"
        rr = sess.get(url, timeout=120)
        if rr.status_code != 200:
            continue
        data = pd.DataFrame(rr.json())
        if data.empty or "Code" not in data.columns:
            continue
        data["symbol"] = data["Code"]
        data["company"] = data.get("Name", "")
        data["exchange"] = code
        frames.append(data[["symbol","company","exchange"]])
    if not frames:
        return pd.DataFrame(columns=EXPECTED_COLS)
    return normalize(pd.concat(frames, ignore_index=True))

# ------- OPSİYONEL: Financial Modeling Prep (geniş kapsam) -------
def fetch_fmp_listings(api_key: str) -> pd.DataFrame:
    """
    Financial Modeling Prep:
    - https://site.financialmodelingprep.com/developer/docs/
    - Ücretsiz katman sınırlı; global list için ücretli gerekir.
    """
    if not api_key:
        raise ValueError("FMP_API_KEY boş.")
    url = f"https://financialmodelingprep.com/api/v3/stock/list?apikey={api_key}"
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    df = pd.DataFrame(r.json())
    if df.empty:
        return pd.DataFrame(columns=EXPECTED_COLS)
    # Beklenen kolonlar: symbol, name, exchangeShortName
    df = df.rename(columns={"name":"company","exchangeShortName":"exchange"})
    return normalize(df[["symbol","company","exchange"]])

# ------- (İsteğe bağlı) Kullanıcı CSV birleştirme ----------
def merge_user_csv(user_csv_path: str, base_df: pd.DataFrame) -> pd.DataFrame:
    if not user_csv_path or not os.path.exists(user_csv_path):
        return base_df
    try:
        user_df = pd.read_csv(user_csv_path, dtype=str)
        user_df = normalize(user_df)
        out = pd.concat([base_df, user_df], ignore_index=True)
        out = out.drop_duplicates(subset=["symbol","exchange"]).reset_index(drop=True)
        return out
    except Exception:
        return base_df
