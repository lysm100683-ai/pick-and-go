#AIzaSyBSUlwmT1xz92dekaV7t-2q75xul8j0Ol8 구글 api 키
import streamlit as st
from datetime import date, timedelta
from typing import Dict, Any

# 1. 페이지 설정
st.set_page_config(
    page_title="픽앤고트래블 | 맞춤형 여행 서비스 시스템",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 2. CSS 스타일
CUSTOM_CSS = '''
<style>
html, body, [class*="css"]  { font-size: 16px; }
.hero-wrap{ text-align:center; padding: 1.6rem 0 1.0rem 0; }
.hero-moto{ font-weight: 700; font-size: 1.15rem; color: #14447a; letter-spacing: 0.02rem; }
.hero-title{ font-weight: 800; font-size: 2.0rem; margin-top: 0.35rem; }
.brand{ display:inline-block; margin-top: 0.2rem; padding: 6px 12px; border-radius: 10px; background: #eef5ff; color: #0b5ed7; font-weight: 700; }
.box{ border: 1px solid #e7ebf0; border-radius: 14px; padding: 18px; background: white; box-shadow: 0 2px 10px rgba(10, 49, 97, 0.03); }
.small-note{ color:#5a6b7b; font-size: 0.92rem; }
.fixed-cta{ position: sticky; top: 0; background: rgba(255,255,255,0.9); padding: 8px 0; z-index: 9; }
</style>
'''
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# 3. 헤더 영역
st.markdown(
    '''
    <div class="hero-wrap">
        <div class="brand">픽앤고트래블 Pick&Go Travel</div>
        <div class="hero-moto">내가 원하는 조건의 여행을 하자!</div>
        <div class="hero-title">맞춤형 여행 서비스 시스템</div>
    </div>
    ''',
    unsafe_allow_html=True
)

# 4. 모드 선택 및 기본 날짜 설정
mode = st.segmented_control("입력 방식 선택", options=["단계형(Stepper)", "일괄형(One-page)"], default="단계형(Stepper)")

today = date.today()
default_start = today + timedelta(days=7)
default_end = today + timedelta(days=13)

# 5. 데이터 저장소 초기화
if "form_data" not in st.session_state:
    st.session_state["form_data"] = {
        "dep_city": "", "dest_city": "", 
        "start_date": str(default_start), "end_date": str(default_end),
        "people": 2, "companions": [], "budget_level": "중",
        "style": ["휴양", "관광"], "transport": ["항공"], "pace": "보통", "walk_minutes": 45,
        "lodging_types": ["호텔"], "star_rating": 4, "price_per_night_manwon": 20,
        "food_prefs": [], "food_allergy_text": "",
        "with_kids": False, "stroller": False, "barrier_free": False,
        "crowd_avoid": "보통", "temp_range": (15, 25), "rainy_ok": False, "photo_spot": False,
        "keywords": "", "time_constraints": "",
        "seat_pref": "무관", "baggage": "기내만", "max_transfers": 1,
        "english_ok": False, "visa_free": False, "agree": False
    }

# --- 함수 정의 ---

def validate_and_render(data: Dict[str, Any]):
    """데이터 검증 및 저장 함수"""
    errors = []
    if not data["dep_city"].strip(): errors.append("출발 도시/공항은 필수입니다.")
    if not data["dest_city"].strip(): errors.append("도착 도시/국가는 필수입니다.")
    if data["end_date"] <= data["start_date"]: errors.append("도착일은 출발일 이후여야 합니다.")
    if not (1 <= data["people"] <= 10): errors.append("인원 수는 1~10 사이여야 합니다.")
    if not data["agree"]: errors.append("추천받기 동의에 체크해주세요.")

    free_texts = {
        "dep_city": data["dep_city"],
        "dest_city": data["dest_city"],
        "food_allergy_text": data.get("food_allergy_text",""),
        "keywords": data.get("keywords",""),
        "time_constraints": data.get("time_constraints",""),
    }
    total = sum(len(str(v).strip()) for v in free_texts.values())
    if total > 1000:
        errors.append("자유 입력 텍스트 총합이 1000자를 초과했습니다.")

    if errors:
        for e in errors: st.error(e)
        st.stop() # 에러가 있으면 여기서 멈춤 (페이지 이동 안 함)

    # 검증 통과 시 데이터 저장
    st.session_state["form_data"] = data
    
    # 파일로도 저장 (로그 남기기 용도)
    import json, os, time
    os.makedirs("out", exist_ok=True)
    fname = f"out/conditions_{int(time.time())}.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 성공 메시지는 페이지 이동 때문에 찰나에만 보일 수 있음
    st.success("조건이 확인되었습니다. 결과 페이지로 이동합니다...")

def render_onepage():
    """일괄형(One-page) 입력 폼"""
    st.markdown('<div class="fixed-cta box"><b>한 번에 조건을 선택하세요.</b></div>', unsafe_allow_html=True)
    with st.form("onepage_form", clear_on_submit=False):
        st.markdown('<div class="box">', unsafe_allow_html=True)
        st.subheader("Step 1. 기본 정보", divider="gray")
        col1, col2 = st.columns(2)
        with col1:
            dep_city = st.text_input("출발 도시/공항 *", placeholder="예: 서울/인천")
        with col2:
            dest_city = st.text_input("도착 도시/국가 *", placeholder="예: 바르셀로나, 스페인")

        c3, c4, c5 = st.columns([1,1,1])
        with c3:
            start_date = st.date_input("출발일 *", value=default_start)
        with c4:
            end_date = st.date_input("도착일 *", value=default_end)
        with c5:
            people = st.number_input("인원 수 *", min_value=1, max_value=10, value=2, step=1)

        companions = st.multiselect("동반 유형", ["커플", "가족(아동)", "친구", "혼자", "노년층"])
        budget_level = st.radio("예산 수준", ["저", "중", "고"], horizontal=True, index=1)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="box">', unsafe_allow_html=True)
        st.subheader("Step 2. 선호/제약", divider="gray")
        style = st.multiselect("선호 스타일", ["휴양", "관광", "맛집", "쇼핑", "자연", "액티비티"], default=["휴양", "관광"])
        transport = st.multiselect("이동 수단 선호", ["항공", "기차", "배", "렌트카", "버스"], default=["항공"])
        pace = st.radio("일정 밀도", ["여유", "보통", "빡빡"], horizontal=True, index=1)
        walk_minutes = st.slider("도보 허용 시간(분)", min_value=10, max_value=120, value=45, step=5)

        lodging_types = st.multiselect("숙소 유형", ["호텔", "리조트", "아파트", "게스트하우스"], default=["호텔"])
        col_lodge1, col_lodge2 = st.columns(2)
        with col_lodge1:
            star_rating = st.slider("숙소 등급(별)", min_value=2, max_value=5, value=4)
        with col_lodge2:
            price_per_night = st.slider("1박 예산(만원)", min_value=5, max_value=100, value=20, step=5)

        food_prefs = st.multiselect("음식 선호/제약(선호)", ["미식", "현지식", "할랄", "채식"])
        food_allergy_text = st.text_input("알러지/제약(자유 입력)")

        col_acc1, col_acc2, col_acc3 = st.columns(3)
        with col_acc1: with_kids = st.checkbox("아이 동반")
        with col_acc2: stroller = st.checkbox("유모차 필요")
        with col_acc3: barrier_free = st.checkbox("무장애(배리어프리)")

        crowd_avoid = st.radio("혼잡도 기피", ["낮음", "보통", "상관없음"], horizontal=True, index=1)

        col_w1, col_w2 = st.columns(2)
        with col_w1: temp_range = st.slider("선호 온도(°C)", min_value=-10, max_value=40, value=(15, 25))
        with col_w2: rainy_ok = st.checkbox("우천 시 대체 활동 허용")

        photo_spot = st.checkbox("SNS/사진 포인트 선호")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="box">', unsafe_allow_html=True)
        st.subheader("Step 3. 고급 옵션(선택)", divider="gray")
        keywords = st.text_area("방문 희망 명소/음식점 키워드 (콤마 또는 줄바꿈으로 구분)", height=100, placeholder="예: 사그라다 파밀리아, 고딕지구, 타파스")
        time_constraints = st.text_input("일정 고정/금지 시간대 (예: 오전 휴식, 21시 이후 활동 금지)")

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1: seat_pref = st.selectbox("항공 좌석 선호", ["무관", "창가", "통로"])
        with col_f2: baggage = st.selectbox("수하물", ["기내만", "위탁 1개", "위탁 2개"])
        with col_f3: max_transfers = st.slider("환승 최대 횟수", min_value=0, max_value=3, value=1)

        col_lv1, col_lv2 = st.columns(2)
        with col_lv1: english_ok = st.checkbox("영어 통용 우선")
        with col_lv2: visa_free = st.checkbox("비자프리 우선")
        st.markdown('</div>', unsafe_allow_html=True)

        agree = st.checkbox("위 조건으로 추천받기 동의 *")
        submitted = st.form_submit_button("추천 일정 보기", use_container_width=True)

    if submitted:
        data = {
            "dep_city": dep_city, "dest_city": dest_city,
            "start_date": str(start_date), "end_date": str(end_date),
            "people": int(people), "companions": companions, "budget_level": budget_level,
            "style": style, "transport": transport, "pace": pace, "walk_minutes": int(walk_minutes),
            "lodging_types": lodging_types, "star_rating": int(star_rating), "price_per_night_manwon": int(price_per_night),
            "food_prefs": food_prefs, "food_allergy_text": food_allergy_text,
            "with_kids": with_kids, "stroller": stroller, "barrier_free": barrier_free,
            "crowd_avoid": crowd_avoid, "temp_range": temp_range, "rainy_ok": rainy_ok, "photo_spot": photo_spot,
            "keywords": keywords, "time_constraints": time_constraints,
            "seat_pref": seat_pref, "baggage": baggage, "max_transfers": int(max_transfers),
            "english_ok": english_ok, "visa_free": visa_free, "agree": agree,
        }
        validate_and_render(data)
        # 일괄형에서도 제출 시 이동
        st.switch_page("pages/2_일정추천출력부.py")

def render_stepper():
    """단계형(Stepper) 입력 폼"""
    if "step" not in st.session_state:
        st.session_state["step"] = 1
    step = st.session_state["step"]

    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.progress(step/3.0, text=f"진행도: Step {step} / 3")
    st.subheader(f"Step {step}", divider="gray")

    # --- Step 1 ---
    if step == 1:
        fd = st.session_state["form_data"]
        
        st.text_input("출발 도시/공항 *", value=fd["dep_city"], placeholder="예: 서울/인천", key="dep_city_s")
        st.text_input("도착 도시/국가 *", value=fd["dest_city"], placeholder="예: 바르셀로나, 스페인", key="dest_city_s")
        
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            try: d_start = date.fromisoformat(fd["start_date"])
            except: d_start = default_start
            st.date_input("출발일 *", value=d_start, key="start_s")
        with col2:
            try: d_end = date.fromisoformat(fd["end_date"])
            except: d_end = default_end
            st.date_input("도착일 *", value=d_end, key="end_s")
        with col3:
            st.number_input("인원 수 *", min_value=1, max_value=10, value=fd["people"], step=1, key="people_s")

        st.multiselect("동반 유형", ["커플", "가족(아동)", "친구", "혼자", "노년층"], default=fd["companions"], key="companions_s")
        
        b_opts = ["저", "중", "고"]
        b_idx = b_opts.index(fd["budget_level"]) if fd["budget_level"] in b_opts else 1
        st.radio("예산 수준", b_opts, horizontal=True, index=b_idx, key="budget_s")

        if st.button("다음 →"):
            errs = []
            if not st.session_state["dep_city_s"].strip(): errs.append("출발 도시를 입력하세요.")
            if not st.session_state["dest_city_s"].strip(): errs.append("도착 도시/국가를 입력하세요.")
            if st.session_state["end_s"] <= st.session_state["start_s"]: errs.append("도착일은 출발일 이후여야 합니다.")
            
            if errs:
                for e in errs: st.error(e)
            else:
                st.session_state["form_data"].update({
                    "dep_city": st.session_state["dep_city_s"],
                    "dest_city": st.session_state["dest_city_s"],
                    "start_date": str(st.session_state["start_s"]),
                    "end_date": str(st.session_state["end_s"]),
                    "people": st.session_state["people_s"],
                    "companions": st.session_state["companions_s"],
                    "budget_level": st.session_state["budget_s"],
                })
                st.session_state["step"] = 2
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # --- Step 2 ---
    elif step == 2:
        fd = st.session_state["form_data"]
        
        st.multiselect("선호 스타일", ["휴양", "관광", "맛집", "쇼핑", "자연", "액티비티"], default=fd["style"], key="style_s")
        st.multiselect("이동 수단 선호", ["항공", "기차", "배", "렌트카", "버스"], default=fd["transport"], key="transport_s")
        
        p_opts = ["여유", "보통", "빡빡"]
        p_idx = p_opts.index(fd["pace"]) if fd["pace"] in p_opts else 1
        st.radio("일정 밀도", p_opts, horizontal=True, index=p_idx, key="pace_s")
        
        st.slider("도보 허용 시간(분)", min_value=10, max_value=120, value=fd["walk_minutes"], step=5, key="walk_s")

        st.multiselect("숙소 유형", ["호텔", "리조트", "아파트", "게스트하우스"], default=fd["lodging_types"], key="lodging_s")
        col_l1, col_l2 = st.columns(2)
        with col_l1: st.slider("숙소 등급(별)", min_value=2, max_value=5, value=fd["star_rating"], key="star_s")
        with col_l2: st.slider("1박 예산(만원)", min_value=5, max_value=100, value=fd["price_per_night_manwon"], step=5, key="price_s")

        st.multiselect("음식 선호/제약(선호)", ["미식", "현지식", "할랄", "채식"], default=fd["food_prefs"], key="food_prefs_s")
        st.text_input("알러지/제약(자유 입력)", value=fd["food_allergy_text"], key="food_allergy_s")

        col_acc1, col_acc2, col_acc3 = st.columns(3)
        with col_acc1: st.checkbox("아이 동반", value=fd["with_kids"], key="kids_s")
        with col_acc2: st.checkbox("유모차 필요", value=fd["stroller"], key="stroller_s")
        with col_acc3: st.checkbox("무장애(배리어프리)", value=fd["barrier_free"], key="bf_s")

        c_opts = ["낮음", "보통", "상관없음"]
        c_idx = c_opts.index(fd["crowd_avoid"]) if fd["crowd_avoid"] in c_opts else 1
        st.radio("혼잡도 기피", c_opts, horizontal=True, index=c_idx, key="crowd_s")

        col_w1, col_w2 = st.columns(2)
        with col_w1: st.slider("선호 온도(°C)", min_value=-10, max_value=40, value=fd["temp_range"], key="temp_s")
        with col_w2: st.checkbox("우천 시 대체 활동 허용", value=fd["rainy_ok"], key="rainy_s")

        st.checkbox("SNS/사진 포인트 선호", value=fd["photo_spot"], key="photo_s")

        colb1, colb2 = st.columns(2)
        with colb1:
            if st.button("← 이전"):
                st.session_state["step"] = 1
                st.rerun()
        with colb2:
            if st.button("다음 →"):
                st.session_state["form_data"].update({
                    "style": st.session_state["style_s"],
                    "transport": st.session_state["transport_s"],
                    "pace": st.session_state["pace_s"],
                    "walk_minutes": st.session_state["walk_s"],
                    "lodging_types": st.session_state["lodging_s"],
                    "star_rating": st.session_state["star_s"],
                    "price_per_night_manwon": st.session_state["price_s"],
                    "food_prefs": st.session_state["food_prefs_s"],
                    "food_allergy_text": st.session_state["food_allergy_s"],
                    "with_kids": st.session_state["kids_s"],
                    "stroller": st.session_state["stroller_s"],
                    "barrier_free": st.session_state["bf_s"],
                    "crowd_avoid": st.session_state["crowd_s"],
                    "temp_range": st.session_state["temp_s"],
                    "rainy_ok": st.session_state["rainy_s"],
                    "photo_spot": st.session_state["photo_s"],
                })
                st.session_state["step"] = 3
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # --- Step 3 ---
    elif step == 3:
        fd = st.session_state["form_data"]
        
        st.text_area("방문 희망 명소/음식점 키워드 (콤마 또는 줄바꿈)", height=100, value=fd["keywords"], key="keywords_s")
        st.text_input("일정 고정/금지 시간대", value=fd["time_constraints"], key="time_const_s")

        col_f1, col_f2, col_f3 = st.columns(3)
        s_opts = ["무관", "창가", "통로"]
        s_idx = s_opts.index(fd["seat_pref"]) if fd["seat_pref"] in s_opts else 0
        with col_f1: st.selectbox("항공 좌석 선호", s_opts, index=s_idx, key="seat_s")
        
        bg_opts = ["기내만", "위탁 1개", "위탁 2개"]
        bg_idx = bg_opts.index(fd["baggage"]) if fd["baggage"] in bg_opts else 0
        with col_f2: st.selectbox("수하물", bg_opts, index=bg_idx, key="bag_s")
        
        with col_f3: st.slider("환승 최대 횟수", min_value=0, max_value=3, value=fd["max_transfers"], key="transfer_s")

        col_lv1, col_lv2 = st.columns(2)
        with col_lv1: st.checkbox("영어 통용 우선", value=fd["english_ok"], key="eng_s")
        with col_lv2: st.checkbox("비자프리 우선", value=fd["visa_free"], key="visa_s")

        st.checkbox("위 조건으로 추천받기 동의 *", value=fd["agree"], key="agree_s")

        colb1, colb2 = st.columns(2)
        with colb1:
            if st.button("← 이전"):
                st.session_state["step"] = 2
                st.rerun()
        with colb2:
            if st.button("제출"):
                # 1. 마지막 데이터 업데이트
                st.session_state["form_data"].update({
                    "keywords": st.session_state["keywords_s"],
                    "time_constraints": st.session_state["time_const_s"],
                    "seat_pref": st.session_state["seat_s"],
                    "baggage": st.session_state["bag_s"],
                    "max_transfers": st.session_state["transfer_s"],
                    "english_ok": st.session_state["eng_s"],
                    "visa_free": st.session_state["visa_s"],
                    "agree": st.session_state["agree_s"],
                })
                
                # 2. 검증 (실패 시 멈춤)
                validate_and_render(st.session_state["form_data"])
                
                # 3. 페이지 이동 (파일 이름 정확해야 함)
                st.switch_page("pages/2_일정추천출력부.py")
        st.markdown('</div>', unsafe_allow_html=True)

# 메인 실행 로직
with st.container():
    c1, c2, c3 = st.columns([1, 2.8, 1])
    with c2:
        if mode.startswith("단계형"):
            render_stepper()
        else:
            render_onepage()