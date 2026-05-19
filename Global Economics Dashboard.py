import streamlit as st
import pandas as pd
import datetime
import requests
import plotly.express as px
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

# =========================================================
# 🌍 基本設定
# =========================================================
st.set_page_config(
    page_title="Global Macro Dashboard Pro",
    layout="wide"
)

st.title("🌐 Global Macro Intelligence Dashboard")
st.caption("FRED + FX + Stock + Manual Override Layer")

st.write(
    f"⏰ 更新時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)

FRED_API_KEY = st.secrets.get("FRED_API_KEY", "")

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

# =========================================================
# 🌎 國家設定
# =========================================================
COUNTRY_CONFIG = {
    "USA": {
        "名稱": "美國",
        "洲": "北美",
        "貨幣": "USD",
        "CPI": "CPIAUCSL",
        "政策利率": "FEDFUNDS",
        "10Y": "DGS10",
        "股市": "^GSPC",
        "新聞": "United States economy"
    },
    "DEU": {
        "名稱": "德國",
        "洲": "歐洲",
        "貨幣": "EUR",
        "CPI": "CP0000EZ19M086NEST",
        "政策利率": "ECBDFR",
        "10Y": "IRLTLT01DEM156N",
        "股市": "^GDAXI",
        "新聞": "Germany economy"
    },
    "JPN": {
        "名稱": "日本",
        "洲": "亞洲",
        "貨幣": "JPY",
        "CPI": "JPNCPIALLMINMEI",
        "政策利率": "IRSTCB01JPM156N",
        "10Y": "IRLTLT01JPM156N",
        "股市": "^N225",
        "新聞": "Japan economy"
    },
    "TWN": {
        "名稱": "台灣",
        "洲": "亞洲",
        "貨幣": "TWD",
        "CPI": "TWNCPIALLMINMEI",
        "政策利率": None,
        "10Y": None,
        "股市": "^TWII",
        "新聞": "Taiwan economy"
    }
}

# =========================================================
# 🔧 手動 fallback（核心）
# =========================================================
def get_or_manual(key, label):

    if key not in st.session_state:
        st.session_state[key] = None

    value = st.session_state[key]

    if value is None:

        st.warning(f"{label} 無法取得數據，請手動輸入")

        st.session_state[key] = st.number_input(
            label,
            step=0.1,
            value=0.0,
            key=key
        )

    return st.session_state[key]

# =========================================================
# 📦 FRED
# =========================================================
@st.cache_data(ttl=1800)
def fetch_fred_series(series_id, limit=24):

    if series_id is None:
        return []

    try:
        url = "https://api.stlouisfed.org/fred/series/observations"

        params = {
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit
        }

        r = session.get(url, params=params, timeout=10)
        r.raise_for_status()

        data = r.json()

        values = []

        for i in data.get("observations", []):
            v = i.get("value")
            if v != ".":
                values.append(float(v))

        return values

    except:
        return []

# =========================================================
# 📈 CPI YoY
# =========================================================
def calc_yoy(values):

    if len(values) < 13:
        return None

    try:
        return round(((values[0] / values[12]) - 1) * 100, 2)
    except:
        return None

# =========================================================
# 💱 FX
# =========================================================
def get_fx(currency):

    if currency == "USD":
        return 1.0

    try:
        url = f"https://api.frankfurter.app/latest?from=USD&to={currency}"
        r = session.get(url, timeout=10)
        r.raise_for_status()
        return round(r.json()["rates"][currency], 4)

    except:
        return None

# =========================================================
# 📈 股票
# =========================================================
def get_stock(symbol):

    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        r = session.get(url, timeout=10)
        r.raise_for_status()
        return round(
            r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"],
            2
        )
    except:
        return None

# =========================================================
# 🌍 單國資料
# =========================================================
def fetch_country(code, info):

    cpi_raw = fetch_fred_series(info["CPI"], 24)
    rate_raw = fetch_fred_series(info["政策利率"], 1)
    bond_raw = fetch_fred_series(info["10Y"], 1)

    cpi = calc_yoy(cpi_raw)

    rate = rate_raw[0] if rate_raw else None
    bond = bond_raw[0] if bond_raw else None

    fx = get_fx(info["貨幣"])
    stock = get_stock(info["股市"])

    # ================================
    # 🔥 fallback layer
    # ================================

    cpi = cpi if cpi is not None else get_or_manual(
        f"{code}_cpi",
        f"{info['名稱']} CPI YoY"
    )

    rate = rate if rate is not None else get_or_manual(
        f"{code}_rate",
        f"{info['名稱']} Policy Rate"
    )

    bond = bond if bond is not None else get_or_manual(
        f"{code}_bond",
        f"{info['名稱']} 10Y Bond"
    )

    return {
        "國家": info["名稱"],
        "洲": info["洲"],
        "CPI YoY (%)": cpi,
        "政策利率 (%)": rate,
        "10Y Bond (%)": bond,
        "FX": fx,
        "股票": stock
    }

# =========================================================
# ⚡ 全域資料
# =========================================================
@st.cache_data(ttl=1800)
def build():

    rows = []

    with ThreadPoolExecutor(max_workers=8) as ex:

        futures = [
            ex.submit(fetch_country, k, v)
            for k, v in COUNTRY_CONFIG.items()
        ]

        for f in futures:
            rows.append(f.result())

    return pd.DataFrame(rows)

# =========================================================
# 📊 RUN
# =========================================================
with st.spinner("Loading macro data..."):
    df = build()

st.header("📊 Global Macro Overview")
st.dataframe(df, use_container_width=True)

# =========================================================
# 🗺️ MAP
# =========================================================
metric = st.selectbox(
    "Indicator",
    ["CPI YoY (%)", "政策利率 (%)", "10Y Bond (%)", "FX"]
)

fig = px.choropleth(
    df,
    locations="國家",
    color=metric,
    hover_name="國家",
    projection="natural earth",
    color_continuous_scale="Blues"
)

st.plotly_chart(fig, use_container_width=True)
