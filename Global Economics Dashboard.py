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
import re
import traceback
from opencc import OpenCC
import numpy as np
from deep_translator import GoogleTranslator

# =========================================================
# 🌐 UI Localization Dictionary
# =========================================================
TEXT = {
    "繁體中文": {
        "title": "🌐 全球即時財經 Dashboard Pro",
        "caption": "資料來源：Yahoo Finance + Google News RSS",
        "update": "⏰ 最後更新時間：",
        "api_error": "❌ 系統偵測不到 API Key！請檢查 Streamlit Cloud Settings > Secrets 是否已存入 DEEPSEEK_API_KEY",
        "sidebar_header": "⚙️ Dashboard 控制台",
        "lang": "🌐 Language",
        "refresh": "🔄 強制刷新數據",
        "syncing": "🌍 全球即時市場數據同步中...",
        "filter_continent": "選擇洲別",
        "filter_metric": "選擇地圖指標",
        "all": "全部",
        "engine_header": "🌍 全球市場狀態引擎",
        "regime_header": "### 🧠 市場 Regime 判斷",
        "regime_dominant": "**主導 Regime: {} ({}%)**",
        "overview_header": "📊 全球股市與匯率總覽",
        "map_header": "🗺️ 全球市場熱力地圖",
        "news_header": "📰 全球即時財經新聞",
        "summary": "🤖 每日市場總結",
        "focus": "🎯 市場焦點",
        "stock": "📈 股市動向",
        "fx": "💰 匯率走勢",
        "risk": "⚠️ 風險提示",
        "latest_news": "📰 最新頭條",
        "no_news": "目前無新聞",
        "ai_error": "AI 分析暫時無法取得",
        "analyzing": "AI 分析中...",
        "re_header": "🏢 房地產宏觀市場總覽",
        "re_metrics": "📊 關鍵房地產指標",
        "re_chart": "📈 全球房地產與基準利率走勢",
        "re_news": "📰 房地產市場焦點新聞"
    },
    "English": {
        "title": "🌐 Global Macro Dashboard Pro",
        "caption": "Data Source: Yahoo Finance + Google News RSS",
        "update": "⏰ Last Update:",
        "api_error": "❌ API Key not found! Please check Streamlit Secrets for DEEPSEEK_API_KEY",
        "sidebar_header": "⚙️ Dashboard Settings",
        "lang": "🌐 Language",
        "refresh": "🔄 Force Refresh Data",
        "syncing": "🌍 Syncing global market data...",
        "filter_continent": "Select Continent",
        "filter_metric": "Select Map Metric",
        "all": "All",
        "engine_header": "🌍 Global Market Engine",
        "regime_header": "### 🧠 Market Regime Analysis",
        "regime_dominant": "**Dominant Regime: {} ({}%)**",
        "overview_header": "📊 Global Market Overview",
        "map_header": "🗺️ Global Market Heatmap",
        "news_header": "📰 Global Real-time News",
        "summary": "🤖 Daily Market Summary",
        "focus": "🎯 Market Focus",
        "stock": "📈 Stock Outlook",
        "fx": "💰 Currency Outlook",
        "risk": "⚠️ Risk Warning",
        "latest_news": "📰 Latest Headlines",
        "no_news": "No news available",
        "ai_error": "AI Summary unavailable",
        "analyzing": "AI is analyzing...",
        "re_header": "🏢 Real Estate Macro Market",
        "re_metrics": "📊 Key Real Estate Metrics",
        "re_chart": "📈 Global Real Estate vs Interest Rates",
        "re_news": "📰 Real Estate Market Focus"
    }
}

# English translations for Dataframe Columns & Dropdowns
COL_EN = {
    "國家代碼": "Country Code", "國家": "Country", "洲": "Continent", 
    "代表指數": "Index", "指數點位": "Index Level", "單日指數漲跌幅 (%)": "Daily Index Change (%)", 
    "年初指數至今報酬 (%)": "YTD Index Return (%)", "單日匯率漲跌幅 (%)": "Daily FX Change (%)", 
    "市場波動率 (%)": "Market Volatility (%)"
}

CONTINENTS_EN = {
    "北美": "North America", "歐洲": "Europe", "亞洲": "Asia", 
    "南美": "South America", "非洲": "Africa", "中東": "Middle East", "大洋洲": "Oceania"
}

# =========================================================
# 🌍 基礎設定與國家設定
# =========================================================
st.set_page_config(page_title="Global Macro Dashboard Pro", layout="wide")

cc = OpenCC('s2t')
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

try:
    api_key = st.secrets["DEEPSEEK_API_KEY"]
except Exception:
    st.error(TEXT["繁體中文"]["api_error"])
    st.stop() 

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# 定義全球總覽的資產代號
ASSET_CONFIG = {
    # 股市：代表風險資產
    "🇺🇸 美國股市": "SPY",
    "🇯🇵 日本股市": "^N225",
    "🇨🇳 中國股市": "000001.SS",
    
    # 房地產：代表實體資產與不動產景氣
    "🌍 全球房產": "REET",
    "🏠 美國房產": "VNQ",
    "🏢 歐洲房產": "IFEU",
    
    # 利率敏感指標：債券代表資金成本與無風險利率
    "⚖️ 美國短債 (利率指標)": "SHV",
    "⛓️ 全球債券": "BNDX"
}

# --- 新增房地產標的設定 ---
# 涵蓋美國REITs、全球REITs、美國房屋建商、以及對標的10年期美債
REAL_ESTATE_CONFIG = {
    "美國房地產 (VNQ)": "VNQ",
    "全球不含美房市 (VNQI)": "VNQI",
    "美國房屋建商 (ITB)": "ITB",
    "商業不動產抵押 (REM)": "REM",
    "10年期美債殖利率": "^TNX" 
}

COUNTRY_CONFIG = {
    "USA": {"名稱": "美國", "洲": "北美", "匯率": "USD=X", "指數": "^GSPC", "新聞": "United States economy", "en_name": "USA"},
    "CAN": {"名稱": "加拿大", "洲": "北美", "匯率": "CAD=X", "指數": "^GSPTSE", "新聞": "Canada economy", "en_name": "Canada"},
    "MEX": {"名稱": "墨西哥", "洲": "北美", "匯率": "MXN=X", "指數": "^MXX", "新聞": "Mexico economy", "en_name": "Mexico"},

    "DEU": {"名稱": "德國", "洲": "歐洲", "匯率": "EUR=X", "指數": "^GDAXI", "新聞": "Germany economy", "en_name": "Germany"},
    "FRA": {"名稱": "法國", "洲": "歐洲", "匯率": "EUR=X", "指數": "^FCHI", "新聞": "France economy", "en_name": "France"},
    "GBR": {"名稱": "英國", "洲": "歐洲", "匯率": "GBP=X", "指數": "^FTSE", "新聞": "United Kingdom economy", "en_name": "UK"},
    "ITA": {"名稱": "義大利", "洲": "歐洲", "匯率": "EUR=X", "指數": "FTSEMIB.MI", "新聞": "Italy economy", "en_name": "Italy"},
    "NLD": {"名稱": "荷蘭", "洲": "歐洲", "匯率": "EUR=X", "指數": "^AEX", "新聞": "Netherlands economy", "en_name": "Netherlands"},
    "GRC": {"名稱": "希臘", "洲": "歐洲", "匯率": "EUR=X", "指數": "GREK", "新聞": "Greece economy", "en_name": "Greece"},
    "RUS": {"名稱": "俄羅斯", "洲": "歐洲", "匯率": "RUB=X", "指數": "BZ=F", "新聞": "Russia economy", "en_name": "Russia"},

    "CHN": {"名稱": "中國", "洲": "亞洲", "匯率": "CNY=X", "指數": "MCHI", "新聞": "China economy", "en_name": "China"},
    "JPN": {"名稱": "日本", "洲": "亞洲", "匯率": "JPY=X", "指數": "^N225", "新聞": "Japan economy", "en_name": "Japan"},
    "KOR": {"名稱": "韓國", "洲": "亞洲", "匯率": "KRW=X", "指數": "069500.KS", "新聞": "South Korea economy", "en_name": "South Korea"},
    "IND": {"名稱": "印度", "洲": "亞洲", "匯率": "INR=X", "指數": "^BSESN", "新聞": "India economy", "en_name": "India"},
    "TWN": {"名稱": "台灣", "洲": "亞洲", "匯率": "TWD=X", "指數": "^TWII", "新聞": "Taiwan economy", "en_name": "Taiwan"},
    "SGP": {"名稱": "新加坡", "洲": "亞洲", "匯率": "SGD=X", "指數": "^STI", "新聞": "Singapore economy", "en_name": "Singapore"},

    "BRA": {"名稱": "巴西", "洲": "南美", "匯率": "BRL=X", "指數": "^BVSP", "新聞": "Brazil economy", "en_name": "Brazil"},
    "ARG": {"名稱": "阿根廷", "洲": "南美", "匯率": "ARS=X", "指數": "^MERV", "新聞": "Argentina economy", "en_name": "Argentina"},

    "ZAF": {"名稱": "南非", "洲": "非洲", "匯率": "ZAR=X", "指數": "^J203.JO", "新聞": "South Africa economy", "en_name": "South Africa"},
    "EGY": {"名稱": "埃及", "洲": "非洲", "匯率": "EGP=X", "指數": "CIBEY", "新聞": "Egypt economy", "en_name": "Egypt"},

    "SAU": {"名稱": "沙烏地", "洲": "中東", "匯率": "SAR=X", "指數": "KSA", "新聞": "Saudi Arabia economy", "en_name": "Saudi Arabia"},
    "TUR": {"名稱": "土耳其", "洲": "中東", "匯率": "TRY=X", "指數": "XU100.IS", "新聞": "Turkey economy", "en_name": "Turkey"},

    "AUS": {"名稱": "澳洲", "洲": "大洋洲", "匯率": "AUD=X", "指數": "^AXJO", "新聞": "Australia economy", "en_name": "Australia"},
    "NZL": {"名稱": "紐西蘭", "洲": "大洋洲", "匯率": "NZD=X", "指數": "^NZ50", "新聞": "New Zealand economy", "en_name": "New Zealand"}
}

@st.cache_data(ttl=86400, show_spinner=False)
def translate_text(text, target_lang):
    if not text: return text
    try: return GoogleTranslator(source="auto", target=target_lang).translate(text)
    except Exception: return text

# =========================================================
# 📈 Yahoo Finance & Global Engine Data Fetching
# =========================================================
@st.cache_data(ttl=6000)
def fetch_live_market_data(ticker_symbol, currency_pair):
    price, pct_change, ytd_change, fx_change = None, None, None, None
    try:
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period="5d")
        if len(hist) >= 2:
            price, prev_price = hist['Close'].iloc[-1], hist['Close'].iloc[-2]
            pct_change = ((price / prev_price) - 1) * 100
        elif not hist.empty:
            price = hist['Close'].iloc[-1]

        ytd_hist = stock.history(period="ytd")
        if not ytd_hist.empty and len(ytd_hist) > 1 and price is not None:
            first_price = ytd_hist['Close'].iloc[0]
            ytd_change = ((price / first_price) - 1) * 100
    except: pass

    try:
        if currency_pair == "USD=X": fx_change = 0.0
        else:
            fx_hist = yf.Ticker(currency_pair).history(period="5d")
            if len(fx_hist) >= 2:
                fx_change = ((fx_hist['Close'].iloc[-1] / fx_hist['Close'].iloc[-2]) - 1) * 100
    except: pass
    return price, pct_change, ytd_change, fx_change

@st.cache_data(ttl=300)
def fetch_global_metrics():
    metrics = {
        "恐慌指數 (VIX)": "^VIX", "黃金 (Gold)": "GC=F",
        "原油 (Crude Oil)": "CL=F", "10年期美債殖利率": "^TNX", "標普500 (S&P500)": "^GSPC"
    }
    results = {}
    for name, ticker in metrics.items():
        try:
            data = yf.Ticker(ticker).history(period="30d")
            if not data.empty and len(data) >= 2:
                latest, prev = data["Close"].iloc[-1], data["Close"].iloc[-2]
                pct_change = ((latest / prev) - 1) * 100
                hist_chg = data["Close"].pct_change().dropna() * 100
                std_dev = hist_chg.std()
                z_score = (pct_change - hist_chg.mean()) / std_dev if std_dev > 0 else 0.0
                results[name] = {"val": latest, "delta": pct_change, "z_score": z_score}
            else:
                results[name] = {"val": np.nan, "delta": 0.0, "z_score": 0.0}
        except Exception:
            results[name] = {"val": np.nan, "delta": 0.0, "z_score": 0.0}
    return results

def compute_regime_probabilities(metrics):
    vix_w, gold_w = metrics.get("恐慌指數 (VIX)", {}).get("z_score", 0.0), metrics.get("黃金 (Gold)", {}).get("z_score", 0.0)
    oil_w, y10_w = metrics.get("原油 (Crude Oil)", {}).get("z_score", 0.0), metrics.get("10年期美債殖利率", {}).get("z_score", 0.0)
    spx_w = metrics.get("標普500 (S&P500)", {}).get("z_score", 0.0)

    scores = {"🟢 風險偏好": 0.0, "🟠 通膨環境": 0.0, "🟡 經濟放緩": 0.0, "🔴 市場壓力": 0.0}
    scores["🟢 風險偏好"] += max(spx_w, 0) + max(-vix_w, 0) + max(-gold_w, 0) * 0.5
    scores["🟠 通膨環境"] += max(oil_w, 0) + max(y10_w, 0) + max(gold_w, 0) * 0.5
    scores["🟡 經濟放緩"] += max(-spx_w, 0) + max(-oil_w, 0) + max(-y10_w, 0)
    scores["🔴 市場壓力"] += max(vix_w, 0) + max(-spx_w, 0) * 0.5 + max(gold_w, 0) * 0.5

    total = sum(scores.values()) + 0.01
    return {k: round((v / total) * 100, 1) for k, v in scores.items()}

def generate_regime_narrative(probs, lang):
    top_regime = max(probs, key=probs.get)
    if lang == "English":
        narratives = {
            "🟢 風險偏好": ("🟢 Risk-On", "Risk appetite recovering, funds flowing into stocks and risk assets."),
            "🟠 通膨環境": ("🟠 Inflation Regime", "Energy and rates rising, market pricing in inflation expectations."),
            "🟡 經濟放緩": ("🟡 Slowdown Risk", "Growth slowdown signals increasing, market reflecting recession risks."),
            "🔴 市場壓力": ("🔴 Risk-Off", "Volatility rising, funds shifting to safe havens, risk aversion increasing.")
        }
    else:
        narratives = {
            "🟢 風險偏好": ("🟢 風險偏好", "風險偏好回升，資金持續流向股票等風險資產。"),
            "🟠 通膨環境": ("🟠 通膨環境", "能源與利率同步上升，市場主要交易通膨預期。"),
            "🟡 經濟放緩": ("🟡 經濟放緩", "經濟成長放緩訊號增加，市場開始反映衰退風險。"),
            "🔴 市場壓力": ("🔴 市場壓力", "波動率上升且資金偏向避險資產，市場風險情緒升溫。")
        }
    return narratives[top_regime]

# =========================================================
# 🧠 Dynamic AI Engine (Native Translation)
# =========================================================
@st.cache_data(ttl=86400)
def get_ai_summary(country_code, date_str, lang):
    info = COUNTRY_CONFIG[country_code]

    news_items = get_news(info["新聞"])
    if not news_items:
        return {

        "market_focus": "No major news available.",

        "stock_outlook": "Insufficient news data.",

        "currency_outlook": "Insufficient news data.",

        "risk_tip": "Monitor future developments."

        }

    news_titles = [item["title"] for item in news_items[:5]]

    lang_instruction = (
        "請務必使用繁體中文。"
        if lang == "繁體中文"
        else "Please output entirely in English."
    )

    prompt = f"""
Today is {date_str}.

Based on the following headlines, analyze today's market condition.

{lang_instruction}

Return a valid JSON object only.

Do not use markdown.
Do not use ```json.
Do not provide explanations.
Do not provide notes.
Do not provide text before or after the JSON.

Required format:

{{
    "market_focus":"One sentence market focus",
    "stock_outlook":"Stock market analysis",
    "currency_outlook":"Currency trend analysis",
    "risk_tip":"Risk warning"
}}

Headlines:
{chr(10).join(news_titles)}
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional macro analyst. "
                        "You must return a valid JSON object only."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            stream=False,
        )

        content = response.choices[0].message.content.strip()

        # =====================================================
        # Extract JSON from response
        # =====================================================
        match = re.search(r"\{.*\}", content, re.DOTALL)

        if not match:
            raise ValueError(
                f"No JSON found in model response.\n\nResponse:\n{content}"
            )

        json_text = match.group()

        # =====================================================
        # Parse JSON
        # =====================================================
        data = json.loads(json_text)

        # =====================================================
        # Validate required fields
        # =====================================================
        required_keys = {
            "market_focus",
            "stock_outlook",
            "currency_outlook",
            "risk_tip",
        }

        missing_keys = required_keys - set(data.keys())

        if missing_keys:
            raise ValueError(
                f"Missing required keys: {missing_keys}\n\nJSON:\n{json_text}"
            )

        # =====================================================
        # Convert Simplified Chinese -> Traditional Chinese
        # =====================================================
        if lang == "繁體中文":
            for k, v in data.items():
                if isinstance(v, str):
                    data[k] = cc.convert(v)

        return data

    except Exception as e:

        print("=" * 80)
        print("AI SUMMARY ERROR")
        print("=" * 80)
        print(f"Country: {country_code}")
        print(f"Date: {date_str}")
        print(f"Language: {lang}")
        print()
        print(traceback.format_exc())
        print("=" * 80)

        return None

@st.cache_data(ttl=3600)
def fetch_real_estate_data():
    hist_data = {}
    metrics_data = {}
    
    for name, ticker in REAL_ESTATE_CONFIG.items():
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            if not hist.empty:
                # 正規化數據 (基準化為100)
                hist_data[name] = (hist['Close'] / hist['Close'].iloc[0]) * 100
                
                latest_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2]
                daily_pct = ((latest_price / prev_price) - 1) * 100
                
                metrics_data[name] = {
                    "price": latest_price,
                    "daily_pct": daily_pct
                }
        except Exception:
            pass
            
    if hist_data:
        df_chart = pd.DataFrame(hist_data).reset_index()
        
        # 📌 防錯 1：強制將第一欄重命名為 "Date"，避免因 yfinance 版本導致的名稱差異 (如 date, Datetime)
        first_col = df_chart.columns[0]
        df_chart.rename(columns={first_col: "Date"}, inplace=True)
        
        # 📌 防錯 2：將日期轉換為標準時間，並徹底「移除時區資訊」(解決 Plotly 空白圖表的主因)
        df_chart["Date"] = pd.to_datetime(df_chart["Date"])
        if df_chart["Date"].dt.tz is not None:
            df_chart["Date"] = df_chart["Date"].dt.tz_localize(None)
            
        # 📌 防錯 3：向前/向後填補因各國休市日不同造成的 NaN 缺失值，確保 Plotly 線條連續不中斷
        df_chart = df_chart.ffill().bfill()
        
        return df_chart, metrics_data
    return pd.DataFrame(), {}


# =========================================================
# 📰 News & Dataset Builder
# =========================================================
@st.cache_data(ttl=1800)
def get_market_data(asset_dict):
    data = []
    for name, ticker in asset_dict.items():
        # 抓取近 2 個月資料以計算 30 天變化
        hist = yf.Ticker(ticker).history(period="2mo")
        if len(hist) >= 30:
            # 計算 30 天報酬率
            price_now = hist['Close'].iloc[-1]
            price_30d = hist['Close'].iloc[-30]
            pct_change = ((price_now - price_30d) / price_30d) * 100
            data.append({"資產類別": name, "漲跌幅": pct_change})
    return pd.DataFrame(data)

def render_market_metrics():
    # 1. 取得數據並計算漲跌幅
    data = {}
    for name, ticker in ASSET_CONFIG.items():
        hist = yf.Ticker(ticker).history(period="60d")
        if len(hist) >= 30:
            price_now = hist['Close'].iloc[-1]
            price_30d = hist['Close'].iloc[-30]
            pct_change = ((price_now - price_30d) / price_30d) * 100
            data[name] = pct_change
    
    # 2. 分組排版 (根據資產類別)
    # 這裡我們手動分組，讓版面更整齊
    groups = {
        "股市": ["🇺🇸 美股(SPY)", "🇯🇵 日股(^N225)"],
        "房產": ["🌍 全球房產(REET)", "🏠 美國房產(VNQ)"],
        "債券/利率": ["⚖️ 美國短債(SHV)"]
    }
    
    for group_name, assets in groups.items():
        st.markdown(f"#### {group_name}")
        cols = st.columns(len(assets))
        for col, asset_name in zip(cols, assets):
            if asset_name in data:
                val = data[asset_name]
                # 簡化名稱，去掉 Emoji 方便顯示
                display_name = asset_name.split(" ")[-1] 
                col.metric(
                    label=display_name, 
                    value=f"{val:.2f}%", 
                    delta=f"{val:.2f}%" if val != 0 else None
                )
        st.divider() # 畫一條線區隔

def get_news(keyword):
    keywords_to_try = [keyword] + (["Taiwan stock market", "Taiex"] if keyword == "Taiwan economy" else 
                                   ["China stock market", "Shanghai composite"] if keyword == "China economy" else [])
    
    for kw in keywords_to_try:
        try:
            # 📌 防錯重點：不要自己把變數塞進字串，改用 params 讓 requests 自動做 URL 安全編碼
            url = "https://news.google.com/rss/search"
            payload = {
                "q": kw,
                "hl": "en-US",
                "gl": "US",
                "ceid": "US:en"
            }
            
            response = session.get(url, params=payload, timeout=10)
            
            # 只有當 HTTP 狀態碼為 200 (成功) 時才解析
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                items = root.findall(".//item")
                if items:
                    return [
                        {
                            "title": i.find("title").text, 
                            "link": i.find("link").text, 
                            "date": i.find("pubDate").text[:16]
                        } for i in items[:5]
                    ]
            else:
                # 若 Google 暫時阻擋或回傳 500，印出警告但不讓程式崩潰
                print(f"Google News RSS 請求失敗: {response.status_code} for keyword: {kw}")
                
        except Exception as e:
            print(f"解析新聞發生錯誤: {e}")
            continue
            
    return []

def fetch_country_data(code, info):
    price, pct_change, ytd_change, fx_change = fetch_live_market_data(info["指數"], info["匯率"])
    volatility = np.nan
    try:
        hist = yf.Ticker(info["指數"]).history(period="1mo")
        if len(hist) > 1: volatility = hist['Close'].pct_change().std() * (252**0.5) * 100
    except: pass

    return {
        "國家代碼": code, "國家": info["名稱"], "洲": info["洲"], "代表指數": info["指數"],
        "指數點位": round(price, 2) if price else np.nan, "單日指數漲跌幅 (%)": round(pct_change, 2) if pct_change else np.nan,
        "年初指數至今報酬 (%)": round(ytd_change, 2) if ytd_change else np.nan,
        "單日匯率漲跌幅 (%)": round(fx_change, 2) if fx_change is not None else np.nan,
        "市場波動率 (%)": round(volatility, 2) if not np.isnan(volatility) else np.nan
    }

@st.cache_data(ttl=300)
def build_dataset():
    rows = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_country_data, code, info) for code, info in COUNTRY_CONFIG.items()]
        for f in futures: rows.append(f.result())
    df = pd.DataFrame(rows)
    for col in ["指數點位", "單日指數漲跌幅 (%)", "年初指數至今報酬 (%)", "市場波動率 (%)", "單日匯率漲跌幅 (%)"]:
        if col in df.columns: df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

# =========================================================
# 📊 User Interface & Sidebar Controls
# =========================================================
st.sidebar.header("⚙️ Dashboard Controls")
language = st.sidebar.selectbox("🌐 Language", ["繁體中文", "English"])

T = TEXT[language] # Simplify dictionary access

with st.spinner(T["syncing"]):
    df = build_dataset()

st.title(T["title"])
st.caption(T["caption"])
st.write(f"{T['update']} {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if st.sidebar.button(T["refresh"]):
    fetch_live_market_data.clear()
    fetch_global_metrics.clear()
    build_dataset.clear()
    st.rerun()

# Dynamic Sidebar Filters
continent_opts = ["全部", "北美", "歐洲", "亞洲", "南美", "非洲", "中東", "大洋洲"]
metric_opts = ["單日指數漲跌幅 (%)", "年初指數至今報酬 (%)", "單日匯率漲跌幅 (%)", "市場波動率 (%)"]

if language == "English":
    display_continents = ["All", "North America", "Europe", "Asia", "South America", "Africa", "Middle East", "Oceania"]
    display_metrics = ["Daily Index Change (%)", "YTD Index Return (%)", "Daily FX Change (%)", "Market Volatility (%)"]
else:
    display_continents = continent_opts
    display_metrics = metric_opts

selected_continent_display = st.sidebar.selectbox(T["filter_continent"], display_continents)
selected_metric_display = st.sidebar.selectbox(T["filter_metric"], display_metrics)

# Map display back to backend keys
continent_filter = continent_opts[display_continents.index(selected_continent_display)]
metric_backend = metric_opts[display_metrics.index(selected_metric_display)]

filtered_df = df if continent_filter == "全部" else df[df["洲"] == continent_filter]

# Convert DF to English for display if needed
display_df = filtered_df.copy()
if language == "English":
    display_df["洲"] = display_df["洲"].map(CONTINENTS_EN)
    display_df["國家"] = display_df["國家代碼"].map(lambda c: COUNTRY_CONFIG[c]["en_name"])
    display_df.rename(columns=COL_EN, inplace=True)

# =========================================================
# 📈 Global Engine & KPIs
# =========================================================
st.subheader(T["engine_header"])
global_data = fetch_global_metrics()

metric_order = ["恐慌指數 (VIX)", "黃金 (Gold)", "原油 (Crude Oil)", "10年期美債殖利率", "標普500 (S&P500)"]
if language == "English":
    display_metric_names = ["VIX", "Gold", "Crude Oil", "10Y Treasury", "S&P 500"]
else:
    display_metric_names = metric_order

cols = st.columns(len(metric_order))
for i, (backend_name, display_name) in enumerate(zip(metric_order, display_metric_names)):
    if backend_name in global_data:
        data = global_data[backend_name]
        val, delta = data.get("val"), data.get("delta", 0.0)
        val_str = f"{val:.2f}" if val and not np.isnan(val) else "N/A"
        delta_str = f"{delta:.2f}%" if delta is not None else "0.00%"
        with cols[i]:
            st.metric(label=display_name, value=val_str, delta=delta_str)

st.markdown("---")

# =========================================================
# 🧠 Regime Pie Chart
# =========================================================
probs = compute_regime_probabilities(global_data)
st.markdown(T["regime_header"])
regime, desc = generate_regime_narrative(probs, language)
top_regime = max(probs, key=probs.get)

st.success(T["regime_dominant"].format(regime, probs[top_regime]))
st.info(desc)

# Map Probabilities to display language for pie chart
if language == "English":
    prob_keys_en = {"🟢 風險偏好": "🟢 Risk-On", "🟠 通膨環境": "🟠 Inflation", "🟡 經濟放緩": "🟡 Slowdown", "🔴 市場壓力": "🔴 Risk-Off"}
    df_prob = pd.DataFrame({"Market Regime": [prob_keys_en[k] for k in probs.keys()], "Probability (%)": list(probs.values())})
    fig_pie = px.pie(df_prob, names="Market Regime", values="Probability (%)", hole=0.45, color="Market Regime",
                     color_discrete_map={"🟢 Risk-On": "#2ECC71", "🟠 Inflation": "#F39C12", "🟡 Slowdown": "#F1C40F", "🔴 Risk-Off": "#E74C3C"})
else:
    df_prob = pd.DataFrame({"市場狀態": list(probs.keys()), "機率 (%)": list(probs.values())})
    fig_pie = px.pie(df_prob, names="市場狀態", values="機率 (%)", hole=0.45, color="市場狀態",
                     color_discrete_map={"🟢 風險偏好": "#2ECC71", "🟠 通膨環境": "#F39C12", "🟡 經濟放緩": "#F1C40F", "🔴 市場壓力": "#E74C3C"})

fig_pie.update_traces(textinfo="percent+label", hovertemplate="%{label}<br>%{value:.1f}%<extra></extra>")
st.plotly_chart(fig_pie, use_container_width=True)

# =========================================================
# 📋 Data Table & Heatmap
# =========================================================
st.header(T["overview_header"])
st.dataframe(display_df, hide_index=True, use_container_width=True)

st.header(T["map_header"])
color_scale = "RdYlGn" if metric_backend in ["單日指數漲跌幅 (%)", "年初指數至今報酬 (%)"] else "Blues"
midpoint = 0 if metric_backend in ["單日指數漲跌幅 (%)", "年初指數至今報酬 (%)"] else None
plot_metric = COL_EN[metric_backend] if language == "English" else metric_backend

fig_map = px.choropleth(
    display_df, locations="Country Code" if language == "English" else "國家代碼", 
    color=plot_metric, hover_name="Country" if language == "English" else "國家",
    projection="natural earth", color_continuous_scale=color_scale, color_continuous_midpoint=midpoint
)
fig_map.update_geos(fitbounds="locations", visible=False)
fig_map.update_layout(margin={"r": 0, "t": 20, "l": 0, "b": 0}, height=500)
st.plotly_chart(fig_map, use_container_width=True)

st.subheader("📊 全球市場動能總覽")
render_market_heatmap()

# =========================================================
# 🏢 房地產宏觀市場模塊 (Real Estate Module)
# =========================================================
st.markdown("---")
st.header(T["re_header"])

re_chart_df, re_metrics = fetch_real_estate_data()

if re_metrics:
    st.subheader(T["re_metrics"])
    # 動態產生 Metric Columns
    re_cols = st.columns(len(REAL_ESTATE_CONFIG))
    
    # 對應英文名稱 (若選擇英文介面)
    re_name_map_en = {
        "美國房地產 (VNQ)": "US Real Estate (VNQ)",
        "全球不含美房市 (VNQI)": "Global ex-US RE (VNQI)",
        "美國房屋建商 (ITB)": "US Homebuilders (ITB)",
        "商業不動產抵押 (REM)": "Mortgage REITs (REM)",
        "10年期美債殖利率": "10Y Treasury Yield"
    }

    for i, (zh_name, data) in enumerate(re_metrics.items()):
        display_name = re_name_map_en.get(zh_name, zh_name) if language == "English" else zh_name
        with re_cols[i]:
            val_str = f"{data['price']:.2f}"
            delta_str = f"{data['daily_pct']:.2f}%"
            # 10年期美債的單位是%，顯示上稍作區分
            if "TNX" in REAL_ESTATE_CONFIG[zh_name]:
                val_str = f"{data['price']:.3f}%"
                delta_str = f"{data['daily_pct']:.2f} bps" # 近似基點變動
                
            st.metric(label=display_name, value=val_str, delta=delta_str)

if not re_chart_df.empty:
    st.subheader(T["re_chart"])
    # 融化 DataFrame 以適應 Plotly 格式
    df_melted = re_chart_df.melt(id_vars=["Date"], var_name="Asset", value_name="Normalized Performance (Base=100)")
    
    if language == "English":
        df_melted["Asset"] = df_melted["Asset"].map(lambda x: re_name_map_en.get(x, x))
        
    # 📌 防錯 4：移除原本有潛在報錯風險的 hover_data 自訂語法，改用乾淨流暢的預設 px.line
    fig_re = px.line(
        df_melted, x="Date", y="Normalized Performance (Base=100)", color="Asset"
    )
    
    fig_re.update_layout(
        hovermode="x unified",
        legend_title_text="資產標的" if language == "繁體中文" else "Assets",
        margin={"r": 0, "t": 20, "l": 0, "b": 0}, 
        height=400
    )
    
    # 📌 透過 update_xaxes 確保 X 軸時間顯示格式漂亮且客製化
    fig_re.update_xaxes(tickformat="%Y-%m-%d")
    st.plotly_chart(fig_re, use_container_width=True)

# =========================================================
# 📰 房地產各大洲專屬 AI 新聞總結
# =========================================================
st.subheader(T["re_news"])

# 1. 獨立出 AI 總結函數，並設定 ttl=86400 (24小時)，確保一天只消耗一次 Token！
@st.cache_data(ttl=86400)
def fetch_re_ai_summary(continent_name, news_titles_tuple, today_str, lang_instruction):
    re_prompt = f"""
    Today is {today_str}.
    Based on the following {continent_name} real estate headlines, analyze the macro real estate market condition for this region.
    {lang_instruction}
    Return a valid JSON object only. Do not use markdown.
    Required format:
    {{
        "market_focus":"One sentence real estate market focus",
        "stock_outlook":"REITs and housing market analysis",
        "currency_outlook":"Impact of interest rates/yields on real estate",
        "risk_tip":"Real estate risk warning"
    }}
    Headlines:
    {chr(10).join(news_titles_tuple)}
    """
    try:
        re_response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a professional real estate macro analyst. Return valid JSON only."},
                {"role": "user", "content": re_prompt},
            ],
            stream=False,
        )
        re_content = re_response.choices[0].message.content.strip()
        match = re.search(r"\{.*\}", re_content, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"AI 解析錯誤 ({continent_name}): {e}")
    return None

# 2. 定義各大洲房地產新聞搜尋關鍵字
RE_CONTINENT_KEYWORDS = {
    "北美": "North America real estate market housing",
    "歐洲": "Europe real estate market housing",
    "亞洲": "Asia real estate market housing",
    "南美": "South America real estate market housing",
    "中東及非洲": "Middle East Africa real estate market",
    "大洋洲": "Australia New Zealand real estate market"
}

if language == "English":
    re_tab_names = ["North America", "Europe", "Asia", "South America", "Middle East & Africa", "Oceania"]
else:
    re_tab_names = list(RE_CONTINENT_KEYWORDS.keys())

re_tabs = st.tabs(re_tab_names)

# 3. 執行迴圈與渲染畫面
for tab, (zh_continent, keyword) in zip(re_tabs, RE_CONTINENT_KEYWORDS.items()):
    with tab:
        re_news_items = get_news(keyword)
        
        if re_news_items:
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            with st.spinner(T["analyzing"]):
                # 將 List 轉為 Tuple，因為 Streamlit 的 cache 函數參數必須是可雜湊的 (hashable)
                re_news_titles = tuple([item["title"] for item in re_news_items[:5]])
                lang_instruction = "請務必使用繁體中文。" if language == "繁體中文" else "Please output entirely in English."
                continent_name = zh_continent if language == "繁體中文" else re_tab_names[list(RE_CONTINENT_KEYWORDS.keys()).index(zh_continent)]
                
                # 呼叫快取函數 (這裡才會真正省 Token！)
                re_data = fetch_re_ai_summary(continent_name, re_news_titles, today_str, lang_instruction)
                
                if re_data:
                    # 繁體中文轉換
                    if language == "繁體中文":
                        for k, v in re_data.items():
                            if isinstance(v, str):
                                re_data[k] = cc.convert(v)
                    
                    with st.container(border=True):
                        # 📌 修正：根據使用者選擇的語言，動態決定小標題的文字
                        if language == "English":
                            focus_label = "Focus: "
                            col1_header = f"**🏢 {continent_name} Real Estate & REITs Outlook**"
                            col2_header = "**📉 Interest Rate Environment & Impact**"
                        else:
                            focus_label = f"{T['focus']}："
                            col1_header = f"**🏢 {continent_name}房市與 REITs 展望**"
                            col2_header = "**📉 利率環境與影響**"

                        st.write(f"📅 {today_str}")
                        st.write(f"**{focus_label}**{re_data.get('market_focus', '')}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(col1_header)
                            st.info(re_data.get("stock_outlook", ""))
                        with col2:
                            st.markdown(col2_header)
                            st.info(re_data.get("currency_outlook", ""))
                            
                        st.markdown(f"**{T['risk']}**")
                        st.warning(re_data.get("risk_tip", ""))
                else:
                    st.error(T["ai_error"])
                    
            # 顯示原始新聞連結
            expander_title = "閱讀最新新聞" if language == "繁體中文" else f"Read Latest {continent_name} News"
            with st.expander(expander_title):
                for item in re_news_items:
                    title_text = translate_text(item['title'], "zh-TW") if language == "繁體中文" else item['title']
                    st.markdown(f"- **[{title_text}]({item['link']})** ({item['date']})")
        else:
            st.warning(T["no_news"])
# =========================================================
# 📰 Financial News & AI Cache System
# =========================================================
st.header(T["news_header"])

display_countries = {k: v for k, v in COUNTRY_CONFIG.items() if continent_filter == "全部" or v["洲"] == continent_filter}
tab_names = [info["en_name"] if language == "English" else info["名稱"] for info in display_countries.values()]

tabs = st.tabs(tab_names)

for tab, (code, info) in zip(tabs, display_countries.items()):
    with tab:
        news_items = get_news(info["新聞"])
        if not news_items:
            st.warning(T["no_news"])
        else:
            st.markdown(f"### {T['summary']}")
            today = datetime.date.today().strftime("%Y-%m-%d")

            with st.spinner(T["analyzing"]):
                summary = get_ai_summary(code, today, language)

            if summary:
                with st.container(border=True):
                    st.write(f"📅 {today}")
                    st.write(f"{T['focus']}：{summary['market_focus']}")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**{T['stock']}**")
                        st.info(summary["stock_outlook"])
                    with col2:
                        st.markdown(f"**{T['fx']}**")
                        st.info(summary["currency_outlook"])
                    st.markdown(f"**{T['risk']}**")
                    st.warning(summary["risk_tip"])
            else:
                st.error(T["ai_error"])

            st.divider()
            st.markdown(f"### {T['latest_news']}")
            for item in news_items:
                # Optionally translate news titles to Traditional Chinese if requested
                title_text = translate_text(item['title'], "zh-TW") if language == "繁體中文" else item['title']
                st.markdown(f"**[{title_text}]({item['link']})**\n\n⏱️ {item['date']}")

# =========================================================
# 📌 Footer
# =========================================================
st.markdown("---")
st.caption("Global Market Dashboard Pro | Built with Streamlit + yfinance + Google News")
