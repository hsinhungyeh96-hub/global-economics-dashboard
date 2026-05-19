import streamlit as st
import pandas as pd
import datetime
import requests
import plotly.express as px
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

# =========================================================
# 🌐 基礎設定
# =========================================================
st.set_page_config(
    page_title="全球自動化經濟儀表板 Pro",
    layout="wide"
)

st.title("🌍 全球核心經濟 Dashboard Pro")
st.caption("資料來源：FRED + ExchangeRate.host + Google News RSS")

# ⚠️ 正式部署時請改用 Streamlit secrets 或環境變數
FRED_API_KEY = st.secrets.get("FRED_API_KEY", "")

# =========================================================
# 🌐 國家設定
# =========================================================
COUNTRY_CONFIG = {
    "USA": {
        "名稱": "美國",
        "貨幣": "USD",
        "失業率": "UNRATE",
        "CPI": "CPIAUCSL",
        "GDP": "A191RL1Q225SBEA",
        "新聞": "United States economy"
    },
    "DEU": {
        "名稱": "德國 / 歐元區",
        "貨幣": "EUR",
        "失業率": "LRHUTTTTEM156S",
        "CPI": "CP0000EZ19M086NEST",
        "GDP": "CLVMEURSCAB1GQEA",
        "新聞": "Germany economy"
    },
    "JPN": {
        "名稱": "日本",
        "貨幣": "JPY",
        "失業率": "JPNURMQSDSMEI",
        "CPI": "JPNCPIALLMINMEI",
        "GDP": "JPNRGDPQDSMEI",
        "新聞": "Japan economy"
    },
    "TWN": {
        "名稱": "台灣",
        "貨幣": "TWD",
        "失業率": "TWNURM",
        "CPI": "TWNCPIALLMINMEI",
        "GDP": "TWNRGDPQDSMEI",
        "新聞": "Taiwan economy"
    }
}

# =========================================================
# 🔧 Session
# =========================================================
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0"
})

# =========================================================
# 📦 FRED API
# =========================================================
@st.cache_data(ttl=1800)
def fetch_fred_series(series_id, limit=24):

    if not FRED_API_KEY:
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

    except Exception as e:
        st.warning(f"FRED 抓取失敗：{series_id} ({e})")
        return []


# =========================================================
# 📈 計算 CPI 年增率
# =========================================================
def calculate_yoy_inflation(values):

    if len(values) < 13:
        return None

    latest = values[0]
    last_year = values[12]

    try:
        yoy = ((latest / last_year) - 1) * 100
        return round(yoy, 2)
    except:
        return None


# =========================================================
# 💱 匯率 API
# =========================================================
@st.cache_data(ttl=1800)
def get_fx_rate(base_currency):

    if base_currency == "USD":
        return 1.0

    try:
        url = f"https://api.frankfurter.app/latest?from=USD&to={base_currency}"

        response = session.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        rate = data["rates"][base_currency]

        return round(rate, 4)

    except:
        return None


# =========================================================
# 📰 新聞 RSS
# =========================================================
@st.cache_data(ttl=1800)
def get_country_news(keyword):

    try:
        rss_url = (
            f"https://news.google.com/rss/search?"
            f"q={keyword}&hl=en-US&gl=US&ceid=US:en"
        )

        response = session.get(rss_url, timeout=10)
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

    except Exception as e:
        return [{
            "title": f"新聞讀取失敗：{e}",
            "link": "#",
            "date": "ERROR"
        }]


# =========================================================
# 🌍 單一國家資料抓取
# =========================================================
def fetch_country_data(country_code, info):

    unemployment_data = fetch_fred_series(info["失業率"], 1)
    cpi_data = fetch_fred_series(info["CPI"], 24)
    gdp_data = fetch_fred_series(info["GDP"], 1)

    unemployment = unemployment_data[0] if unemployment_data else None
    inflation = calculate_yoy_inflation(cpi_data)
    gdp = gdp_data[0] if gdp_data else None
    fx = get_fx_rate(info["貨幣"])

    return {
        "國家代碼": country_code,
        "國家": info["名稱"],
        "貨幣": info["貨幣"],
        "GDP 成長率 (%)": gdp,
        "通膨率 YoY (%)": inflation,
        "失業率 (%)": unemployment,
        "USD FX": fx
    }


# =========================================================
# ⚡ 平行抓取全球資料
# =========================================================
@st.cache_data(ttl=1800)
def build_global_dataset():

    rows = []

    with ThreadPoolExecutor(max_workers=8) as executor:

        futures = []

        for code, info in COUNTRY_CONFIG.items():
            futures.append(
                executor.submit(fetch_country_data, code, info)
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
        df[col] = pd.to_numeric(df[col], errors="coerce").round(2)

    return df


# =========================================================
# 📊 主資料表
# =========================================================
st.header("📊 全球即時經濟總覽")

with st.spinner("同步全球經濟數據中..."):
    df = build_global_dataset()

st.dataframe(
    df,
    hide_index=True,
    use_container_width=True
)

# =========================================================
# 🗺️ 全球地圖
# =========================================================
st.header("🗺️ 全球經濟熱力地圖")

metric = st.selectbox(
    "選擇觀察指標",
    [
        "GDP 成長率 (%)",
        "通膨率 YoY (%)",
        "失業率 (%)",
        "USD FX"
    ]
)

fig = px.choropleth(
    df,
    locations="國家代碼",
    color=metric,
    hover_name="國家",
    projection="natural earth",
    color_continuous_scale="Blues"
)

fig.update_layout(
    margin={"r": 0, "t": 20, "l": 0, "b": 0}
)

st.plotly_chart(fig, use_container_width=True)

# =========================================================
# 📰 新聞區
# =========================================================
st.header("📰 全球財經新聞")

tabs = st.tabs([
    info["名稱"] for info in COUNTRY_CONFIG.values()
])

for tab, (_, info) in zip(tabs, COUNTRY_CONFIG.items()):

    with tab:

        news_items = get_country_news(info["新聞"])

        for news in news_items:

            st.markdown(
                f"""
                ### [{news['title']}]({news['link']})

                ⏱️ {news['date']}
                """
            )

# =========================================================
# 📌 Footer
# =========================================================
st.markdown("---")
st.caption(
    f"最後更新時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)
