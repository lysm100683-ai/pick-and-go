# 1_여행조건입력부.py
# =========================================================
# 📌 [Frontend] 상세 여행 조건 입력 및 서버 요청 담당
# =========================================================
import streamlit as st
import requests
from datetime import date, timedelta
import json
from typing import List

# 1. 페이지 설정
st.set_page_config(page_title="Pick&Go (Client Mode)", page_icon="✈️", layout="wide")

# 2. FastAPI 서버 주소
BASE_API_URL = "http://127.0.0.1:8000/api/v1"
GENERATE_API_URL = f"{BASE_API_URL}/generate"
# DB 업데이트 API URL 복구
UPDATE_DB_API_URL = f"{BASE_API_URL}/update-db" 

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
        "style": ["휴양", "관광"], "transport": ["항공"], 
        "local_transport": "자차",
        "pace": "보통", "walk_minutes": 45,
        "lodging_types": ["호텔"], "star_rating": 4, "price_per_night_manwon": 20,
        "num_hotels": 1, # 희망 숙소 수
        
        # 음식 및 편의
        "food_prefs": [], "food_allergy_text": "",
        "with_kids": False, "stroller": False, "barrier_free": False, "photo_spot": False,
        
        # Step 3: 고급 설정
        "keywords": "", "seat_pref": "무관", "baggage": "기내만", "english_ok": False,
        
        # 누락 방지용 기본값
        "crowd_avoid": "보통", "temp_range": (15,25), "rainy_ok": False, 
        "time_constraints": "", "max_transfers": 1, "visa_free": False
    }

# 4. 여행 조건 입력 폼
st.title("✈️ Pick&Go: AI 여행 일정 추천")
st.markdown("---")

# 🚀 NEW: 여행 일수 계산 (max_value 안정성 확보)
try:
    num_days = (st.session_state["form_data"]["end_date"] - st.session_state["form_data"]["start_date"]).days
    max_hotels = num_days if num_days > 0 else 1
except:
    max_hotels = 1
    
with st.form("travel_form"):
    
    # --- Step 1: 기본 정보 ---
    st.header("1. 기본 정보")
    col1, col2, col3 = st.columns(3)
    dep = col1.text_input("출발 도시", st.session_state["form_data"]["dep_city"])
    dest = col2.text_input("여행 도시 (목적지)", st.session_state["form_data"]["dest_city"])
    people = col3.number_input("인원 (명)", 1, 10, st.session_state["form_data"]["people"])

    col4, col5 = st.columns(2)
    s_date = col4.date_input("출발일", st.session_state["form_data"]["start_date"])
    e_date = col5.date_input("종료일", st.session_state["form_data"]["end_date"])
    
    companions = st.multiselect("동행인", ["가족", "커플", "친구", "나홀로", "반려동물"], st.session_state["form_data"]["companions"])
    
    budget_options = ["저", "중", "고"]
    budget_level = st.select_slider("예산 수준", budget_options, value=st.session_state["form_data"]["budget_level"])
    st.markdown("---")

    # --- Step 2: 상세 취향 ---
    st.header("2. 상세 취향 및 조건")
    
    col6, col7, col8 = st.columns(3)
    
    style = col6.multiselect("선호하는 여행 스타일", ["휴양", "관광", "맛집", "쇼핑", "액티비티", "자연", "문화"], st.session_state["form_data"]["style"])
    transport = col7.multiselect("주요 이동 수단 (출발/도착)", ["항공", "기차", "버스", "자차"], st.session_state["form_data"]["transport"])
    
    pace_options = ["여유", "보통", "빡빡"]
    pace = col8.radio(
        "선호하는 일정 강도", 
        pace_options, 
        index=pace_options.index(st.session_state["form_data"]["pace"]),
        horizontal=True
    )

    local_transport_options = ["렌트카", "자차", "대중교통"]
    local_transport = st.radio(
        "여행지 내 이동 수단", 
        local_transport_options, 
        index=local_transport_options.index(st.session_state["form_data"]["local_transport"]),
        horizontal=True,
        help="여행지 내에서 장소 간 이동 시 이용할 교통수단입니다. 이동 시간 계산에 반영됩니다."
    )
    st.divider()

    # 숙소 조건
    st.subheader("숙소 조건")
    col9, col10, col11 = st.columns(3)
    lodging_types = col9.multiselect("숙소 종류", ["호텔", "리조트", "펜션", "에어비앤비"], st.session_state["form_data"]["lodging_types"])
    star_rating = col10.slider("별점 (최소)", 1, 5, st.session_state["form_data"]["star_rating"])
    price_per_night = col11.number_input("1박 예산 (만원, 최대)", 1, 100, st.session_state["form_data"]["price_per_night_manwon"])
    
    # 🚀 2-1. 숙소 개수 입력 (값이 유지되도록 로직 수정)
    num_hotels_input = st.number_input(
        "희망하는 숙소 수 (전체 일정 중)", 
        min_value=1, 
        max_value=max_hotels, 
        value=st.session_state["form_data"]["num_hotels"], 
        help="1박마다 숙소를 변경하고 싶다면 전체 일자 수와 동일하게 입력하세요. 기본값은 1개(고정 숙소)입니다."
    )
    st.divider()

    # 기타 상세 조건
    st.subheader("기타 상세 조건")
    col12, col13, col14 = st.columns(3)
    with_kids = col12.checkbox("어린이 동반", st.session_state["form_data"]["with_kids"])
    stroller = col13.checkbox("유모차 사용 필요", st.session_state["form_data"]["stroller"])
    photo_spot = col14.checkbox("사진 명소 선호", st.session_state["form_data"]["photo_spot"])
    
    # --- Step 3: 고급 설정 (생략 가능) ---
    with st.expander("3. 고급 설정 (선택 사항)"):
        keywords = st.text_input("추가 키워드", st.session_state["form_data"]["keywords"])
        
        col_adv1, col_adv2, col_adv3 = st.columns(3)
        
        seat_options = ["무관", "창가", "통로"]
        seat_pref = col_adv1.selectbox(
            "항공/기차 좌석 선호", 
            seat_options, 
            index=seat_options.index(st.session_state["form_data"]["seat_pref"])
        )
        
        baggage_options = ["기내만", "위탁 포함"]
        baggage = col_adv2.selectbox(
            "수하물", 
            baggage_options,
            index=baggage_options.index(st.session_state["form_data"]["baggage"])
        )
        english_ok = col_adv3.checkbox("현지 영어 소통 원활 지역", st.session_state["form_data"]["english_ok"])
        
    submitted = st.form_submit_button("일정 생성 시작! (Server 전송)", use_container_width=True, type="primary")

# 5. 폼 제출 처리
if submitted:
    # (1) 데이터 정리 및 세션 저장
    updated_data = {
        "dep_city": dep, "dest_city": dest,
        "start_date": str(s_date), "end_date": str(e_date),
        "people": people, "companions": companions, "budget_level": budget_level,
        "style": style, "transport": transport, 
        "local_transport": local_transport, 
        "pace": pace, 
        "lodging_types": lodging_types, "star_rating": star_rating, "price_per_night_manwon": price_per_night,
        
        # 🚀 2-1. num_hotels_input의 최신 값을 세션에 저장하여 유지되도록 함
        "num_hotels": num_hotels_input,
        
        "food_prefs": st.session_state["form_data"]["food_prefs"], "food_allergy_text": st.session_state["form_data"]["food_allergy_text"],
        "with_kids": with_kids, "stroller": stroller, "barrier_free": st.session_state["form_data"]["barrier_free"], "photo_spot": photo_spot,
        "keywords": keywords, "seat_pref": seat_pref, "baggage": baggage, "english_ok": english_ok,
        "walk_minutes": 45, "crowd_avoid": "보통", "temp_range": (15,25), 
        "rainy_ok": False, "time_constraints": "", "max_transfers": 1, "visa_free": False
    }
    st.session_state["form_data"].update(updated_data)

    # (2) 서버 요청 (일정 생성)
    with st.spinner("📡 FastAPI 서버가 상세 조건을 분석하여 일정을 생성 중입니다..."):
        try:
            response = requests.post(GENERATE_API_URL, json=updated_data)
            
            if response.status_code == 200:
                st.session_state["api_result"] = response.json()
                st.success("✅ 일정 생성 완료!")
                st.balloons()
                st.switch_page("pages/2_일정추천출력부.py") 
            else:
                error_detail = response.json().get("detail", "알 수 없는 오류")
                st.error(f"❌ 일정 생성 실패 (Code: {response.status_code}): {error_detail}")
            
        except requests.exceptions.ConnectionError:
            st.error("❌ 서버 연결 실패: FastAPI 서버가 실행 중인지 확인해 주세요.")
        except Exception as e:
            st.error(f"❌ 예상치 못한 오류 발생: {e}")

st.markdown("---")
# 🚀 2-3. DB 업데이트 버튼 복구
if st.button("데이터베이스 업데이트 (장소 데이터 새로 수집) 🔄", type="secondary", use_container_width=True):
    st.warning("⚠️ 이 기능은 **관리자용**이며, 대량의 데이터 요청 및 처리를 유발합니다. 반드시 필요할 때만 사용하세요.")
    
    city_to_update = st.session_state["form_data"]["dest_city"]
    styles_to_update = st.session_state["form_data"]["style"]

    update_payload = {
        "dest_city": city_to_update,
        "styles": styles_to_update
    }

    with st.spinner(f"📡 '{city_to_update}'의 장소 데이터를 백그라운드에서 업데이트 요청 중..."):
        try:
            response = requests.post(UPDATE_DB_API_URL, json=update_payload)
            if response.status_code == 200:
                st.success(f"✅ DB 업데이트 요청 수락: '{city_to_update}' 장소 수집이 백그라운드에서 시작되었습니다.")
                st.info("💡 **FastAPI 서버 콘솔**에서 수집 결과를 확인하고, **일정 생성 시작** 버튼을 다시 눌러 최신 데이터를 반영하세요.")
            else:
                st.error(f"❌ DB 업데이트 요청 실패 (Code: {response.status_code}): {response.json().get('detail', '서버 오류')}")
        except requests.exceptions.ConnectionError:
            st.error("❌ 서버 연결 실패: FastAPI 서버가 실행 중인지 확인해 주세요.")
        except Exception as e:
            st.error(f"❌ 예상치 못한 오류 발생: {e}")