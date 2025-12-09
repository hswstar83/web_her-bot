import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

# 1. 페이지 설정 (넓게 보기)
st.set_page_config(
    page_title="작전주 헌터 대시보드",
    page_icon="📈",
    layout="wide"
)

# 2. 제목
st.title("📈 작전주 헌터 : 세력 포착 대시보드")
st.markdown("매일 **오후 3:40**, 세력의 매집 흔적이 있는 종목을 자동으로 찾아내고 추적합니다.")

# 3. 데이터 로드 함수 (캐싱)
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
    except Exception as e:
        return pd.DataFrame()

# 4. 데이터 전처리 (글자를 숫자로 변환) - 핵심 기능!
def clean_data(df):
    if df.empty: return df
    
    # 수익률(%)에서 '%' 기호 빼고 숫자로 변환
    if '수익률(%)' in df.columns:
        # 빈칸이나 에러값 처리
        df['수익률_숫자'] = df['수익률(%)'].astype(str).str.replace('%', '').str.replace(',', '')
        df['수익률_숫자'] = pd.to_numeric(df['수익률_숫자'], errors='coerce').fillna(0)

    # 현재가에서 ',' 기호 빼고 숫자로 변환
    if '현재가(Live)' in df.columns:
        df['현재가_숫자'] = df['현재가(Live)'].astype(str).str.replace(',', '').str.replace('코드확인', '0')
        df['현재가_숫자'] = pd.to_numeric(df['현재가_숫자'], errors='coerce').fillna(0)
        
    return df

# 5. 스타일링 함수 (빨강/파랑 색칠하기)
def color_profit(val):
    color = 'black'
    if val > 0: color = 'red'    # 수익이면 빨강
    elif val < 0: color = 'blue' # 손실이면 파랑
    return f'color: {color}; font-weight: bold;'

# --- 메인 화면 로직 ---

if st.button('🔄 데이터 새로고침'):
    st.cache_data.clear()

raw_df = load_data()

if raw_df is not None and not raw_df.empty:
    # 데이터 다듬기
    df = clean_data(raw_df)

    # 최신순 정렬
    if '탐색일' in df.columns:
        df = df.sort_values(by='탐색일', ascending=False)

    # 📊 상단 요약 지표 (Metrics)
    col1, col2, col3 = st.columns(3)
    
    total_count = len(df)
    # 오늘 날짜 종목 수 계산 (탐색일 기준)
    # 날짜 형식이 'YYYY-MM-DD'라고 가정
    latest_date = df['탐색일'].iloc[0]
    today_count = len(df[df['탐색일'] == latest_date])
    
    # 전체 평균 수익률
    avg_profit = df['수익률_숫자'].mean()

    col1.metric("총 포착 종목", f"{total_count}개", f"최근: {latest_date}")
    col2.metric("오늘 발견", f"{today_count}개")
    col3.metric("평균 수익률", f"{avg_profit:.2f}%", delta_color="normal")

    st.divider() # 구분선

    # 📋 메인 테이블 보여주기
    # 사용자에게 보여줄 컬럼만 선택
    display_cols = ['탐색일', '종목명', '코드', '시장', '포착가', '현재가(Live)', '수익률(%)', '거래량급증']
    
    # 실제 존재하는 컬럼만 필터링
    valid_cols = [c for c in display_cols if c in df.columns]
    
    st.subheader("📋 포착 종목 리스트")
    
    # 스타일 적용해서 보여주기
    # (수익률_숫자 컬럼을 기준으로 색깔을 정하고, 보여주는 건 수익률(%) 컬럼임)
    st.dataframe(
        df[valid_cols].style.applymap(
            lambda x: color_profit(float(str(x).replace('%','').replace(',','')) if str(x).replace('%','').replace(',','').replace('.','',1).replace('-','',1).isdigit() else 0),
            subset=['수익률(%)']
        ),
        use_container_width=True,
        hide_index=True,
        height=600 # 표 높이 고정
    )

else:
    st.warning("데이터가 없거나 로딩 중입니다.")
    st.info("구글 시트에 데이터가 있는지 확인해주세요.")
