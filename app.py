import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(
    page_title="작전주 헌터",
    page_icon="🦅",
    layout="centered"
)

# --- 스타일(CSS) ---
st.markdown("""
    <style>
    .main-title { font-size: 1.8rem !important; color: #1E1E1E; text-align: center; font-weight: 800; margin-bottom: 5px; }
    .sub-text { font-size: 0.9rem; color: #555; text-align: center; margin-bottom: 20px; }
    .profit-badge-plus { background-color: #ffebee; color: #d32f2f; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 0.8rem; }
    .profit-badge-minus { background-color: #e3f2fd; color: #1976d2; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 0.8rem; }
    
    /* 상세 정보 텍스트 스타일 */
    .detail-info {
        font-size: 0.85rem;
        color: #444;
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 8px;
        margin-top: 8px;
        line-height: 1.6;
    }
    
    /* 요약 지표 가로 정렬 */
    .metric-container {
        display: flex;
        justify-content: space-around;
        background-color: #f8f9fa;
        padding: 15px 0;
        border-radius: 10px;
        margin-bottom: 20px;
        border: 1px solid #eee;
    }
    .metric-box { text-align: center; width: 33%; }
    .metric-label { font-size: 0.8rem; color: #666; margin-bottom: 2px; }
    .metric-value { font-size: 1.2rem; font-weight: 700; color: #333; }
    </style>
""", unsafe_allow_html=True)

# 2. 구글 시트 데이터 로드
@st.cache_data(ttl=60)
def load_data():
    try:
        json_key = os.environ.get('GOOGLE_JSON')
        if not json_key: return None
        creds_dict = json.loads(json_key)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sh = client.open("작전주_포착_로그")
        worksheet = sh.sheet1
        data = worksheet.get_all_values()
        if len(data) < 2: return pd.DataFrame()
        header = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=header)
        return df
    except:
        return pd.DataFrame()

# 3. [NEW] 시가총액 정보 미리 가져오기 (캐싱)
@st.cache_data(ttl=3600) # 1시간마다 갱신
def get_market_cap_data():
    try:
        # KRX 전체 상장 종목 가져오기
        stocks = fdr.StockListing('KRX')
        # 코드와 시가총액만 딕셔너리로 저장 {'005930': 400000000000, ...}
        return stocks.set_index('Code')['Marcap'].to_dict()
    except:
        return {}

# 4. 상세 분석 데이터 및 차트 데이터 가져오기
@st.cache_data(ttl=3600)
def get_stock_analysis(code):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=100) # 60일선과 박스권 계산 위해 넉넉히
        df = fdr.DataReader(code, start=start_date)
        
        if len(df) < 60: return None, None
        
        # 최신 데이터
        last_row = df.iloc[-1]
        close = last_row['Close']
        volume = last_row['Volume']
        
        # 1. 거래대금 (억 원)
        amount = int((close * volume) / 100000000)
        
        # 2. 추세 (60일선)
        ma60 = df['Close'].rolling(60).mean().iloc[-1]
        trend = "60일선 위 (상승/안정)" if close >= ma60 else "60일선 아래 (하락/위험)"
        
        # 3. 에너지 응축 (최근 60일 박스권)
        df_recent = df.iloc[-60:]
        max_p = df_recent['Close'].max()
        min_p = df_recent['Close'].min()
        box_range = ((max_p - min_p) / min_p) * 100
        
        # 차트용 데이터 (최근 30일)
        chart_data = df['Close'].tail(30)
        
        return chart_data, {
            'amount': amount,
            'trend': trend,
            'box_range': box_range
        }
    except:
        return None, None

# 5. 줌인 차트 함수
def plot_sparkline(data, color_hex):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data.index, y=data.values, mode='lines', 
        line=dict(color=color_hex, width=2), hoverinfo='y'
    ))
    min_val = data.min()
    max_val = data.max()
    padding = (max_val - min_val) * 0.1 
    fig.update_layout(
        showlegend=False, margin=dict(l=0, r=0, t=0, b=0),
        height=80, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(visible=False), 
        yaxis=dict(visible=False, range=[min_val - padding, max_val + padding]) 
    )
    return fig

def clean_data(df):
    if df.empty: return df
    if '수익률(%)' in df.columns:
        df['수익률_숫자'] = df['수익률(%)'].astype(str).str.replace('%', '').str.replace(',', '')
        df['수익률_숫자'] = pd.to_numeric(df['수익률_숫자'], errors='coerce').fillna(0)
    if '현재가(Live)' in df.columns:
        df['현재가_표시'] = df['현재가(Live)'].astype(str).str.replace('코드확인', '-')
    return df

# --- 메인 화면 ---

st.markdown('<div class="main-title">🦅 작전주 헌터 대시보드</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">세력의 매집 흔적과 추세를 추적합니다</div>', unsafe_allow_html=True)

# 새로고침
col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
with col_btn2:
    if st.button('🔄 최신 데이터 새로고침', use_container_width=True):
        st.cache_data.clear()

raw_df = load_data()
marcap_dict = get_market_cap_data() # 시가총액 데이터 미리 로드

if raw_df is not None and not raw_df.empty:
    df = clean_data(raw_df)
    if '탐색일' in df.columns:
        df = df.sort_values(by='탐색일', ascending=False)

    total = len(df)
    today_cnt = len(df[df['탐색일'] == df['탐색일'].iloc[0]])
    last_update = df['탐색일'].iloc[0][5:]

    st.markdown(f"""
        <div class="metric-container">
            <div class="metric-box">
                <div class="metric-label">총 포착</div>
                <div class="metric-value">{total}건</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">오늘 발견</div>
                <div class="metric-value">{today_cnt}건</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">업데이트</div>
                <div class="metric-value">{last_update}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.subheader("📋 포착 종목 리스트")
    
    for index, row in df.iterrows():
        profit = row['수익률_숫자']
        profit_str = row['수익률(%)']
        price = row['현재가_표시']
        code = row['코드'].replace("'", "")
        
        try:
            price_fmt = f"{int(str(price).replace(',','')): ,}원"
        except:
            price_fmt = price

        badge_class = "profit-badge-plus" if profit >= 0 else "profit-badge-minus"
        
        # 상세 데이터 계산 (웹에서 즉석 계산)
        chart_data, analysis = get_stock_analysis(code)
        
        # 시가총액 가져오기 (없으면 0)
        marcap_val = marcap_dict.get(code, 0)
        marcap_str = f"{int(marcap_val / 100000000):,}억원" if marcap_val > 0 else "정보없음"

        with st.container(border=True):
            col_info, col_chart = st.columns([1.8, 1.2])
            
            with col_info:
                st.markdown(f"**{row['종목명']}** <span style='color:#888; font-size:0.8em;'>({code})</span> <span class='{badge_class}'>{profit_str}</span>", unsafe_allow_html=True)
                st.markdown(f"<div style='margin-top:5px; font-size:0.95em; font-weight:bold;'>{price_fmt}</div>", unsafe_allow_html=True)
                st.caption(f"{row['탐색일']} 포착")
                st.markdown(f"<div style='color:#666; font-size:0.8em;'>{row['거래량급증']}</div>", unsafe_allow_html=True)
            
            with col_chart:
                if chart_data is not None and not chart_data.empty:
                    color_hex = '#d32f2f' if profit >= 0 else '#1976d2'
                    fig = plot_sparkline(chart_data, color_hex)
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                else:
                    st.caption("차트 로딩 실패")
            
            # 🌟 [NEW] 상세 정보 섹션 (회색 박스)
            if analysis:
                st.markdown(f"""
                <div class="detail-info">
                • <b>시가총액:</b> {marcap_str}<br>
                • <b>오늘대금:</b> {analysis['amount']:,}억원<br>
                • <b>추세확인:</b> {analysis['trend']}<br>
                • <b>에너지응축:</b> 60일 박스권 {analysis['box_range']:.1f}% 이내
                </div>
                """, unsafe_allow_html=True)

    with st.expander("📊 전체 데이터 엑셀형태로 보기"):
        st.dataframe(df, use_container_width=True, hide_index=True)

else:
    st.info("데이터를 불러오는 중입니다... (잠시 후 다시 시도해주세요)")
