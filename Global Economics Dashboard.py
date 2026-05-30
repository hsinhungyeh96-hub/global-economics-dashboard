import streamlit as st
import pandas as pd
import datetime
import requests
import plotly.express as px
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
import yfinance as yf
from openai import OpenAI
import streamlit as st

# =========================================================
# 🔐 API 安全設定
# =========================================================
# 使用 get 方法，若讀不到會給出明確錯誤提示，而不是直接跳 KeyError
try:
    api_key = st.secrets["DEEPSEEK_API_KEY"]
except Exception:
    st.error("❌ 系統偵測不到 API Key！請檢查 Streamlit Cloud Settings > Secrets 是否已存入 DEEPSEEK_API_KEY")
    st.stop() # 停止程式，避免後續報錯

client = OpenAI(
    api_key=api_key, 
    base_url="https://api.deepseek.com"
)
@st.cache_data(ttl=86400)
def get_ai_summary(news_titles, date_str):
    if not news_titles:
        return "暫無新聞。"
    
    prompt = f"""
    今天是 {date_str}，以下是關於該國經濟的即時新聞標題：
    {', '.join(news_titles)}
    
    請以專業財經分析師角度提供簡短分析：
    1. 【市場焦點】：一句話總結今日主要趨勢。
    2. 【潛在影響】：對股市與匯率的影響預測。
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat", # DeepSeek 的模型名稱
            messages=[
                {"role": "system", "content": "你是一位資深的全球總經分析師，請提供專業且客觀的市場洞察。"},
                {"role": "user", "content": prompt}
            ],
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI 分析暫時無法取得: {e}"

# =========================================================
# 🌍 基礎設定
# =========================================================
st.set_page_config(
    page_title="Global Macro Dashboard Pro",
    layout="wide"
)

st.title("🌐 全球即時財經 Dashboard Pro")
st.caption("資料來源：Yahoo Finance + Google News RSS")

st.write(
    f"⏰ 最後更新時間： "
    f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)

# =========================================================
# 🌎 全球主要經濟體設定 (更新為 yfinance Ticker)
# =========================================================
COUNTRY_CONFIG = {
    # 北美
    "USA": {"名稱": "美國", "洲": "北美", "匯率": "USD=X", "指數": "^GSPC", "新聞": "United States economy"},
    "CAN": {"名稱": "加拿大", "洲": "北美", "匯率": "CAD=X", "指數": "^GSPTSE", "新聞": "Canada economy"},
    "MEX": {"名稱": "墨西哥", "洲": "北美", "匯率": "MXN=X", "指數": "^MXX", "新聞": "Mexico economy"},

    # 歐洲
    "DEU": {"名稱": "德國", "洲": "歐洲", "匯率": "EUR=X", "指數": "^GDAXI", "新聞": "Germany economy"},
    "FRA": {"名稱": "法國", "洲": "歐洲", "匯率": "EUR=X", "指數": "^FCHI", "新聞": "France economy"},
    "GBR": {"名稱": "英國", "洲": "歐洲", "匯率": "GBP=X", "指數": "^FTSE", "新聞": "United Kingdom economy"},
    "ITA": {"名稱": "義大利", "洲": "歐洲", "匯率": "EUR=X", "指數": "FTSEMIB.MI", "新聞": "Italy economy"},

    # 亞洲
    "CHN": {"名稱": "中國", "洲": "亞洲", "匯率": "CNY=X", "指數": "000001.SS", "新聞": "China economy"},
    "JPN": {"名稱": "日本", "洲": "亞洲", "匯率": "JPY=X", "指數": "^N225", "新聞": "Japan economy"},
    "KOR": {"名稱": "韓國", "洲": "亞洲", "匯率": "KRW=X", "指數": "^KS11", "新聞": "South Korea economy"},
    "IND": {"名稱": "印度", "洲": "亞洲", "匯率": "INR=X", "指數": "^BSESN", "新聞": "India economy"},
    "TWN": {"名稱": "台灣", "洲": "亞洲", "匯率": "TWD=X", "指數": "^TWII", "新聞": "Taiwan economy"},
    "SGP": {"名稱": "新加坡", "洲": "亞洲", "匯率": "SGD=X", "指數": "^STI", "新聞": "Singapore economy"},

    # 南美
    "BRA": {"名稱": "巴西", "洲": "南美", "匯率": "BRL=X", "指數": "^BVSP", "新聞": "Brazil economy"},
    "ARG": {"名稱": "阿根廷", "洲": "南美", "匯率": "ARS=X", "指數": "^MERV", "新聞": "Argentina economy"},

    # 非洲
    "ZAF": {"名稱": "南非", "洲": "非洲", "匯率": "ZAR=X", "指數": "^J203.JO", "新聞": "South Africa economy"},
    "EGY": {"名稱": "埃及", "洲": "非洲", "匯率": "EGP=X", "指數": "CIBEY", "新聞": "Egypt economy"},

    # 中東
    "SAU": {"名稱": "沙烏地阿拉伯", "洲": "中東", "匯率": "SAR=X", "指數": "KSA", "新聞": "Saudi Arabia economy"},
    "TUR": {"名稱": "土耳其", "洲": "中東", "匯率": "TRY=X", "指數": "XU100.IS", "新聞": "Turkey economy"},

    # 大洋洲 (全新區塊)
    "AUS": {"名稱": "澳洲", "洲": "大洋洲", "匯率": "AUD=X", "指數": "^AXJO", "新聞": "Australia economy"},
    "NZL": {"名稱": "紐西蘭", "洲": "大洋洲", "匯率": "NZD=X", "指數": "^NZ50", "新聞": "New Zealand economy"},
}

# =========================================================
# 🌐 Session
# =========================================================
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0"
})

# =========================================================
# 📈 Yahoo Finance 抓取 (更新匯率為漲跌幅)
# =========================================================
@st.cache_data(ttl=300)
def fetch_live_market_data(ticker_symbol, currency_pair):
    price, pct_change, ytd_change, fx_change = None, None, None, None
    
    # 1. 股市抓取 (保持不變)
    try:
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period="5d")
        if len(hist) >= 2:
            price = hist['Close'].iloc[-1]
            prev_price = hist['Close'].iloc[-2]
            pct_change = ((price / prev_price) - 1) * 100
        elif not hist.empty:
            price = hist['Close'].iloc[-1]

        ytd_hist = stock.history(period="ytd")
        if not ytd_hist.empty and len(ytd_hist) > 1 and price is not None:
            first_price = ytd_hist['Close'].iloc[0]
            ytd_change = ((price / first_price) - 1) * 100
    except:
        pass

    # 2. 匯率漲跌幅計算
    try:
        if currency_pair == "USD=X":
            fx_change = 0.0
        else:
            fx = yf.Ticker(currency_pair)
            fx_hist = fx.history(period="5d") # 抓 5 天計算漲跌
            if len(fx_hist) >= 2:
                curr = fx_hist['Close'].iloc[-1]
                prev = fx_hist['Close'].iloc[-2]
                # 匯率漲跌幅定義：(今日匯率 - 昨日匯率) / 昨日匯率
                fx_change = ((curr / prev) - 1) * 100
    except:
        pass
        
    return price, pct_change, ytd_change, fx_change

# =========================================================
# 🌎 全球核心總經指標抓取
# =========================================================
@st.cache_data(ttl=300)
def fetch_global_metrics():
    # 定義指標代碼與名稱
    metrics = {
        "恐慌指數 (VIX)": "^VIX",
        "黃金 (Gold)": "GC=F",
        "原油 (Crude Oil)": "CL=F",
        "10年期美債殖利率": "^TNX"
    }
    
    results = {}
    for name, ticker in metrics.items():
        data = yf.Ticker(ticker).history(period="2d")
        if len(data) >= 2:
            latest = data['Close'].iloc[-1]
            prev = data['Close'].iloc[-2]
            results[name] = {"val": latest, "delta": latest - prev}
    return results

# =========================================================
# 📰 新聞 (保持原樣)
# =========================================================
@st.cache_data(ttl=1800)
def get_news(keyword):
    # 定義每個國家的主要關鍵字與備用關鍵字
    search_queries = {
        "Taiwan economy": ["Taiwan stock market", "Taiex"],
        "China economy": ["China stock market", "Shanghai composite"],
        # 其他國家也可以依此類推
    }
    
    # 嘗試抓取的關鍵字清單
    keywords_to_try = [keyword] + search_queries.get(keyword, [])
    
    for kw in keywords_to_try:
        try:
            url = f"https://news.google.com/rss/search?q={kw}&hl=en-US&gl=US&ceid=US:en"
            response = session.get(url, timeout=10)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                items = root.findall(".//item")
                if items:
                    news = []
                    for item in items[:5]:
                        news.append({
                            "title": item.find("title").text,
                            "link": item.find("link").text,
                            "date": item.find("pubDate").text[:16]
                        })
                    return news
        except:
            continue
    return [] # 真的都抓不到才回傳空

# =========================================================
# 🌎 單國資料組裝
# =========================================================
def fetch_country_data(code, info):
    price, pct_change, ytd_change, fx_change = fetch_live_market_data(info["指數"], info["匯率"])

    return {
        "國家代碼": code,
        "國家": info["名稱"],
        "洲": info["洲"],
        "代表指數": info["指數"],
        "指數點位": round(price, 2) if price else None,
        "單日漲跌幅 (%)": round(pct_change, 2) if pct_change else None,
        "年初至今報酬 (%)": round(ytd_change, 2) if ytd_change else None,
        "匯率漲跌幅 (%)": round(fx_change, 2) if fx_change is not None else None # 修改這裡
    }

# =========================================================
# ⚡ 平行抓取
# =========================================================
@st.cache_data(ttl=300)
def build_dataset():
    rows = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_country_data, code, info) for code, info in COUNTRY_CONFIG.items()]
        for future in futures:
            rows.append(future.result())

    df = pd.DataFrame(rows)
    
    # 【關鍵檢查】：這裡的欄位名稱必須與 fetch_country_data 中的字典 Key 完全吻合
    # 如果你在 fetch_country_data 裡改名了，這裡也必須同步修改！
    numeric_cols = [
        "指數點位", 
        "單日漲跌幅 (%)", 
        "年初至今報酬 (%)", 
        "匯率漲跌幅 (%)"  # 這裡要確認是否已改名
    ]
    
    # 這裡增加一個過濾，避免因為欄位不存在而報錯
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

# =========================================================
# 📊 建立資料
# =========================================================
with st.spinner("🌍 全球即時市場數據同步中..."):
    df = build_dataset()

# =========================================================
# 🎛️ Sidebar 控制台
# =========================================================
st.sidebar.header("⚙️ Dashboard 控制台")

# 手動刷新按鈕
if st.sidebar.button("🔄 強制刷新數據"):
    st.cache_data.clear()
    st.rerun()

continent_filter = st.sidebar.selectbox(
    "選擇洲別",
    ["全部", "北美", "歐洲", "亞洲", "南美", "非洲", "中東", "大洋洲"]
)

# sidebar 選項要與字典中的 Key 嚴格對應
metric = st.sidebar.selectbox(
    "選擇地圖指標",
    ["單日漲跌幅 (%)", "年初至今報酬 (%)", "匯率漲跌幅 (%)", "指數點位"]
)

# =========================================================
# 🌍 Filter
# =========================================================
if continent_filter != "全部":
    filtered_df = df[df["洲"] == continent_filter]
else:
    filtered_df = df

# =========================================================
# 📈 全球總經 KPI 板塊
# =========================================================
st.subheader("🌍 全球核心市場指標")
global_data = fetch_global_metrics()

cols = st.columns(4)
for col, (name, data) in zip(cols, global_data.items()):
    col.metric(
        label=name, 
        value=f"{data['val']:.2f}", 
        delta=f"{data['delta']:.2f}"
    )
st.markdown("---") # 分隔線

# =========================================================
# 📋 Data Table
# =========================================================
st.header("📊 全球股市與匯率總覽")

st.dataframe(
    filtered_df,
    hide_index=True,
    use_container_width=True
)

# =========================================================
# 🗺️ 地圖配色設定
# =========================================================
st.header("🗺️ 全球市場熱力地圖")

# 針對單日漲跌幅與年初至今報酬，皆使用紅綠配色 (RdYlGn)
if metric in ["單日漲跌幅 (%)", "年初至今報酬 (%)"]:
    color_scale = "RdYlGn"
    midpoint = 0 # 讓 0% 保持在中性顏色
else:
    color_scale = "Blues"
    midpoint = None

fig = px.choropleth(
    filtered_df,
    locations="國家代碼",
    color=metric,
    hover_name="國家",
    projection="natural earth",
    color_continuous_scale=color_scale,
    color_continuous_midpoint=midpoint
)

fig.update_layout(
    margin={"r": 0, "t": 30, "l": 0, "b": 0}
)

st.plotly_chart(fig, use_container_width=True)

# =========================================================
# 📰 財經新聞 (修正版：針對台灣跳過 AI 分析)
# =========================================================
st.header("📰 全球即時財經新聞")

tab_names = [info["名稱"] for info in COUNTRY_CONFIG.values()]
tabs = st.tabs(tab_names)

for tab, (code, info) in zip(tabs, COUNTRY_CONFIG.items()):
    with tab:
        news_items = get_news(info["新聞"])
        
        if not news_items:
            st.warning("目前無新聞")
        else:
            # --- AI 分析區塊 (現在台灣也會執行) ---
            titles = [item['title'] for item in news_items]
            with st.expander(f"🤖 AI 每日市場總結 ({datetime.date.today().strftime('%Y-%m-%d')})", expanded=True):
                with st.spinner("AI 正在分析市場動態..."):
                    today = datetime.date.today().strftime("%Y-%m-%d")
                    # 直接呼叫 AI
                    summary = get_ai_summary(titles, today)
                    st.markdown(summary)
            
            st.divider() 
            for item in news_items:
                st.markdown(f"### [{item['title']}]({item['link']}) \n ⏱️ {item['date']}")

# =========================================================
# 📌 Footer
# =========================================================
st.markdown("---")
st.caption(
    "Global Market Dashboard Pro | "
    "Built with Streamlit + yfinance + Google News"
)
