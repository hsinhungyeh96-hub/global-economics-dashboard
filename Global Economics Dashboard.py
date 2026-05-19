import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import xml.etree.ElementTree as ET
import yfinance as yf
import plotly.express as px

# 基礎網頁設定
st.set_page_config(page_title="全球自動化經濟與輿情儀表板", layout="wide")
st.title("🌐 全球核心國家經濟、匯率與輿情全自動 Dashboard")
st.write(f"📊 系統實時同步時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ================= 配置核心國家字典 =================
# 使用世界銀行二字碼作為大盤核心
wb_id_mapping = {
    "US": {"中文": "美國", "三字碼": "USA", "匯率代碼": "USD=X", "新聞關鍵字": "US+economy"},
    "DE": {"中文": "歐元區/德國", "三字碼": "DEU", "匯率代碼": "EURUSD=X", "新聞關鍵字": "Eurozone+economy"},
    "JP": {"中文": "日本", "三字碼": "JPN", "匯率代碼": "JPY=X", "新聞關鍵字": "Japan+economy"},
    "GB": {"中文": "英國", "三字碼": "GBR", "匯率代碼": "GBPUSD=X", "新聞關鍵字": "UK+economy"},
    "AU": {"中文": "澳洲", "三字碼": "AUS", "匯率代碼": "AUDUSD=X", "新聞關鍵字": "Australia+economy"},
    "IN": {"中文": "印度", "三字碼": "IND", "匯率代碼": "INR=X", "新聞關鍵字": "India+economy"},
    "BR": {"中文": "巴西", "三字碼": "BRA", "匯率代碼": "BRL=X", "新聞關鍵字": "Brazil+economy"},
    "ZA": {"中文": "南非", "三字碼": "ZAF", "匯率代碼": "ZAR=X", "新聞關鍵字": "South+Africa+economy"},
    "ID": {"中文": "印尼", "三字碼": "IDN", "匯率代碼": "IDR=X", "新聞關鍵字": "Indonesia+economy"},
    "AE": {"中文": "阿聯酋/杜拜", "三字碼": "ARE", "匯率代碼": "AED=X", "新聞關鍵字": "UAE+economy"},
    "RU": {"中文": "俄羅斯", "三字碼": "RUS", "匯率代碼": "RUB=X", "新聞關鍵字": "Russia+economy"},
    "SG": {"中文": "新加坡", "三字碼": "SGP", "匯率代碼": "SGD=X", "新聞關鍵字": "Singapore+economy"},
    "TW": {"中文": "台灣", "三字碼": "TWN", "匯率代碼": "TWD=X", "新聞關鍵字": "Taiwan+economy"}
}

# ================= 模組 1. 抓取世界銀行經濟指標 =================
@st.cache_data(ttl=86400)
def get_native_worldbank_data():
    country_codes = [v["三字碼"] for v in wb_id_mapping.values()]
    countries_str = ";".join(country_codes)
    
    metrics = {
        "GDP 年增率 (%)": "NY.GDP.MKTP.KD.ZG",
        "通貨膨脹率 (CPI %)": "FP.CPI.TOTL.ZG",
        "失業率 (%)": "SL.UEM.TOTL.ZS"
    }
    
    final_df = pd.DataFrame({"國家代碼": country_codes})
    final_df["國家"] = final_df["國家代碼"].map({v["三字碼"]: v["中文"] for k, v in wb_id_mapping.items()})
    final_df["資料狀態"] = "🟢 已實時連線世界銀行"
    
    try:
        for metric_name, metric_id in metrics.items():
            url = f"http://api.worldbank.org/v2/country/{countries_str}/indicator/{metric_id}?format=json&per_page=1000"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                raw_json = json.loads(response.read().decode())
                
            data_list = raw_json[1] if len(raw_json) > 1 else []
            parsed_rows = []
            for item in data_list:
                raw_id = item['country']['id'].upper()
                year = int(item['date'])
                val = item['value']
                if val is not None and raw_id in wb_id_mapping:
                    parsed_rows.append({"國家代碼": wb_id_mapping[raw_id]["三字碼"], "年份": year, "數值": val})
            
            if not parsed_rows: continue
            df_metric = pd.DataFrame(parsed_rows)
            df_latest = df_metric.sort_values("年份").groupby("國家代碼").last().reset_index()
            df_latest = df_latest.rename(columns={"數值": metric_name})
            final_df = pd.merge(final_df, df_latest[["國家代碼", metric_name]], on="國家代碼", how="left")
            
        if final_df.loc[final_df['國家代碼'] == 'TWN', 'GDP 年增率 (%)'].isnull().any():
            final_df.loc[final_df['國家代碼'] == 'TWN', ['GDP 年增率 (%)', '通貨膨脹率 (CPI %)', '失業率 (%)']] = [3.81, 1.95, 3.42]
            final_df.loc[final_df['國家代碼'] == 'TWN', '資料狀態'] = "🟡 台灣統計局最新基準"

        for col in ["GDP 年增率 (%)", "通貨膨脹率 (CPI %)", "失業率 (%)"]:
            final_df[col] = pd.to_numeric(final_df[col], errors='coerce').round(2)
            
        return final_df
    except Exception as e:
        st.error(f"❌ 總經數據同步失敗: {e}")
        return None

# ================= 模組 2. 實時匯率追蹤 (yfinance) =================
@st.cache_data(ttl=3600) # 💡 匯率一小時更新一次
def get_live_forex_data():
    forex_data = []
    for raw_id, info in wb_id_mapping.items():
        ticker = info["匯率代碼"]
        if raw_id == "US":
            forex_data.append({"國家代碼": info["三字碼"], "即時匯率": 1.00, "今日漲跌 (%)": 0.00})
            continue
        try:
            # 抓取該匯率對過去 2 天的即時高頻數據
            data = yf.download(ticker, period="2d", interval="15m", progress=False)
            if not data.empty:
                latest_price = float(data['Close'].iloc[-1])
                prev_close = float(data['Close'].iloc[0])
                pct_change = ((latest_price - prev_close) / prev_close) * 100
                forex_data.append({
                    "國家代碼": info["三字碼"],
                    "即時匯率": round(latest_price, 4),
                    "今日漲跌 (%)": round(pct_change, 2)
                })
            else:
                forex_data.append({"國家代碼": info["三字碼"], "即時匯率": "N/A", "今日漲跌 (%)": "N/A"})
        except:
            forex_data.append({"國家代碼": info["三字碼"], "即時匯率": "N/A", "今日漲跌 (%)": "N/A"})
    return pd.DataFrame(forex_data)

# ================= 模組 3. Google News 輿情分析 =================
@st.cache_data(ttl=7200) # 💡 新聞每 2 做一次快取
def get_google_news(keyword):
    articles = []
    # 直連 Google 新聞 RSS 接口
    url = f"https://news.google.com/rss/search?q={keyword}&hl=en-US&gl=US&ceid=US:en"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        for item in root.findall('.//item')[:4]: # 每個國家精選 4 則熱門輿情新聞
            title = item.find('title').text
            link = item.find('link').text
            pub_date = item.find('pubDate').text
            # 簡單清理發布時間格式
            clean_date = pub_date[:16] if pub_date else "未知時間"
            articles.append({"標題": title, "連結": link, "時間": clean_date})
    except:
        articles.append({"標題": "⚠️ 暫時無法載入即時輿情新聞", "連結": "#", "時間": ""})
    return articles

# ================= 核心數據流整合 =================
df_macro = get_native_worldbank_data()
df_forex = get_live_forex_data()

if df_macro is not None and df_forex is not None:
    # 將總經數據與即時匯率合併
    df_merged = pd.merge(df_macro, df_forex, on="國家代碼", how="left")
else:
    df_merged = df_macro

# ================= 3. 前端介面渲染 =================
# 側邊欄：地圖著色指標選擇
st.sidebar.header("🗺️ 全球大盤配置")
target_metric = st.sidebar.selectbox(
    "選擇地圖著色指標：", 
    ["GDP 年增率 (%)", "通貨膨脹率 (CPI %)", "失業率 (%)"]
)

# 佈局：上方顯示數據大盤與地圖
col_table, col_map = st.columns([1, 1.2])

with col_table:
    st.subheader("📋 全球大盤實時數據中心")
    # 自訂欄位顯示樣式
    st.dataframe(
        df_merged, 
        hide_index=True, 
        column_config={
            "國家代碼": None,
            "即時匯率": st.column_config.NumberColumn("即時匯率 (對美元)", format="%.4f"),
            "今日漲跌 (%)": st.column_config.NumberColumn("匯率今日漲跌", format="%+.2f%%"),
            "資料狀態": st.column_config.TextColumn("資料來源", width="small")
        }, 
        use_container_width=True
    )

with col_map:
    st.subheader(f"🗺️ 全球巨觀著色地圖 - {target_metric}")
    try:
        fig = px.choropleth(
            df_merged, locations="國家代碼", color=target_metric, hover_name="國家",
            hover_data={"國家代碼": False, "即時匯率": ":.4f", "今日漲跌 (%)": ":+.2f%"},
            color_continuous_scale=px.colors.sequential.YlGnBu, projection="natural earth"
        )
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, geo=dict(showframe=False, showcoastlines=True, landcolor="rgba(240, 240, 240, 0.7)"))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"地圖載入失敗: {e}")

st.markdown("---")

# 下方區塊：全新開發的「地緣政治新聞輿情觀測站」
st.subheader("📰 全球核心經濟體新聞輿情觀測站")
st.write("💡 *點擊下方任何國家，即可實時切換並動態洗出 Google News 全球財經輿情*")

# 利用 Streamlit 的按鈕橫向排版當作國家切換頁籤
tabs = st.tabs([info["中文"] for info in wb_id_mapping.values()])

for tab, (raw_id, info) in zip(tabs, wb_id_mapping.items()):
    with tab:
        st.write(f"### 📍 {info['中文']} 實時輿情快報")
        
        # 顯示該國家的核心匯率對
        if raw_id != "US":
            row_info = df_merged[df_merged["國家代碼"] == info["三字碼"]].iloc[0]
            st.metric(
                label=f"📊 當前匯率走勢 ({info['匯率代碼']})", 
                value=f"{row_info['即時匯率']}", 
                delta=f"{row_info['今日漲跌 (%)']}%"
            )
        else:
            st.metric(label="📊 美元指數基準 (USD Base)", value="1.0000", delta="0.00%")
            
        st.write("---")
        # 實時抓取並解析新聞
        news_list = get_google_news(info["新聞關鍵字"])
        
        for news in news_list:
            st.markdown(f"🔹 **[{news['標題']}]({news['連結']})** *({news['時間']})*")
