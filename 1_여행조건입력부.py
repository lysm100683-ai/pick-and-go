# 1_여행조건입력부.py
# =========================================================
# 📌 [Frontend] 상세 여행 조건 입력 및 서버 요청 담당
# =========================================================
import streamlit as st
import requests
from datetime import date, timedelta
import json

# 1. 페이지 설정
st.set_page_config(page_title="Pick&Go (Client Mode)", page_icon="✈️", layout="wide")

# 2. FastAPI 서버 주소
API_URL = "http://127.0.0.1:8000/api/v1/generate"

# 3. 초기 데이터 및 세션 설정
today = date.today()
default_start = today + timedelta(days=7)
default_end = today + timedelta(days=13)

if "form_data" not in st.session_state:
    st.session_state["form_data"] = {
        # Step 1: 기본 정보
        "dep_city": "서울/인천", "dest_city": "제주", 
        "start_date": default_start, "end_date": default_end,
        "people": 2, "companions": [], "budget_level": "중",
        
        # Step 2: 상세 취향
        "style": ["휴양", "관광"], "transport": ["항공"], "pace": "보통", "walk_minutes": 45,
        "lodging_types": ["호텔"], "star_rating": 4, "price_per_night_manwon": 20,
        "food_prefs": [], "food_allergy_text": "",
        "with_kids": False, "stroller": False, "barrier_free": False,
        "crowd_avoid": "보통", "temp_range": (15, 25), "rainy_ok": False, "photo_spot": False,
        
        # Step 3: 고급 옵션
        "keywords": "", "time_constraints": "",
        "seat_pref": "무관", "baggage": "기내만", "max_transfers": 1,
        "english_ok": False, "visa_free": False
    }

# 4. 헤더
st.markdown("""
<div style="text-align:center; margin-bottom: 2rem;">
    <h1 style="color:#0068c3;">✈️ Pick & Go : 맞춤 여행 일정 생성</h1>
    <p>원하는 모든 조건을 상세하게 입력하고 <b>FastAPI 고성능 서버</b>에 요청하세요!</p>
</div>
""", unsafe_allow_html=True)

# 5. 입력 폼 (전체 항목 복구)
with st.form("full_api_form"):
    
    # --- Step 1. 기본 정보 ---
    st.subheader("1. 기본 여행 정보")
    c1, c2 = st.columns(2)
    dep = c1.text_input("출발지", value=st.session_state["form_data"]["dep_city"])
    dest = c2.text_input("목적지 (도시명)", value=st.session_state["form_data"]["dest_city"])
    
    c3, c4, c5 = st.columns([1, 1, 1])
    s_date = c3.date_input("가는 날", value=st.session_state["form_data"]["start_date"])
    e_date = c4.date_input("오는 날", value=st.session_state["form_data"]["end_date"])
    people = c5.number_input("인원 수", min_value=1, max_value=10, value=st.session_state["form_data"]["people"])

    c6, c7 = st.columns(2)
    companions = c6.multiselect("동반 유형", ["커플", "가족(아동)", "친구", "혼자", "노년층"], default=st.session_state["form_data"]["companions"])
    budget_level = c7.select_slider("예산 수준", options=["저", "중", "고"], value=st.session_state["form_data"]["budget_level"])

    st.markdown("---")

    # --- Step 2. 상세 스타일 ---
    st.subheader("2. 여행 스타일 및 취향")
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        style = st.multiselect("선호 테마", ["휴양", "관광", "맛집", "쇼핑", "힐링", "액티비티", "자연"], default=st.session_state["form_data"]["style"])
        transport = st.multiselect("이동 수단", ["항공", "기차", "렌트카", "대중교통"], default=st.session_state["form_data"]["transport"])
        pace = st.radio("일정 강도", ["여유", "보통", "빡빡"], horizontal=True, index=["여유", "보통", "빡빡"].index(st.session_state["form_data"]["pace"]))
    
    with col_s2:
        lodging_types = st.multiselect("숙소 유형", ["호텔", "리조트", "펜션", "게스트하우스"], default=st.session_state["form_data"]["lodging_types"])
        star_rating = st.slider("숙소 등급 (별)", 2, 5, st.session_state["form_data"]["star_rating"])
        price_per_night = st.slider("1박 예산 (만원)", 5, 100, st.session_state["form_data"]["price_per_night_manwon"], step=5)

    st.caption("음식 및 편의 옵션")
    col_opt1, col_opt2 = st.columns(2)
    food_prefs = col_opt1.multiselect("식사 선호", ["현지식", "한식", "양식", "길거리음식", "채식"], default=st.session_state["form_data"]["food_prefs"])
    food_allergy = col_opt2.text_input("알러지/기피 음식", value=st.session_state["form_data"]["food_allergy_text"])

    c_chk1, c_chk2, c_chk3, c_chk4 = st.columns(4)
    with_kids = c_chk1.checkbox("아이 동반", value=st.session_state["form_data"]["with_kids"])
    stroller = c_chk2.checkbox("유모차 필수", value=st.session_state["form_data"]["stroller"])
    barrier_free = c_chk3.checkbox("휠체어/배리어프리", value=st.session_state["form_data"]["barrier_free"])
    photo_spot = c_chk4.checkbox("사진 명소 중요", value=st.session_state["form_data"]["photo_spot"])

    st.markdown("---")

    # --- Step 3. 고급 설정 ---
    with st.expander("Step 3. 고급 설정 (클릭해서 펼치기)"):
        keywords = st.text_area("꼭 가고 싶은 장소/키워드", value=st.session_state["form_data"]["keywords"], placeholder="예: 유니버셜 스튜디오, 야경 좋은 곳")
        
        col_adv1, col_adv2, col_adv3 = st.columns(3)
        seat_pref = col_adv1.selectbox("좌석 선호", ["무관", "창가", "통로"], index=["무관", "창가", "통로"].index(st.session_state["form_data"]["seat_pref"]))
        baggage = col_adv2.selectbox("수하물", ["기내만", "위탁 1개", "위탁 2개"], index=["기내만", "위탁 1개", "위탁 2개"].index(st.session_state["form_data"]["baggage"]))
        english_ok = col_adv3.checkbox("영어 소통 원활 지역", value=st.session_state["form_data"]["english_ok"])

    # 제출 버튼
    submitted = st.form_submit_button("🚀 맞춤 일정 생성 요청 (Server 전송)", use_container_width=True)


# 6. 로직 처리
if submitted:
    # (1) 세션 데이터 최신화
    updated_data = {
        "dep_city": dep, "dest_city": dest,
        "start_date": str(s_date), "end_date": str(e_date), # 문자열 변환
        "people": people, "companions": companions, "budget_level": budget_level,
        "style": style, "transport": transport, "pace": pace, 
        "lodging_types": lodging_types, "star_rating": star_rating, "price_per_night_manwon": price_per_night,
        "food_prefs": food_prefs, "food_allergy_text": food_allergy,
        "with_kids": with_kids, "stroller": stroller, "barrier_free": barrier_free, "photo_spot": photo_spot,
        "keywords": keywords, "seat_pref": seat_pref, "baggage": baggage, "english_ok": english_ok,
        # 누락 방지용 기본값
        "walk_minutes": 45, "crowd_avoid": "보통", "temp_range": (15,25), 
        "rainy_ok": False, "time_constraints": "", "max_transfers": 1, "visa_free": False
    }
    st.session_state["form_data"].update(updated_data)

    # (2) 서버 요청
    with st.spinner("📡 FastAPI 서버가 상세 조건을 분석하여 일정을 생성 중입니다..."):
        try:
            response = requests.post(API_URL, json=updated_data)
            
            if response.status_code == 200:
                st.session_state["api_result"] = response.json()
                st.success("일정 생성 완료!")
                st.switch_page("pages/2_일정추천출력부.py")
            else:
                st.error(f"서버 오류: {response.text}")
        except requests.exceptions.ConnectionError:
            st.error("서버 연결 실패! 터미널에서 'python -m uvicorn app.main:app --reload'를 실행해주세요.")