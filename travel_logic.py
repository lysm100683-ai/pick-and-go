# travel_logic.py
import sys
import os
import math
import random
from datetime import date, timedelta

# [경로 설정] backend.py 위치 찾기 (상위 폴더)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import backend  # DB 통신 모듈

# --- [기능 1] 국내/해외 판별 ---
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

    R = 6371 
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2) * math.sin(dLat/2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLon/2) * math.sin(dLon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# --- [기능 3] 점수 계산 알고리즘 ---
def calculate_score(place, user_styles):
    style_keywords = {
        "휴양": ["beach", "park", "nature", "resort", "해변", "공원", "휴양", "산책"],
        "힐링": ["forest", "garden", "spa", "relax", "숲", "정원", "온천", "힐링"],
        "관광": ["tourist", "museum", "landmark", "sight", "관광", "박물관", "명소", "유적"],
        "맛집": ["food", "restaurant", "meal", "dish", "식당", "음식", "요리", "맛집"],
        "쇼핑": ["shopping", "mall", "market", "store", "쇼핑", "시장", "몰", "백화점"],
        "자연": ["nature", "mountain", "lake", "hiking", "자연", "산", "호수", "등산"]
    }
    
    try: rating = float(place.get('rating', 0))
    except: rating = 3.0
        
    base_score = rating * 10
    if base_score == 0: base_score = 30
    
    bonus_score = 0
    place_cat = str(place['category']).lower() + " " + str(place['name']).lower()
    
    matched_tags = []
    for style in user_styles:
        keywords = style_keywords.get(style, [style])
        if any(k in place_cat for k in keywords):
            bonus_score += 20
            matched_tags.append(style)
            
    final_score = base_score + bonus_score
    return final_score, matched_tags

# --- [기능 4] 예약 링크 생성 ---
def get_booking_url(place_name):
    base_url = "https://m.search.naver.com/search.naver?query="
    return f"{base_url}{place_name} 예약"

# --- [기능 5] 장소 객체 포맷팅 ---
def make_place(time, type_name, db_row):
    img = db_row.get('img_url')
    if not img: img = "https://source.unsplash.com/400x300/?travel"
    
    # 태그 HTML 생성은 UI 영역이지만, 데이터 구조 안에 포함되어 있어 여기서 처리
    tags_html = ""
    if 'matched_tags' in db_row and db_row['matched_tags']:
        tags_html = " ".join([f"<span class='score-tag'>#{t}</span>" for t in db_row['matched_tags']])
    
    try: raw_score = int(db_row.get('score', 80))
    except: raw_score = 80

    return {
        "time": time, "type": type_name, "name": db_row['name'],
        "desc": f"{db_row['category']} | {db_row['address']} {tags_html}",
        "lat": db_row['lat'], "lng": db_row['lng'], "url": db_row['img_url'],
        "raw_score": raw_score, "img": img
    }

# --- [핵심 기능] 일정 생성 알고리즘 ---
def generate_plans(data, duration):
    city = data['dest_city']
    user_styles = data['style']
    
    places = backend.get_places(city)
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
    
    # 3. 상위 그룹 셔플 (랜덤성 부여)
    top_tier_count = min(len(scored_places), 40)
    top_tier = scored_places[:top_tier_count]
    rest_tier = scored_places[top_tier_count:]
    random.shuffle(top_tier) 
    shuffled_places = top_tier + rest_tier
    
    # 4. 카테고리 분류
    food_keywords = ['음식', '식당', '카페', 'food', 'restaurant', 'cafe', 'bakery', 'meal', 'bar', 'pub']
    hotel_keywords = ['hotel', 'motel', 'resort', 'pension', '숙소', '호텔', '리조트', '펜션']
    
    all_foods = [p for p in shuffled_places if any(k in str(p['category']).lower() for k in food_keywords)]
    all_hotels = [p for p in shuffled_places if any(k in str(p['category']).lower() for k in hotel_keywords)]
    all_sights = [p for p in shuffled_places if (p not in all_foods) and (p not in all_hotels)]
    
    themes = [
        {"name": f"✨ {city} 맞춤 추천", "desc": "밸런스 최적 코스", "mix_ratio": "balanced"},
        {"name": "🍽️ 식도락 여행", "desc": "맛집 위주 탐방", "mix_ratio": "food_heavy"},
        {"name": "🔥 핫플레이스", "desc": "인기 명소 위주", "mix_ratio": "sight_heavy"},
        {"name": "🌿 힐링 & 휴식", "desc": "여유로운 일정", "mix_ratio": "relaxed"}
    ]
    
    final_plans = []
    
    for theme in themes:
        pool_sights = all_sights[:] 
        pool_foods = all_foods[:]
        pool_hotels = all_hotels[:]
        
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

        for d in range(1, duration + 1):
            day_places = []
            last_place = None 
            
            for time, type_name, p_type in schedule_template:
                if p_type == "food": candidates = pool_foods
                elif p_type == "hotel": candidates = pool_hotels
                else: candidates = pool_sights
                
                if not candidates: continue 
                
                selected = None
                if last_place is None:
                    selected = candidates[0]
                else:
                    # 거리순 정렬 (Greedy)
                    last_lat, last_lng = last_place['lat'], last_place['lng']
                    candidates.sort(key=lambda p: haversine_distance(last_lat, last_lng, p.get('lat'), p.get('lng')))
                    selected = candidates[0]
                
                if selected:
                    candidates.remove(selected) 
                    day_places.append(make_place(time, type_name, selected))
                    last_place = selected 
            
            days.append({"day": d, "places": day_places})
            
        all_scores = [p['raw_score'] for d in days for p in d['places']]
        avg_score = int(sum(all_scores) / len(all_scores)) if all_scores else 80
        
        final_plans.append({
            "theme": theme['name'], "desc": theme['desc'], 
            "score": avg_score, "tags": user_styles, "days": days
        })
    return final_plans
    
# --- [기능 6] DB 업데이트 ---
def update_db(dest_city, styles):
    backend.init_db() 
    keywords = ["가볼만한곳", "명소", "숙소", "호텔"] + styles
    # 국내/해외 모두 수집 시도
    backend.fetch_all_data(dest_city, keywords, is_domestic=True)
    backend.fetch_all_data(dest_city, keywords, is_domestic=False)