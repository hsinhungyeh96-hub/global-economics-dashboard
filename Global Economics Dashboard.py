import streamlit as st
import pandas as pd
import datetime
import requests
import plotly.express as px
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

# =========================================================
# 🌍 基礎設定
# =========================================================
st.set_page_config(
    page_title="Global Macro Dashboard Pro",
    layout="wide"
)

st.title("🌐 全球 Macro Intelligence Dashboard")
st.caption("資料來源：FRED + Yahoo Finance + Google News RSS")

st.write(
    f"⏰ 更新時間："
    f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)

FRED_API_KEY = st.secrets["FRED_API_KEY"]

# =========================================================
# 🌎 全球主要經濟體
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

    "GBR": {
        "名稱": "英國",
        "洲": "歐洲",
        "貨幣": "GBP",
        "CPI": "GBRCPIALLMINMEI",
        "政策利率": "IRSTCB01GBM156N",
        "10Y": "IRLTLT01GBM156N",
        "股市": "^FTSE",
        "新聞": "United Kingdom economy"
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

    "CHN": {
        "名稱": "中國",
        "洲": "亞洲",
        "貨幣": "CNY",
        "CPI": "CHNCPIALLMINMEI",
        "政策利率": "IRSTCB01CNM156N",
        "10Y": "IRLTLT01CNM156N",
        "股市": "000001.SS",
        "新聞": "China economy"
    },

    "IND": {
        "名稱": "印度",
        "洲": "亞洲",
        "貨幣": "INR",
        "CPI": "INDCPIALLMINMEI",
        "政策利率": "IRSTCB01INM156N",
        "10Y": "INDIRLTLT01STM",
        "股市": "^BSESN",
        "新聞": "India economy"
    },

    "BRA": {
        "名稱": "巴西",
        "洲": "南美",
        "貨幣": "BRL",
        "CPI": "BRACPIALLMINMEI",
        "政策利率": "IRSTCB01BRM156N",
        "10Y": "IRLTLT01BRM156N",
        "股市": "^BVSP",
        "新聞": "Brazil economy"
    },

    "ZAF": {
        "名稱": "南非",
        "洲": "非洲",
        "貨幣": "ZAR",
        "CPI": "ZAFCPIALLMINMEI",
        "政策利率": "IRSTCB01ZAM156N",
        "10Y": "IRLTLT01ZAM156N",
        "股市": "J200.JO",
        "新聞": "South Africa economy"
    },

    "TWN": {
        "名稱": "台灣",
        "洲": "亞洲",
        "貨幣": "TWD",
        "CPI": "TWNCPIALLMINMEI",
        "政策利率": "IRSTCB01TWM156N",
        "10Y": "IRLTLT01TWM156N",
        "股市": "^TWII",
        "新聞": "Taiwan economy"
    }
}

# =========================================================
# 🌐 Requests Session
# =========================================================
session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0"
})

# =========================================================
# 📦 FRED 抓資料
# =========================================================
@st.cache_data(ttl=1800)
def fetch_fred_series(series_id, limit=24):

    try:

        url = (
            "https://api.stlouisfed.org/"
            "fred/series/observations"
        )

        params = {
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit
        }

        response = session.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        observations = data.get(
            "observations",
            []
        )

        cleaned = []

        for obs in observations:

            val = obs.get("value")

            if val != ".":
                cleaned.append(float(val))

        return cleaned

    except:
        return []

# =========================================================
# 📈 CPI YoY
# =========================================================
def calculate_yoy(values):

    if len(values) < 13:
        return None

    try:

        latest = values[0]
        last_year = values[12]

        return round(
            ((latest / last_year) - 1) * 100,
            2
        )

    except:
        return None

# =========================================================
# 💱 匯率
# =========================================================
@st.cache_data(ttl=1800)
def get_fx_rate(currency):

    if currency == "USD":
        return 1.0

    try:

        url = (
            f"https://api.frankfurter.app/latest?"
            f"from=USD&to={currency}"
        )

        response = session.get(
            url,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        return round(
            data["rates"][currency],
            4
        )

    except:
        return None

# =========================================================
# 📈 股票市場（Yahoo Finance）
# =========================================================
@st.cache_data(ttl=1800)
def get_stock_price(symbol):

    try:

        url = (
            f"https://query1.finance.yahoo.com/"
            f"v8/finance/chart/{symbol}"
        )

        response = session.get(
            url,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        result = data["chart"]["result"][0]

        return round(
            result["meta"]["regularMarketPrice"],
            2
        )

    except:
        return None

# =========================================================
# 📰 新聞
# =========================================================
@st.cache_data(ttl=1800)
def get_news(keyword):

    try:

        url = (
            f"https://news.google.com/rss/search?"
            f"q={keyword}&hl=en-US&gl=US&ceid=US:en"
        )

        response = session.get(
            url,
            timeout=10
        )

        response.raise_for_status()

        root = ET.fromstring(
            response.content
        )

        news = []

        for item in root.findall(".//item")[:5]:

            news.append({
                "title": item.find("title").text,
                "link": item.find("link").text,
                "date": item.find("pubDate").text[:16]
            })

        return news

    except:
        return []

# =========================================================
# 🌍 單一國家資料
# =========================================================
def fetch_country_data(code, info):

    cpi_data = fetch_fred_series(
        info["CPI"],
        24
    )

    rate_data = fetch_fred_series(
        info["政策利率"],
        1
    )

    bond_data = fetch_fred_series(
        info["10Y"],
        1
    )

    stock = get_stock_price(
        info["股市"]
    )

    fx = get_fx_rate(
        info["貨幣"]
    )

    return {

        "國家代碼": code,

        "國家": info["名稱"],

        "洲": info["洲"],

        "貨幣": info["貨幣"],

        "CPI YoY (%)":
            calculate_yoy(cpi_data),

        "政策利率 (%)":
            rate_data[0]
            if rate_data else None,

        "10Y Bond Yield (%)":
            bond_data[0]
            if bond_data else None,

        "USD FX":
            fx,

        "股票市場":
            stock
    }

# =========================================================
# ⚡ 平行抓取
# =========================================================
@st.cache_data(ttl=1800)
def build_dataset():

    rows = []

    with ThreadPoolExecutor(
        max_workers=10
    ) as executor:

        futures = []

        for code, info in COUNTRY_CONFIG.items():

            futures.append(

                executor.submit(
                    fetch_country_data,
                    code,
                    info
                )
            )

        for future in futures:

            rows.append(
                future.result()
            )

    df = pd.DataFrame(rows)

    numeric_cols = [

        "CPI YoY (%)",

        "政策利率 (%)",

        "10Y Bond Yield (%)",

        "USD FX",

        "股票市場"
    ]

    for col in numeric_cols:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        ).round(2)

    return df

# =========================================================
# 🌍 建立資料
# =========================================================
with st.spinner(
    "🌐 全球 Macro Data 同步中..."
):

    df = build_dataset()

# =========================================================
# 🎛️ Sidebar
# =========================================================
st.sidebar.header("⚙️ 控制台")

continent = st.sidebar.selectbox(

    "選擇洲別",

    [
        "全部",
        "北美",
        "歐洲",
        "亞洲",
        "南美",
        "非洲"
    ]
)

metric = st.sidebar.selectbox(

    "選擇地圖指標",

    [
        "CPI YoY (%)",
        "政策利率 (%)",
        "10Y Bond Yield (%)",
        "USD FX"
    ]
)

# =========================================================
# 🌍 Filter
# =========================================================
if continent != "全部":

    filtered_df = df[
        df["洲"] == continent
    ]

else:

    filtered_df = df

# =========================================================
# 📊 Data Table
# =========================================================
st.header("📊 全球總體經濟總覽")

st.dataframe(

    filtered_df,

    hide_index=True,

    use_container_width=True
)

# =========================================================
# 🗺️ 地圖
# =========================================================
st.header("🗺️ 全球 Macro Heatmap")

fig = px.choropleth(

    filtered_df,

    locations="國家代碼",

    color=metric,

    hover_name="國家",

    projection="natural earth",

    color_continuous_scale="Blues"
)

fig.update_layout(

    margin={
        "r": 0,
        "t": 30,
        "l": 0,
        "b": 0
    }
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# =========================================================
# 📰 新聞
# =========================================================
st.header("📰 全球財經新聞")

tabs = st.tabs([
    info["名稱"]
    for info in COUNTRY_CONFIG.values()
])

for tab, (_, info) in zip(
    tabs,
    COUNTRY_CONFIG.items()
):

    with tab:

        news = get_news(
            info["新聞"]
        )

        if not news:

            st.warning(
                "目前無新聞"
            )

        else:

            for item in news:

                st.markdown(
                    f"""
### [{item['title']}]({item['link']})

⏱️ {item['date']}
"""
                )

# =========================================================
# 📌 Footer
# =========================================================
st.markdown("---")

st.caption(
    "Global Macro Intelligence Dashboard | "
    "Powered by Streamlit + FRED"
)
