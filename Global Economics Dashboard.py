import streamlit as st
import pandas as pd
import datetime
import requests
import plotly.express as px
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
import yfinance as yf
from openai import OpenAI
import json
from opencc import OpenCC

# 初始化 OpenCC
cc = OpenCC('s2t')

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
import json

@st.cache_data(ttl=86400)
def get_ai_summary(_news_titles, country_code, date_str):
    if not _news_titles:
        return None
    
    # 注意這裡的變數名稱要改成 _news_titles
    prompt = f"""
    今天是 {date_str}，請針對以下新聞進行財經總結。
    請務必使用【繁體中文】輸出。
    請僅輸出純 JSON 字串，不要包含任何 ```json 或 ``` 標記，也不要包含任何文字解釋。
    {{
        "market_focus": "一句話總結市場焦點，30字內",
        "stock_outlook": "股市動向分析",
        "currency_outlook": "匯率變動方向",
        "risk_tip": "關鍵風險提示"
    }}
    新聞標題：{', '.join(_news_titles)}
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一位專業的財經分析師。請始終使用繁體中文進行分析。請只輸出 JSON，不要輸出任何 Markdown 格式或額外對話。"},
                {"role": "user", "content": prompt}
            ],
            stream=False
        )
        
        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(content)
        
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = cc.convert(value)
            
        return data
    except Exception as e:
        print(f"AI Summary Error: {e}")
        return None
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
    "RUS": {"名稱": "俄羅斯 (Brent)", "洲": "歐洲", "匯率": "RUB=X", "指數": "BZ=F", "新聞": "Russia economy"},

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

    # 2. 單日匯率漲跌幅計算
    try:
        if currency_pair == "USD=X":
            fx_change = 0.0
        else:
            fx = yf.Ticker(currency_pair)
            fx_hist = fx.history(period="5d") # 抓 5 天計算漲跌
            if len(fx_hist) >= 2:
                curr = fx_hist['Close'].iloc[-1]
                prev = fx_hist['Close'].iloc[-2]
                # 單日匯率漲跌幅定義：(今日匯率 - 昨日匯率) / 昨日匯率
                fx_change = ((curr / prev) - 1) * 100
    except:
        pass
        
    return price, pct_change, ytd_change, fx_change

# =========================================================
# 🌎 全球核心總經指標抓取 (最終穩定版)
# =========================================================
@st.cache_data(ttl=300)
def fetch_global_metrics():
    # 定義指標
    metrics = {
        "恐慌指數 (VIX)": "^VIX",
        "黃金 (Gold)": "GC=F",
        "原油 (Crude Oil)": "CL=F",
        "10年期美債殖利率": "^TNX",
        "標普500 (S&P500)": "^GSPC"
    }
    
    results = {}
    for name, ticker in metrics.items():
        try:
            # 抓取近 5 天數據 (即便假日也會顯示最後交易日)
            data = yf.Ticker(ticker).history(period="5d")
            
            if not data.empty and len(data) >= 1:
                # 取得最新一筆價格
                latest = data['Close'].iloc[-1]
                
                # 若有歷史數據(>=2)，則計算漲跌；若只有 1 筆，delta 設為 0
                if len(data) >= 2:
                    prev = data['Close'].iloc[-2]
                    delta = latest - prev
                else:
                    delta = 0.0
                
                results[name] = {"val": latest, "delta": delta}
            else:
                # 若完全沒資料，補上 0 避免區塊消失
                results[name] = {"val": 0.0, "delta": 0.0}
                
        except Exception as e:
            # 若發生錯誤，給予預設值，確保程式不中斷
            results[name] = {"val": 0.0, "delta": 0.0}
            
    return results

# =========================================================
# 🧠 Market Regime Engine V2.5
# =========================================================
def classify_market_regime_v25(metrics):

    vix = metrics["恐慌指數 (VIX)"]
    gold = metrics["黃金 (Gold)"]
    oil = metrics["原油 (Crude Oil)"]
    yield10 = metrics["10年期美債殖利率"]
    spx = metrics["標普500 (S&P500)"]

    vix_d = vix["delta"]
    gold_d = gold["delta"]
    oil_d = oil["delta"]
    y_d = yield10["delta"]
    spx_d = spx["delta"]

    # ---------------------------
    # 🔴 Crisis / Risk-Off
    # ---------------------------
    if vix_d > 0 and spx_d < 0:
        return (
            "🔴 Risk-Off / Stress",
            "股市下跌 + 波動上升，資金轉向避險資產"
        )

    # ---------------------------
    # 🟠 Inflation Regime
    # ---------------------------
    if oil_d > 0 and y_d > 0 and gold_d > 0:
        return (
            "🟠 Inflation Regime",
            "能源與利率同步上升，市場交易通膨壓力"
        )

    # ---------------------------
    # 🟡 Slowdown / Recession Risk
    # ---------------------------
    if spx_d < 0 and oil_d < 0 and y_d < 0:
        return (
            "🟡 Slowdown / Recession Risk",
            "股市與商品下跌，利率回落，成長預期轉弱"
        )

    # ---------------------------
    # 🟢 Risk-On
    # ---------------------------
    if spx_d > 0 and vix_d < 0:
        return (
            "🟢 Risk-On",
            "風險偏好回升，股市主導資金流"
        )

    # ---------------------------
    # ⚪ Mixed
    # ---------------------------
    return (
        "⚪ Mixed Regime",
        "市場訊號分歧，尚未形成一致敘事"
    )

# =========================================================
# 🧠 Market Regime Probability Engine V3
# =========================================================
def compute_regime_probabilities(metrics):

    vix = metrics["恐慌指數 (VIX)"]["delta"]
    gold = metrics["黃金 (Gold)"]["delta"]
    oil = metrics["原油 (Crude Oil)"]["delta"]
    y10 = metrics["10年期美債殖利率"]["delta"]
    spx = metrics["標普500 (S&P500)"]["delta"]

    scores = {
         "🟢 風險偏好（Risk-On）": 0,

    "🟠 通膨環境（Inflation）": 0,

    "🟡 經濟放緩（Recession）": 0,

    "🔴 風險壓力（Stress）": 0

}

    # ---------------- Risk-On ----------------
    if spx > 0: scores["🟢 Risk-On"] += 2
    if vix < 0: scores["🟢 Risk-On"] += 2
    if gold < 0: scores["🟢 Risk-On"] += 1

    # ---------------- Inflation ----------------
    if oil > 0: scores["🟠 Inflation"] += 2
    if y10 > 0: scores["🟠 Inflation"] += 2
    if gold > 0: scores["🟠 Inflation"] += 1

    # ---------------- Recession ----------------
    if spx < 0: scores["🟡 Recession"] += 2
    if oil < 0: scores["🟡 Recession"] += 1
    if y10 < 0: scores["🟡 Recession"] += 1

    # ---------------- Stress / Risk-Off ----------------
    if vix > 0: scores["🔴 Stress"] += 2
    if spx < 0 and vix > 0: scores["🔴 Stress"] += 2
    if gold > 0: scores["🔴 Stress"] += 1

    # normalize → probability
    total = sum(scores.values())
    if total == 0:
        return {k: 0 for k in scores}

    probs = {k: round(v / total * 100, 1) for k, v in scores.items()}

    return probs
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
# 🌎 單國資料組裝 (更新版)
# =========================================================
def fetch_country_data(code, info):
    price, pct_change, ytd_change, fx_change = fetch_live_market_data(info["指數"], info["匯率"])
    
    # --- 新增：計算年化波動率 ---
    volatility = None
    try:
        # 抓取近一個月數據計算標準差
        ticker = yf.Ticker(info["指數"])
        hist = ticker.history(period="1mo")
        if len(hist) > 1:
            # 計算每日報酬率的標準差 -> 年化 (乘以 sqrt(252)) -> 轉為百分比
            daily_returns = hist['Close'].pct_change()
            volatility = daily_returns.std() * (252**0.5) * 100
    except:
        pass
    # ---------------------------

    return {
        "國家代碼": code,
        "國家": info["名稱"],
        "洲": info["洲"],
        "代表指數": info["指數"],
        "指數點位": round(price, 2) if price else None,
        "單日指數漲跌幅 (%)": round(pct_change, 2) if pct_change else None,
        "年初指數至今報酬 (%)": round(ytd_change, 2) if ytd_change else None,
        "單日匯率漲跌幅 (%)": round(fx_change, 2) if fx_change is not None else None,
        "市場波動率 (%)": round(volatility, 2) if volatility is not None else 0.0 # 新增欄位
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
        "單日指數漲跌幅 (%)", 
        "年初指數至今報酬 (%)",
        "市場波動率 (%)",
        "單日匯率漲跌幅 (%)"  # 這裡要確認是否已改名
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
    # 只精準清除「報價與組裝資料」的快取，絕對不動 AI 與新聞的快取！
    fetch_live_market_data.clear()
    fetch_global_metrics.clear()
    build_dataset.clear()
    
    st.rerun()

continent_filter = st.sidebar.selectbox(
    "選擇洲別",
    ["全部", "北美", "歐洲", "亞洲", "南美", "非洲", "中東", "大洋洲"]
)

# sidebar 選項要與字典中的 Key 嚴格對應
metric = st.sidebar.selectbox(
    "選擇地圖指標",
    ["單日指數漲跌幅 (%)", "年初指數至今報酬 (%)", "單日匯率漲跌幅 (%)", "市場波動率 (%)"]
)

# =========================================================
# 🌍 Filter
# =========================================================
if continent_filter != "全部":
    filtered_df = df[df["洲"] == continent_filter]
else:
    filtered_df = df

# =========================================================
# 📈 全球總經 KPI 板塊 (V2.5 Regime Integrated)
# =========================================================

st.subheader("🌍 全球市場狀態引擎")

global_data = fetch_global_metrics()


# =========================================================
# 📊 KPI Metrics Display（安全版）
# =========================================================

# 固定順序（避免 dict 順序變動造成 UI 跳動）
metric_order = [
    "恐慌指數 (VIX)",
    "黃金 (Gold)",
    "原油 (Crude Oil)",
    "10年期美債殖利率",
    "標普500 (S&P500)"
]

cols = st.columns(len(metric_order))

for i, name in enumerate(metric_order):

    # 防止 key error（避免 API/抓取失敗炸 UI）
    if name not in global_data:
        continue

    data = global_data[name]

    val = data.get("val", 0.0)
    delta = data.get("delta", 0.0)

    # 防止 NoneType crash
    val_str = f"{val:.2f}" if val is not None else "N/A"
    delta_str = f"{delta:.2f}" if delta is not None else "0.00"

    with cols[i]:
        st.metric(
            label=name,
            value=val_str,
            delta=delta_str
        )

st.markdown("---")

# =========================================================
# 🧠 V3 Regime Probabilities
# =========================================================

global_data = fetch_global_metrics()

probs = compute_regime_probabilities(global_data)

st.markdown("### 🧠 市場 Regime 判斷")

# 找最大 regime
top_regime = max(probs, key=probs.get)

st.success(f"**主導 Regime: {top_regime} ({probs[top_regime]}%)**")

# =========================================================
# 📊 Chart
# =========================================================

df_prob = pd.DataFrame({
    "市場狀態": list(probs.keys()),
    "機率 (%)": list(probs.values())
})

fig = px.bar(
    df_prob,
    x="市場狀態",
    y="機率 (%)",
    text="機率 (%)"
)

st.plotly_chart(fig, use_container_width=True)

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

# 針對單日指數漲跌幅與年初指數至今報酬，皆使用紅綠配色 (RdYlGn)
if metric in ["單日指數漲跌幅 (%)", "年初指數至今報酬 (%)"]:
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
# 📰 財經新聞 
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
            # --- 固定排版：UI 由我們完全控制 ---
            titles = [item['title'] for item in news_items]
            
            st.markdown("### 🤖 每日市場總結")
            
            # 修正縮排並呼叫新版快取函式（傳入 code）
            with st.spinner("AI 正在分析市場趨勢..."):
                today = datetime.date.today().strftime("%Y-%m-%d")
                summary = get_ai_summary(titles, code, today)
            
            if summary:
                with st.container(border=True):
                    st.write(f"📅 **分析日期：** {today}")
                    st.write(f"🎯 **市場焦點：** {summary['market_focus']}")
                    
                    # 使用 Columns 讓排版更對稱
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        st.markdown("**📈 股市動向：**")
                        st.info(summary['stock_outlook']) 
                        
                    with col2:
                        st.markdown("**💰 匯率走勢：**")
                        st.info(summary['currency_outlook'])
                    
                    st.markdown("**⚠️ 風險提示：**")
                    st.warning(summary['risk_tip'])
            else:
                st.error("AI 分析暫時無法取得，請稍後再試。")
                
            st.divider() # 橫線固定在新聞列表上方
            
            st.markdown("### 📰 最新頭條")
            for item in news_items:
                st.markdown(f"**[{item['title']}]({item['link']})** \n ⏱️ {item['date']}")
# =========================================================
# 📌 Footer
# =========================================================
st.markdown("---")
st.caption(
    "Global Market Dashboard Pro | "
    "Built with Streamlit + yfinance + Google News"
)
