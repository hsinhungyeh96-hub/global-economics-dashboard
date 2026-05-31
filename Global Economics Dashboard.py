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
import numpy as np

# 初始化 OpenCC (繁簡轉換)
cc = OpenCC('s2t')

# =========================================================
# 🔐 API 安全設定
# =========================================================
try:
    api_key = st.secrets["DEEPSEEK_API_KEY"]
except Exception:
    st.error("❌ 系統偵測不到 API Key！請檢查 Streamlit Cloud Settings > Secrets 是否已存入 DEEPSEEK_API_KEY")
    st.stop() 

client = OpenAI(
    api_key=api_key, 
    base_url="https://api.deepseek.com"
)

@st.cache_data(ttl=86400)
def get_ai_summary(_news_titles, country_code, date_str):
    if not _news_titles:
        return None
    
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
# 🌍 基礎設定與國家設定
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
    # 大洋洲
    "AUS": {"名稱": "澳洲", "洲": "大洋洲", "匯率": "AUD=X", "指數": "^AXJO", "新聞": "Australia economy"},
    "NZL": {"名稱": "紐西蘭", "洲": "大洋洲", "匯率": "NZD=X", "指數": "^NZ50", "新聞": "New Zealand economy"},
}

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

# =========================================================
# 📈 Yahoo Finance 數據抓取
# =========================================================
@st.cache_data(ttl=300)
def fetch_live_market_data(ticker_symbol, currency_pair):
    price, pct_change, ytd_change, fx_change = None, None, None, None
    
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

    try:
        if currency_pair == "USD=X":
            fx_change = 0.0
        else:
            fx = yf.Ticker(currency_pair)
            fx_hist = fx.history(period="5d")
            if len(fx_hist) >= 2:
                curr = fx_hist['Close'].iloc[-1]
                prev = fx_hist['Close'].iloc[-2]
                fx_change = ((curr / prev) - 1) * 100
    except:
        pass
        
    return price, pct_change, ytd_change, fx_change

# =========================================================
# 🧠 總經指標與 Z-Score 核心引擎 (解決波動率不對等問題)
# =========================================================
@st.cache_data(ttl=300)
def fetch_global_metrics():
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
            # 抓取 30 天數據以計算標準差與 Z-Score
            data = yf.Ticker(ticker).history(period="30d")
            if not data.empty and len(data) >= 2:
                latest = data["Close"].iloc[-1]
                prev = data["Close"].iloc[-2]
                pct_change = ((latest / prev) - 1) * 100
                
                # 計算歷史波動率標準差以進行 Z-Score 標準化
                historical_changes = data["Close"].pct_change().dropna() * 100
                std_dev = historical_changes.std()
                mean_val = historical_changes.mean()
                
                # 計算 Z-Score (若標準差為 0 則設為 0)
                z_score = (pct_change - mean_val) / std_dev if std_dev > 0 else 0.0
                
                results[name] = {
                    "val": latest,
                    "delta": pct_change,
                    "z_score": z_score
                }
            else:
                results[name] = {"val": np.nan, "delta": 0.0, "z_score": 0.0}
        except Exception:
            results[name] = {"val": np.nan, "delta": 0.0, "z_score": 0.0}
    return results

def compute_regime_probabilities(metrics):
    # 提取標準化後的 Z-Score 權重，解決 VIX 天生波動大於 SPX 的問題
    vix_w = metrics.get("恐慌指數 (VIX)", {}).get("z_score", 0.0)
    gold_w = metrics.get("黃金 (Gold)", {}).get("z_score", 0.0)
    oil_w = metrics.get("原油 (Crude Oil)", {}).get("z_score", 0.0)
    y10_w = metrics.get("10年期美債殖利率", {}).get("z_score", 0.0)
    spx_w = metrics.get("標普500 (S&P500)", {}).get("z_score", 0.0)

    scores = {
        "🟢 風險偏好": 0.0,
        "🟠 通膨環境": 0.0,
        "🟡 經濟放緩": 0.0,
        "🔴 市場壓力": 0.0
    }

    # 各 Regime 邏輯特徵加總
    scores["🟢 風險偏好"] += max(spx_w, 0) + max(-vix_w, 0) + max(-gold_w, 0) * 0.5
    scores["🟠 通膨環境"] += max(oil_w, 0) + max(y10_w, 0) + max(gold_w, 0) * 0.5
    scores["🟡 經濟放緩"] += max(-spx_w, 0) + max(-oil_w, 0) + max(-y10_w, 0)
    scores["🔴 市場壓力"] += max(vix_w, 0) + max(-spx_w, 0) * 0.5 + max(gold_w, 0) * 0.5

    # 加入微小基準分 (Baseline)，完美防止全市場零波動時分母為零的 Crash 狀況
    baseline_score = 0.01
    total = sum(scores.values()) + baseline_score

    return {k: round((v / total) * 100, 1) for k, v in scores.items()}

def generate_regime_narrative(probs):
    top_regime = max(probs, key=probs.get)
    narratives = {
        "🟢 風險偏好": ("🟢 風險偏好", "風險偏好回升，資金持續流向股票等風險資產。"),
        "🟠 通膨環境": ("🟠 通膨環境 Regime", "能源與利率同步上升，市場主要交易通膨預期。"),
        "🟡 經濟放緩": ("🟡 Slowdown / 經濟放緩 Risk", "經濟成長放緩訊號增加，市場開始反映衰退風險。"),
        "🔴 市場壓力": ("🔴 Risk-Off / 市場壓力", "波動率上升且資金偏向避險資產，市場風險情緒升溫。")
    }
    return narratives[top_regime]

# =========================================================
# 📰 新聞與單國數據組裝
# =========================================================
@st.cache_data(ttl=1800)
def get_news(keyword):
    search_queries = {
        "Taiwan economy": ["Taiwan stock market", "Taiex"],
        "China economy": ["China stock market", "Shanghai composite"],
    }
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
    return []

def fetch_country_data(code, info):
    price, pct_change, ytd_change, fx_change = fetch_live_market_data(info["指數"], info["匯率"])
    volatility = np.nan
    try:
        ticker = yf.Ticker(info["指數"])
        hist = ticker.history(period="1mo")
        if len(hist) > 1:
            daily_returns = hist['Close'].pct_change()
            volatility = daily_returns.std() * (252**0.5) * 100
    except:
        pass

    # 若抓取失敗則給予 np.nan，避免 0.0 導致地圖顏色失真
    return {
        "國家代碼": code,
        "國家": info["名稱"],
        "洲": info["洲"],
        "代表指數": info["指數"],
        "指數點位": round(price, 2) if price else np.nan,
        "單日指數漲跌幅 (%)": round(pct_change, 2) if pct_change else np.nan,
        "年初指數至今報酬 (%)": round(ytd_change, 2) if ytd_change else np.nan,
        "單日匯率漲跌幅 (%)": round(fx_change, 2) if fx_change is not None else np.nan,
        "市場波動率 (%)": round(volatility, 2) if not np.isnan(volatility) else np.nan
    }

@st.cache_data(ttl=300)
def build_dataset():
    rows = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_country_data, code, info) for code, info in COUNTRY_CONFIG.items()]
        for future in futures:
            rows.append(future.result())
    df = pd.DataFrame(rows)
    numeric_cols = ["指數點位", "單日指數漲跌幅 (%)", "年初指數至今報酬 (%)", "市場波動率 (%)", "單日匯率漲跌幅 (%)"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

# =========================================================
# 📊 建立資料與介面控制
# =========================================================
with st.spinner("🌍 全球即時市場數據同步中..."):
    df = build_dataset()

st.sidebar.header("⚙️ Dashboard 控制台")
if st.sidebar.button("🔄 強制刷新數據"):
    fetch_live_market_data.clear()
    fetch_global_metrics.clear()
    build_dataset.clear()
    st.rerun()

continent_filter = st.sidebar.selectbox("選擇洲別", ["全部", "北美", "歐洲", "亞洲", "南美", "非洲", "中東", "大洋洲"])
metric = st.sidebar.selectbox("選擇地圖指標", ["單日指數漲跌幅 (%)", "年初指數至今報酬 (%)", "單日匯率漲跌幅 (%)", "市場波動率 (%)"])

filtered_df = df if continent_filter == "全部" else df[df["洲"] == continent_filter]

# =========================================================
# 📈 全球總經 KPI 板塊
# =========================================================
st.subheader("🌍 全球市場狀態引擎")
global_data = fetch_global_metrics()

metric_order = ["恐慌指數 (VIX)", "黃金 (Gold)", "原油 (Crude Oil)", "10年期美債殖利率", "標普500 (S&P500)"]
cols = st.columns(len(metric_order))

for i, name in enumerate(metric_order):
    if name not in global_data:
        continue
    data = global_data[name]
    val = data.get("val")
    delta = data.get("delta", 0.0)
    val_str = f"{val:.2f}" if val and not np.isnan(val) else "N/A"
    delta_str = f"{delta:.2f}%" if delta is not None else "0.00%"
    with cols[i]:
        st.metric(label=name, value=val_str, delta=delta_str)

st.markdown("---")

# =========================================================
# 🧠 V3 Regime 圓餅圖與敘述
# =========================================================
probs = compute_regime_probabilities(global_data)
st.markdown("### 🧠 市場 Regime 判斷")
regime, desc = generate_regime_narrative(probs)
top_regime = max(probs, key=probs.get)

st.success(f"**主導 Regime: {regime} ({probs[top_regime]}%)**")
st.info(desc)

df_prob = pd.DataFrame({"市場狀態": list(probs.keys()), "機率 (%)": list(probs.values())})

fig_pie = px.pie(
    df_prob, names="市場狀態", values="機率 (%)", hole=0.45, color="市場狀態",
    color_discrete_map={"🟢 風險偏好": "#2ECC71", "🟠 通膨環境": "#F39C12", "🟡 經濟放緩": "#F1C40F", "🔴 市場壓力": "#E74C3C"}
)
fig_pie.update_traces(textinfo="percent+label", hovertemplate="%{label}<br>%{value:.1f}%<extra></extra>")
st.plotly_chart(fig_pie, use_container_width=True)

# =========================================================
# 📋 資料表格與地圖 (優化留白)
# =========================================================
st.header("📊 全球股市與匯率總覽")
st.dataframe(filtered_df, hide_index=True, use_container_width=True)

st.header("🗺️ 全球市場熱力地圖")
color_scale = "RdYlGn" if metric in ["單日指數漲跌幅 (%)", "年初指數至今報酬 (%)"] else "Blues"
midpoint = 0 if metric in ["單日指數漲跌幅 (%)", "年初指數至今報酬 (%)"] else None

fig_map = px.choropleth(
    filtered_df, locations="國家代碼", color=metric, hover_name="國家",
    projection="natural earth", color_continuous_scale=color_scale, color_continuous_midpoint=midpoint
)
# 自動縮放並貼合地圖邊界，大幅縮減不必要的上下留白
fig_map.update_geos(fitbounds="locations", visible=False)
fig_map.update_layout(margin={"r": 0, "t": 20, "l": 0, "b": 0}, height=500)
st.plotly_chart(fig_map, use_container_width=True)

# =========================================================
# 📰 財經新聞與 AI 節流加載系統 (Lazy Loading)
# =========================================================
st.header("📰 全球即時財經新聞")
tab_names = [info["名稱"] for info in COUNTRY_CONFIG.values()]
tabs = st.tabs(tab_names)

# 初始化用來紀錄各國 AI 報告生成狀態的 Session State
if "ai_triggered" not in st.session_state:
    st.session_state.ai_triggered = {}

for tab, (code, info) in zip(tabs, COUNTRY_CONFIG.items()):
    with tab:
        news_items = get_news(info["新聞"])
        if not news_items:
            st.warning("目前無新聞")
        else:
            titles = [item['title'] for item in news_items]
            st.markdown("### 🤖 每日市場總結")
            
            # 使用手動觸核機制，避免一載入就瞬間向 DeepSeek 發出 20+ 次請求導致 API 崩潰
            button_key = f"btn_{code}"
            if code not in st.session_state.ai_triggered:
                st.session_state.ai_triggered[code] = False
                
            if not st.session_state.ai_triggered[code]:
                if st.button("🧠 點擊生成該國 AI 深度趨勢報告", key=button_key):
                    st.session_state.ai_triggered[code] = True
                    st.rerun()
            else:
                with st.spinner("AI 正在分析市場趨勢..."):
                    today = datetime.date.today().strftime("%Y-%m-%d")
                    summary = get_ai_summary(titles, code, today)
                
                if summary:
                    with st.container(border=True):
                        st.write(f"📅 **分析日期：** {today}")
                        st.write(f"🎯 **市場焦點：** {summary['market_focus']}")
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
                
            st.divider()
            st.markdown("### 📰 最新頭條")
            for item in news_items:
                st.markdown(f"**[{item['title']}]({item['link']})** \n ⏱️ {item['date']}")

# =========================================================
# 📌 Footer
# =========================================================
st.markdown("---")
st.caption("Global Market Dashboard Pro | Built with Streamlit + yfinance + Google News")
