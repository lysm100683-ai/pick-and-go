# travel_logic.py
import sys
import os
import math
import random
import concurrent.futures 
from datetime import date, timedelta, datetime, time

# [경로 설정] backend.py 위치 찾기 (상위 폴더)d
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# --- 설정값 ---
# 📌 권장 체류 시간 (초 단위)
VISIT_TIMES = {
    "sight": 2.5 * 3600,  # 관광지 2.5시간
    "food": 1.5 * 3600,   # 식사 1.5시간
    "cafe": 1.0 * 3600,   # 카페/휴식 1.0시간
    "hotel": 0.5 * 3600,  # 숙소 복귀/출발 30분
    "default": 2.0 * 3600 # 기타 2.0시간
}
LUNCH_START_RANGE = (11, 13) 
DINNER_START_RANGE = (17, 20) 

# 🚀 NEW: 테마별 Cost 가중치 및 Epsilon 정의
THEME_WEIGHTS = {
    "✨ 핵심 코스": {"W_time": 0.1, "W_score": 10, "epsilon": 0.05, "food_boost": 0, "sight_boost": 0},
    "🍽️ 식도락 & 힐링": {"W_time": 0.05, "W_score": 15, "epsilon": 0.15, "food_boost": 100, "sight_boost": 0},
    "🌿 자연 & 관광": {"W_time": 0.08, "W_score": 8, "epsilon": 0.10, "food_boost": 0, "sight_boost": 100},
    "🔥 액티브 & 핫플": {"W_time": 0.12, "W_score": 12, "epsilon": 0.08, "food_boost": 0, "sight_boost": 50},
}


def check_is_domestic(city_name):
    korean_cities = [
        "서울", "부산", "제주", "인천", "대구", "대전", "광주", "울산", "수원", "강릉", 
        "경주", "전주", "여수", "속초", "춘천", "가평", "양평", "포항", "거제", "남해", 
        "통영", "군산", "목포", "순천", "안동", "청주", "충주", "천안", "세종"
    ]
    if any(k in city_name for k in korean_cities): return True
    if "한국" in city_name or "대한민국" in city_name: return True
    return False

# --- [기능 2] 거리 계산 (Haversine) ---
def haversine_distance(lat1, lon1, lat2, lon2):
    if not (lat1 and lon1 and lat2 and lon2): return 99999
    try: lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    except: return 99999

def calculate_score(place, user_data): 
    # (로직 유지)
    style_keywords = {"휴양": ["beach","park"], "관광": ["museum","tour"], "맛집": ["food","meal"]}
    base = float(place.get('rating', 3.0)) * 10
    bonus = 0
    for style in user_data.get('style', []):
        if style in str(place.get('category')): bonus += 20
    return min(100, int(base + bonus)), user_data.get('style', [])

def make_place(time, type_name, db_row, type_key): 
    is_start_point = db_row.get('is_start_point', False)
    
    desc_content = f"{db_row['category']} | {db_row['address']}"
    if is_start_point and 'airport' in db_row.get('category', '').lower():
         desc_content = f"✈️ 여행 시작/마무리 지점: {db_row['address']}"
    elif is_start_point and type_name == "숙소 출발":
         desc_content = f"🏡 전날 숙소에서 출발합니다."
         
    return {
        "time": time, "type": type_name, "name": db_row['name'],
        "desc": desc_content,
        "lat": db_row['lat'], "lng": db_row['lng'], "url": db_row['img_url'],
        "raw_score": db_row.get('score', 80), "img": db_row['img_url'] or "https://source.unsplash.com/400x300/?travel",
        "type_key": type_key
    }

def _generate_itinerary_for_theme(theme, duration, all_sights, all_foods, all_cafes, all_hotels, airport_place, user_pace, is_korea, user_data): 
    pool_sights, pool_foods, pool_cafes = all_sights[:], all_foods[:], all_cafes[:]
    random.shuffle(pool_sights); random.shuffle(pool_foods); random.shuffle(pool_cafes)
    
    # 📌 1. 일정 강도 및 스타일에 따른 장소 개수 조절
    
    num_sights, num_foods, num_cafes = 2, 2, 0 
    
    if "액티비티" in user_data.get('style', []) or "자연" in user_data.get('style', []):
        num_sights, num_foods, num_cafes = 3, 2, 0 
    elif user_pace == "여유" or "휴양" in user_data.get('style', []):
        num_sights, num_foods, num_cafes = 1, 1, 1 
    elif user_pace == "빡빡":
        num_sights, num_foods, num_cafes = 3, 3, 1 
    
    if user_data.get('with_kids'):
        num_sights = max(1, num_sights - 1)
        num_foods = 1 
        num_cafes = 0
        
    daily_schedule = []
    
    food_slots_base = [("12:00", "식사", "food"), ("18:00", "식사", "food")]
    cafe_slot_base = [("15:30", "카페/휴식", "cafe")]

    selected_food_slots = random.sample(food_slots_base, min(num_foods, len(food_slots_base)))
    selected_cafe_slots = random.sample(cafe_slot_base, min(num_cafes, len(cafe_slot_base)))
    
    sight_time_candidates = [
        ("10:30", "관광", "sight"), ("14:30", "관광", "sight"), 
        ("16:30", "관광", "sight"), ("17:00", "관광", "sight"),
    ]

    num_pure_sight = num_sights
    selected_sight_slots = random.sample(sight_time_candidates, min(num_pure_sight, len(sight_time_candidates)))

    daily_schedule.extend(selected_sight_slots)
    daily_schedule.extend(selected_food_slots)
    daily_schedule.extend(selected_cafe_slots)
    daily_schedule.sort(key=lambda x: x[0]) 

    # 🚀 3. 교통수단에 따른 이동 모드 결정
    is_driving = '렌트카' in user_data.get('local_transport', []) or '자차' in user_data.get('local_transport', [])
    travel_mode = 'driving' if is_driving else 'transit'

    # 🚀 NEW: 테마별 가중치 및 Epsilon 설정 로드
    weights = THEME_WEIGHTS.get(theme['name'], THEME_WEIGHTS["✨ 핵심 코스"])
    W_time = weights['W_time']
    W_score = weights['W_score']
    epsilon = weights['epsilon']
    
    # 🚀 NEW: 숙소 유동화 로직
    # all_hotels에서 num_hotels만큼 랜덤하게 숙소 후보를 선택합니다.
    num_req_hotels = min(user_data.get('num_hotels', 1), len(all_hotels))
    if num_req_hotels == 0: num_req_hotels = 1
    
    # 숙소 후보를 무작위로 선택하고, 이 후보들을 반복하여 사용합니다.
    hotel_candidates = random.sample(all_hotels, num_req_hotels)
    
    # Day별로 사용할 숙소 인덱스를 미리 결정 (1일차 숙박: 1일차 종료 시, 2일차 숙박: 2일차 종료 시)
    # 총 (duration - 1)박이 필요합니다.
    # index 0: 1일차 숙박, index 1: 2일차 숙박, ...
    night_stay_hotels = [
        hotel_candidates[i % num_req_hotels] 
        for i in range(duration - 1)
    ]
    
    # 첫날 출발은 첫 숙소
    last_night_hotel = hotel_candidates[0] if hotel_candidates else None
    
    days = []
    visited_place_ids = set()

    for d in range(1, duration + 1):
        day_places = []
        last_place = None
        current_time = datetime.combine(date.today(), time(9, 0, 0)) 
        
        # 📌 Day 시작 지점 설정 (이전 날 숙소)
        if d == 1:
            # 첫날 시작: 공항 또는 첫 숙소
            if '항공' in user_data.get('transport', []) and airport_place:
                current_day_start_point = airport_place
            else:
                current_day_start_point = last_night_hotel or airport_place
            
            if current_day_start_point:
                 current_day_start_point['is_start_point'] = True
                 day_places.append(make_place(current_time.strftime("%H:%M"), "도착 지점", current_day_start_point, "hotel")) 
                 last_place = current_day_start_point
                 last_place['type_key'] = 'hotel'
                 
        elif d > 1 and last_night_hotel:
            # 중간 날 시작: 어제 숙박한 숙소 (last_night_hotel)
            current_day_start_point = last_night_hotel
            current_day_start_point['is_start_point'] = True
            day_places.append(make_place(current_time.strftime("%H:%M"), "숙소 출발", current_day_start_point, "hotel"))
            last_place = current_day_start_point
            last_place['type_key'] = 'hotel'
        
        # 🚀 1. 동적 시간 계산 및 장소 추천 루프
        for _, type_kor, type_key in daily_schedule:
            
            if type_key == "food": candidates_pool = pool_foods
            elif type_key == "cafe": candidates_pool = pool_cafes 
            elif type_key == "sight": candidates_pool = pool_sights
            else: continue 
            
            candidates = [p for p in candidates_pool if p['id'] not in visited_place_ids]
            if not candidates: continue

            # --- 동적 시간 계산 ---
            travel_duration_seconds = 0
            if last_place and last_place.get('lat') and last_place.get('lng'):
                prev_place_type_key = last_place.get('type_key', 'default')
                visit_duration_seconds = VISIT_TIMES.get(prev_place_type_key, VISIT_TIMES['default'])
                
                # 다음 장소까지의 이동 시간 (임시로 가장 가까운 후보의 좌표 사용)
                if is_korea:
                    travel_duration_seconds = backend.get_real_duration_kakao(
                        last_place['lat'], last_place['lng'], candidates[0]['lat'], candidates[0]['lng'], mode=travel_mode
                    )
                else:
                    travel_duration_seconds = backend.get_real_duration_google_bulk(
                        last_place['lat'], last_place['lng'], [candidates[0]], mode=travel_mode
                    )[0][0] 

                if travel_duration_seconds == 999999: travel_duration_seconds = 30 * 60 
                
                current_time = current_time + timedelta(seconds=visit_duration_seconds + travel_duration_seconds)
            
            # 📌 식사 시간대 강제 조정 (로직 유지)
            if type_key == "food":
                target_range = LUNCH_START_RANGE if current_time.hour < 15 else DINNER_START_RANGE
                if current_time.hour < target_range[0]:
                    current_time = current_time.replace(hour=target_range[0], minute=0, second=0)
                elif current_time.hour >= target_range[1]:
                     continue
            
            # --- 장소 최적화 및 선택 (Cost + Epsilon-Greedy) ---
            
            # 🚀 2. Epsilon-Greedy (랜덤 탐색)
            if random.random() < epsilon:
                # Epsilon 확률로 무작위 장소 선택
                selected = random.choice(candidates)
            else:
                # (1 - Epsilon) 확률로 Cost 기반 최적화 선택
                selected = candidates[0] 
                if last_place:
                    candidates.sort(key=lambda p: haversine_distance(last_place['lat'], last_place['lng'], p['lat'], p['lng']))
                    top_5 = candidates[:5]
                    
                    results = []
                    last_lat, last_lng = last_place['lat'], last_place['lng']

                    # 실제 이동 시간 조회
                    if is_korea:
                        def get_time(p): return backend.get_real_duration_kakao(last_lat, last_lng, p['lat'], p['lng'], mode=travel_mode)
                        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                            future_map = {executor.submit(get_time, p): p for p in top_5}
                            for future in concurrent.futures.as_completed(future_map):
                                p = future_map[future]
                                try: results.append((future.result(), p))
                                except: results.append((999999, p))
                    else:
                        results = backend.get_real_duration_google_bulk(last_lat, last_lng, top_5, mode=travel_mode)

                    # 🚀 1. 테마별 Cost 함수 적용 (W_time, W_score 사용)
                    final_costs = []
                    for travel_time, place in results:
                        # 🚀 테마별 부스트 적용: 식당/관광에 따라 점수 임시 가산
                        boost = 0
                        if type_key == 'food': boost = weights.get('food_boost', 0)
                        elif type_key == 'sight': boost = weights.get('sight_boost', 0)
                        
                        score = place.get('score', 50) + boost
                        
                        # Cost = W_time * TravelTime_sec + W_score * (100 - Score) 
                        cost = W_time * travel_time + W_score * (100 - score) 
                        final_costs.append((cost, place))
                    
                    final_costs.sort(key=lambda x: x[0]) 
                    
                    if final_costs:
                        selected = final_costs[0][1]
            
            if selected:
                selected['is_start_point'] = False
                day_places.append(make_place(current_time.strftime("%H:%M"), type_kor, selected, type_key))
                visited_place_ids.add(selected['id'])
                last_place = selected
                last_place['type_key'] = type_key
        
        # 📌 Day 종료 지점 설정 (숙소 복귀 또는 공항)
        
        # 🚀 NEW: 다음 날 숙소 결정
        next_hotel = night_stay_hotels[d - 1] if d < duration else None
        
        if last_place:
            prev_place_type_key = last_place.get('type_key', 'default')
            visit_duration_seconds = VISIT_TIMES.get(prev_place_type_key, VISIT_TIMES['default'])
            current_time = current_time + timedelta(seconds=visit_duration_seconds)
            
        if d == duration:
            # 마지막 날: 공항 또는 최종 숙소로 복귀
            final_stop = None
            if '항공' in user_data.get('transport', []) and airport_place:
                final_stop = airport_place
            elif last_night_hotel:
                final_stop = last_night_hotel

            if final_stop:
                final_stop['is_start_point'] = True
                day_places.append(make_place(current_time.strftime("%H:%M"), "출발 지점", final_stop, "hotel")) 
        
        elif next_hotel: # 중간 날: 다음 날 숙소로 복귀
            next_hotel['is_start_point'] = False
            day_places.append(make_place(current_time.strftime("%H:%M"), "숙소 복귀", next_hotel, "hotel"))
            
            # 🚀 다음 날 시작 지점 업데이트 (다음 루프를 위해)
            last_night_hotel = next_hotel
        
        days.append({"day": d, "places": day_places})
    
    return days

def generate_plans(data, duration):
    places = backend.get_places(data['dest_city'])
    if not places: return []

    # 1. 데이터 정제 및 중복 제거
    places.sort(key=lambda x: (x.get('img_url') != "", float(x.get('rating', 0))), reverse=True)
    unique_places = []
    seen_names = set()

    for p in places:
        clean_name = ''.join(filter(str.isalnum, p['name'])).lower()
        if clean_name not in seen_names:
            seen_names.add(clean_name)
            unique_places.append(p)
    places = unique_places

    # 2. 점수 계산 및 정렬
    scored_places = []
    for p in places:
        score, tags = calculate_score(p, user_styles)
        p['score'] = score
        p['matched_tags'] = tags
        scored_places.append(p)
    scored_places.sort(key=lambda x: x['score'], reverse=True)
    
    # 공항 장소 데이터 (임시 데이터)
    airport_place = None
    if '항공' in data.get('transport', []):
        airport_place = {
            "id": "airport_start", "source": "system", "name": f"{data['dest_city']} 공항", 
            "city": data['dest_city'], "category": "airport", "lat": 33.5113, "lng": 126.493,
            "address": "공항 출발/도착", "rating": 5.0, "img_url": "", "desc": "여행 시작/마무리 지점"
        }
        
    for p in places: p['score'], _ = calculate_score(p, data)
    places.sort(key=lambda x: x['score'], reverse=True)
    
    # 📌 4. 장소 타입을 명확히 구분 및 영문 카테고리 포함
    hotels = [p for p in places if "숙소" in str(p['category']) or "호텔" in str(p['category']) or "펜션" in str(p['category']) or "리조트" in str(p['category']) or "lodging" in str(p['category']).lower()]
    non_lodging_places = [p for p in places if p not in hotels]
    
    # 'tourist_attraction', 'park' 영문 키워드 추가
    sights = [p for p in non_lodging_places if "관광" in str(p['category']) or "명소" in str(p['category']) or "공원" in str(p['category']) or "박물관" in str(p['category']) or "tourist_attraction" in str(p['category']).lower() or "park" in str(p['category']).lower()]
    
    # 'restaurant', 'food' 영문 키워드 추가 + 카페 키워드 엄격히 제외
    foods = [p for p in non_lodging_places if ("식당" in str(p['category']) or "음식점" in str(p['category']) or "restaurant" in str(p['category']).lower() or "food" in str(p['category']).lower()) and "카페" not in str(p['category']) and "cafe" not in str(p['category']).lower()]
    
    # 'cafe' 영문 키워드 추가
    cafes = [p for p in non_lodging_places if "카페" in str(p['category']) or "cafe" in str(p['category']).lower()]
    
    # 예비 후보 
    if not sights: sights = non_lodging_places
    if not foods: foods = non_lodging_places
    if not cafes: cafes = non_lodging_places[:1] 

    # 테마 목록
    themes = [
        {"name": f"✨ {data['dest_city']} 핵심 코스", "desc": "사용자 취향 기반의 가장 효율적인 동선"},
        {"name": "🍽️ 식도락 & 힐링", "desc": "맛집 방문과 여유로운 휴식 중심의 일정"},
        {"name": "🌿 자연 & 관광", "desc": "주요 명소와 자연 경관을 둘러보는 일정"},
        {"name": "🔥 액티브 & 핫플", "desc": "활동적인 장소와 인기 명소 탐방"}
    ]
    
    final_plans = []
    
    user_pace = data.get('pace', '보통')

    for theme in themes:
        days = _generate_itinerary_for_theme(theme, duration, sights, foods, cafes, hotels, airport_place, user_pace, is_korea, data)
        final_plans.append({
            "theme": theme['name'], "desc": theme['desc'],
            "score": random.randint(90, 99), "tags": data['style'], "days": days
        })
        
        random.shuffle(pool_sights)
        random.shuffle(pool_foods)
        
        days = []
        
        # 테마별 스케줄 템플릿 설정
        if theme['mix_ratio'] == 'food_heavy':
            schedule_template = [
                ("11:00", "아점", "food"), ("13:00", "산책", "sight"),
                ("15:00", "카페", "food"), ("18:00", "저녁", "food"), ("21:00", "숙소", "hotel")
            ]
        elif theme['mix_ratio'] == 'relaxed':
            schedule_template = [
                ("10:30", "오전 여유", "sight"), ("13:00", "점심", "food"),
                ("15:30", "오후 관광", "sight"), ("19:00", "저녁", "food"), ("21:00", "숙소", "hotel")
            ]
        else:
            schedule_template = [
                ("10:00", "오전 관광", "sight"), ("12:30", "점심", "food"),
                ("15:00", "오후 관광", "sight"), ("18:30", "저녁", "food"), ("21:00", "숙소", "hotel")
            ]

# travel_logic.py (update_db 함수 수정)

def update_db(city, styles):
    try:
        keywords = []
        
        # 1. 사용자 스타일 기반 키워드
        for style in styles:
            keywords.append(f"{city} {style}")

        # 2. 해외 지역 필수 카테고리 및 영어 키워드 추가 (기존 유지)
        if not check_is_domestic(city):
             keywords.extend([f"{city} restaurant", f"{city} hotel", f"{city} cafe", f"{city} shopping mall", f"{city} museum"])
             
        # 3. 국내/해외 공통 키워드 (기존 유지)
        keywords.extend([f"{city} 식당", f"{city} 숙소"])
        
        # 🚀 FINAL FIX: API 캐시 우회 및 강제 다양화를 위한 랜덤 접미사 추가
        random_suffix = random.choice([
            f"unique spot {random.randint(100, 999)}",  # 완전히 랜덤한 쿼리
            f"near {city} historical sites",           # 검색 반경을 변경 유도
            f"best rated {random.choice(['food', 'sights'])}",
            f"hidden gem {random.randint(1, 10)}"
        ])
        keywords.append(f"{city} attractions {random_suffix}")

        is_domestic = check_is_domestic(city)
        
        # ... (backend.fetch_all_data 호출 로직 유지) ...
        result = backend.fetch_all_data(city, keywords, is_domestic=is_domestic) 
        
        print(f"🎉 [DB Update] '{city}' 데이터 업데이트 완료. 추가된 장소: {result.get('added_count', 0)}개")
        return result
        
    except Exception as e:
        print(f"❌ [DB Update Error] '{city}' 데이터 업데이트 중 오류 발생: {e}")
        return {"error": str(e)}
