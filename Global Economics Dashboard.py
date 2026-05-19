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

st.title("🌐 全球總體經濟 Dashboard Pro")
st.caption("資料來源：FRED + Frankfurter FX + Google News RSS")

st.write(
    f"⏰ 最後更新時間： "
    f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)

# ⚠️ 練習可直接寫死，但正式專案建議用 secrets
FRED_API_KEY = st.secrets.get("FRED_API_KEY", "")

# =========================================================
# 🌎 全球主要經濟體設定
# =========================================================
COUNTRY_CONFIG = {

    # 北美
    "USA": {
        "名稱": "美國",
        "洲": "北美",
        "貨幣": "USD",
        "失業率": "UNRATE",
        "CPI": "CPIAUCSL",
        "GDP": "A191RL1Q225SBEA",
        "新聞": "United States economy"
    },

    "CAN": {
        "名稱": "加拿大",
        "洲": "北美",
        "貨幣": "CAD",
        "失業率": "LRUNTTTTCAM156S",
        "CPI": "CPALCY01CAM661N",
        "GDP": "CANRGDPQDSMEI",
        "新聞": "Canada economy"
    },

    "MEX": {
        "名稱": "墨西哥",
        "洲": "北美",
        "貨幣": "MXN",
        "失業率": "LRUNTTTTMXM156S",
        "CPI": "MEXCPIALLMINMEI",
        "GDP": "MEXRGDPQDSMEI",
        "新聞": "Mexico economy"
    },

    # 歐洲
    "DEU": {
        "名稱": "德國",
        "洲": "歐洲",
        "貨幣": "EUR",
        "失業率": "LRHUTTTTEM156S",
        "CPI": "CP0000EZ19M086NEST",
        "GDP": "CLVMEURSCAB1GQEA",
        "新聞": "Germany economy"
    },

    "FRA": {
        "名稱": "法國",
        "洲": "歐洲",
        "貨幣": "EUR",
        "失業率": "LRHUTTTTFRM156S",
        "CPI": "FRACPIALLMINMEI",
        "GDP": "FRARGDPQDSMEI",
        "新聞": "France economy"
    },

    "GBR": {
        "名稱": "英國",
        "洲": "歐洲",
        "貨幣": "GBP",
        "失業率": "LRHUTTTTGBM156S",
        "CPI": "GBRCPIALLMINMEI",
        "GDP": "GBRRGDPQDSMEI",
        "新聞": "United Kingdom economy"
    },

    "ITA": {
        "名稱": "義大利",
        "洲": "歐洲",
        "貨幣": "EUR",
        "失業率": "LRHUTTTTITM156S",
        "CPI": "ITACPIALLMINMEI",
        "GDP": "ITARGDPQDSMEI",
        "新聞": "Italy economy"
    },

    # 亞洲
    "CHN": {
        "名稱": "中國",
        "洲": "亞洲",
        "貨幣": "CNY",
        "失業率": "LRUN64TTCNQ156S",
        "CPI": "CHNCPIALLMINMEI",
        "GDP": "CHNRGDPNQDSMEI",
        "新聞": "China economy"
    },

    "JPN": {
        "名稱": "日本",
        "洲": "亞洲",
        "貨幣": "JPY",
        "失業率": "JPNURMQSDSMEI",
        "CPI": "JPNCPIALLMINMEI",
        "GDP": "JPNRGDPQDSMEI",
        "新聞": "Japan economy"
    },

    "KOR": {
        "名稱": "韓國",
        "洲": "亞洲",
        "貨幣": "KRW",
        "失業率": "LRUN64TTKRM156S",
        "CPI": "KORCPIALLMINMEI",
        "GDP": "KORRGDPQDSMEI",
        "新聞": "South Korea economy"
    },

    "IND": {
        "名稱": "印度",
        "洲": "亞洲",
        "貨幣": "INR",
        "失業率": "INDUCEMPSLM",
        "CPI": "INDCPIALLMINMEI",
        "GDP": "INDRGDPQDSMEI",
        "新聞": "India economy"
    },

    "TWN": {
        "名稱": "台灣",
        "洲": "亞洲",
        "貨幣": "TWD",
        "失業率": "TWNURM",
        "CPI": "TWNCPIALLMINMEI",
        "GDP": "TWNRGDPQDSMEI",
        "新聞": "Taiwan economy"
    },

    # 南美
    "BRA": {
        "名稱": "巴西",
        "洲": "南美",
        "貨幣": "BRL",
        "失業率": "LRUN64TTBRM156S",
        "CPI": "BRACPIALLMINMEI",
        "GDP": "BRARGDPQDSMEI",
        "新聞": "Brazil economy"
    },

    "ARG": {
        "名稱": "阿根廷",
        "洲": "南美",
        "貨幣": "ARS",
        "失業率": "LRUN64TTARM156S",
        "CPI": "ARGCPIALLMINMEI",
        "GDP": "ARGRGDPQDSMEI",
        "新聞": "Argentina economy"
    },

    # 非洲
    "ZAF": {
        "名稱": "南非",
        "洲": "非洲",
        "貨幣": "ZAR",
        "失業率": "ZAFURQSMEI",
        "CPI": "ZAFCPIALLMINMEI",
        "GDP": "ZAFRGDPQDSMEI",
        "新聞": "South Africa economy"
    },

    "EGY": {
        "名稱": "埃及",
        "洲": "非洲",
        "貨幣": "EGP",
        "失業率": "LRUN64TTEGM156S",
        "CPI": "EGYCPIALLMINMEI",
        "GDP": "EGYRGDPQDSMEI",
        "新聞": "Egypt economy"
    },

    # 中東
    "SAU": {
        "名稱": "沙烏地阿拉伯",
        "洲": "中東",
        "貨幣": "SAR",
        "失業率": "SAULRUN64TTM156S",
        "CPI": "SAUCPIALLMINMEI",
        "GDP": "SAURGDPNQDSMEI",
        "新聞": "Saudi Arabia economy"
    },

    "TUR": {
        "名稱": "土耳其",
        "洲": "中東",
        "貨幣": "TRY",
        "失業率": "LRUN64TTTRM156S",
        "CPI": "TURCPIALLMINMEI",
        "GDP": "TURRGDPQDSMEI",
        "新聞": "Turkey economy"
    }
}

# =========================================================
# 🌐 Session
# =========================================================
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0"
})

# =========================================================
# 📦 FRED 抓取
# =========================================================
@st.cache_data(ttl=1800)
def fetch_fred_series(series_id, limit=24):

    try:
        url = "https://api.stlouisfed.org/fred/series/observations"

        params = {
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit
        }

        response = session.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        observations = data.get("observations", [])

        cleaned = []

        for obs in observations:

            value = obs.get("value")

            if value != ".":
                cleaned.append(float(value))

        return cleaned

    except:
        return []

# =========================================================
# 📈 CPI YoY 計算
# =========================================================
def calculate_yoy(values):

    if len(values) < 13:
        return None

    latest = values[0]
    last_year = values[12]

    try:
        return round(((latest / last_year) - 1) * 100, 2)
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

        response = session.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        return round(data["rates"][currency], 4)

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

        response = session.get(url, timeout=10)
        response.raise_for_status()

        root = ET.fromstring(response.content)

        news = []

        for item in root.findall(".//item")[:5]:

            title = item.find("title").text
            link = item.find("link").text
            pub_date = item.find("pubDate").text

            news.append({
                "title": title,
                "link": link,
                "date": pub_date[:16]
            })

        return news

    except:
        return []

# =========================================================
# 🌎 單國資料
# =========================================================
def fetch_country_data(code, info):

    unemployment = fetch_fred_series(
        info["失業率"],
        1
    )

    cpi = fetch_fred_series(
        info["CPI"],
        24
    )

    gdp = fetch_fred_series(
        info["GDP"],
        1
    )

    fx = get_fx_rate(info["貨幣"])

    return {
        "國家代碼": code,
        "國家": info["名稱"],
        "洲": info["洲"],
        "貨幣": info["貨幣"],
        "GDP 成長率 (%)": gdp[0] if gdp else None,
        "通膨率 YoY (%)": calculate_yoy(cpi),
        "失業率 (%)": unemployment[0] if unemployment else None,
        "USD FX": fx
    }

# =========================================================
# ⚡ 平行抓取
# =========================================================
@st.cache_data(ttl=1800)
def build_dataset():

    rows = []

    with ThreadPoolExecutor(max_workers=10) as executor:

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
            rows.append(future.result())

    df = pd.DataFrame(rows)

    numeric_cols = [
        "GDP 成長率 (%)",
        "通膨率 YoY (%)",
        "失業率 (%)",
        "USD FX"
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        ).round(2)

    return df

# =========================================================
# 📊 建立資料
# =========================================================
with st.spinner("🌍 全球經濟數據同步中..."):

    df = build_dataset()

# =========================================================
# 🎛️ Sidebar
# =========================================================
st.sidebar.header("⚙️ Dashboard 控制台")

continent_filter = st.sidebar.selectbox(
    "選擇洲別",
    [
        "全部",
        "北美",
        "歐洲",
        "亞洲",
        "南美",
        "非洲",
        "中東"
    ]
)

metric = st.sidebar.selectbox(
    "選擇地圖指標",
    [
        "GDP 成長率 (%)",
        "通膨率 YoY (%)",
        "失業率 (%)",
        "USD FX"
    ]
)

# =========================================================
# 🌍 Filter
# =========================================================
if continent_filter != "全部":

    filtered_df = df[
        df["洲"] == continent_filter
    ]

else:
    filtered_df = df

# =========================================================
# 📋 Data Table
# =========================================================
st.header("📊 全球主要經濟體總覽")

st.dataframe(
    filtered_df,
    hide_index=True,
    use_container_width=True
)

# =========================================================
# 🗺️ 地圖
# =========================================================
st.header("🗺️ 全球經濟熱力地圖")

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
# 📰 財經新聞
# =========================================================
st.header("📰 全球即時財經新聞")

tab_names = [
    info["名稱"]
    for info in COUNTRY_CONFIG.values()
]

tabs = st.tabs(tab_names)

for tab, (_, info) in zip(
    tabs,
    COUNTRY_CONFIG.items()
):

    with tab:

        news_items = get_news(
            info["新聞"]
        )

        if not news_items:

            st.warning("目前無新聞")

        else:

            for item in news_items:

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
    "Global Macro Dashboard Pro | "
    "Built with Streamlit + FRED API"
)
