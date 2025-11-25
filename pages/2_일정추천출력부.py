import streamlit as st
import sys
import os
import pandas as pd
import json
import random
import math
from datetime import date, timedelta
import streamlit.components.v1 as components 
import requests # backend 호출용

# [경로 설정] backend.py 위치 찾기 
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import backend 

# ==========================================
# 👇 [필수] 지도 표시용 키 (배포 시 secrets 사용)
# ==========================================
try:
    KAKAO_MAPS_JS_KEY = st.secrets["KAKAO_JS_KEY"]
    GOOGLE_MAPS_JS_KEY = st.secrets["GOOGLE_JS_KEY"]
except:
    # 로컬 테스트용 키
    GOOGLE_MAPS_JS_KEY = ""
    KAKAO_MAPS_JS_KEY = "" 
# ==========================================

st.set_page_config(page_title="픽앤고 결과", page_icon="✈️", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .main-header { margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 20px; }
    .title-badge { background-color: #fee500; color: #000; padding: 5px 10px; border-radius: 20px; font-weight: 700; font-size: 0.9rem; }
    .place-card { background: #fff; border: 1px solid #ddd; border-radius: 10px; padding: 15px; margin-bottom: 10px; display: flex; align-items: center; gap: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.02); transition: 0.2s; }
    .place-card:hover { box-shadow: 0 5px 15px rgba(0,0,0,0.1); transform: translateY(-2px); }
    .place-time { font-weight: bold; color: #1a73e8; min-width: 60px; text-align:center; }
    .place-info { flex: 1; }
    .place-name { font-size: 1.1rem; font-weight: 800; color: #333; margin-bottom: 4px; }
    .place-desc { font-size: 0.85rem; color: #666; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    .score-tag { background-color: #e8f0fe; color: #1a73e8; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; margin-left: 5px; }
    
    /* [3] 예약 버튼 스타일 추가 */
    .booking-btn {
        background-color: #03C75A; color: white !important; 
        padding: 5px 10px; border-radius: 5px; 
        text-decoration: none; font-size: 0.8rem; font-weight: bold;
        display: inline-block; margin-top: 5px;
    }
    .booking-btn:hover { opacity: 0.9; }

    div[role="radiogroup"] > label > div:first-child { display: none; }
    div[role="radiogroup"] { gap: 10px; display: flex; flex-direction: row; }
</style>
""", unsafe_allow_html=True)

# --- [0] 국내/해외 판별 함수 ---
def check_is_domestic(city_name):
    korean_cities = [
        "서울", "부산", "제주", "인천", "대구", "대전", "광주", "울산", "수원", "강릉", 
        "경주", "전주", "여수", "속초", "춘천", "가평", "양평", "포항", "거제", "남해", 
        "통영", "군산", "목포", "순천", "안동", "청주", "충주", "천안", "세종"
    ]
    if any(k in city_name for k in korean_cities): return True
    if "한국" in city_name or "대한민국" in city_name: return True
    return False

# --- [1] 지도 렌더링 함수 ---
def render_kakao_map(markers, path):
    if not markers: avg_lat, avg_lng = 33.450701, 126.570667
    else:
        avg_lat = sum([m['lat'] for m in markers]) / len(markers)
        avg_lng = sum([m['lng'] for m in markers]) / len(markers)
    
    html = f"""
    <div id="map" style="width:100%;height:400px;border-radius:12px;"></div>
    <script type="text/javascript" src="//dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_MAPS_JS_KEY}"></script>
    <script>
        var container = document.getElementById('map');
        var options = {{ center: new kakao.maps.LatLng({avg_lat}, {avg_lng}), level: 9 }};
        var map = new kakao.maps.Map(container, options);
        var markersData = {json.dumps(markers)};
        var pathData = {json.dumps(path)};
        
        if (pathData.length > 0) {{
            var linePath = pathData.map(p => new kakao.maps.LatLng(p.lat, p.lng));
            var polyline = new kakao.maps.Polyline({{
                path: linePath, strokeWeight: 5, strokeColor: '#1A73E8', strokeOpacity: 0.8, strokeStyle: 'solid'
            }});
            polyline.setMap(map);
        }}

        if (markersData.length > 0) {{
            var bounds = new kakao.maps.LatLngBounds();
            markersData.forEach((m, i) => {{
                var position = new kakao.maps.LatLng(m.lat, m.lng);
                var marker = new kakao.maps.Marker({{ map: map, position: position, title: m.title }});
                var iw = new kakao.maps.InfoWindow({{ content: '<div style="padding:5px;font-size:12px;color:black;">' + (i+1) + '. ' + m.title + '</div>' }});
                kakao.maps.event.addListener(marker, 'mouseover', () => iw.open(map, marker));
                kakao.maps.event.addListener(marker, 'mouseout', () => iw.close());
                bounds.extend(position);
            }});
            if (markersData.length > 1) {{ map.setBounds(bounds); }}
        }}
    </script>
    """
    return html

def render_google_map(markers, path):
    if not markers: return "<div style='padding:20px;'>📍 데이터가 없습니다.</div>"
    avg_lat = sum([m['lat'] for m in markers]) / len(markers)
    avg_lng = sum([m['lng'] for m in markers]) / len(markers)
    
    html = f"""
    <!DOCTYPE html>
    <html><head><style>#map {{ height: 400px; width: 100%; border-radius: 12px; }} html,body {{ height:100%; margin:0; }}</style></head><body>
    <div id="map"></div>
    <script>
        function initMap() {{
            const map = new google.maps.Map(document.getElementById("map"), {{ zoom: 12, center: {{ lat: {avg_lat}, lng: {avg_lng} }} }});
            const markers = {json.dumps(markers)};
            const path = {json.dumps(path)};
            
            const polyline = new google.maps.Polyline({{ path: path, map: map, strokeColor: "#1A73E8", strokeWeight: 5 }});
            const bounds = new google.maps.LatLngBounds();
            
            markers.forEach((m, i) => {{
                const pos = {{ lat: m.lat, lng: m.lng }};
                new google.maps.Marker({{ position: pos, map: map, label: (i+1).toString(), title: m.title }});
                bounds.extend(pos);
            }});
            
            if (markers.length > 1) {{ map.fitBounds(bounds); }}
        }}
    </script>
    <script src="https://maps.googleapis.com/maps/api/js?key={GOOGLE_MAPS_JS_KEY}&callback=initMap" async defer></script>
    </body></html>"""
    return html

# --- [2] 데이터 로직 ---
def get_db_places(city):
    return backend.get_places(city)

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

# --- 거리 계산 알고리즘 ---
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

# --- [3] 예약 딥링크 생성 함수 추가 ---
def get_booking_url(place_name):
    # 네이버 검색을 통한 예약 딥링크 (가장 범용적)
    base_url = "https://m.search.naver.com/search.naver?query="
    return f"{base_url}{place_name} 예약"

# --- 일정 생성 함수 (수정됨: 속도 개선 + Re-roll + 숙소) ---
def generate_plans(data, duration):
    city = data['dest_city']
    user_styles = data['style']
    
    places = get_db_places(city)
    if not places: return []

    scored_places = []
    for p in places:
        score, tags = calculate_score(p, user_styles)
        p['score'] = score
        p['matched_tags'] = tags
        scored_places.append(p)
        
    # [수정] 점수 순으로 정렬하되, 상위권 내에서 랜덤성을 부여해 Re-roll이 동작하게 함
    scored_places.sort(key=lambda x: x['score'], reverse=True)
    
    # 상위 40개 정도만 추려서 셔플 (Re-roll 시 매번 결과가 달라짐)
    top_tier_count = min(len(scored_places), 40)
    top_tier = scored_places[:top_tier_count]
    rest_tier = scored_places[top_tier_count:]
    random.shuffle(top_tier) 
    shuffled_places = top_tier + rest_tier
    
    # 카테고리 분류
    food_keywords = ['음식', '식당', '카페', 'food', 'restaurant', 'cafe', 'bakery', 'meal']
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
        # 테마별 풀 복사 (셔플해서 매번 다르게)
        pool_sights = all_sights[:] 
        pool_foods = all_foods[:]
        pool_hotels = all_hotels[:]
        random.shuffle(pool_sights)
        random.shuffle(pool_foods)
        
        days = []
        
        # [수정] 숙소(hotel) 포함된 템플릿
        if theme['mix_ratio'] == 'food_heavy':
            schedule_template = [
                ("11:00", "아점", "food"),
                ("13:00", "산책", "sight"),
                ("15:00", "카페", "food"),
                ("18:00", "저녁", "food"),
                ("21:00", "숙소", "hotel")
            ]
        elif theme['mix_ratio'] == 'relaxed':
            schedule_template = [
                ("10:30", "오전 여유", "sight"),
                ("13:00", "점심", "food"),
                ("15:30", "오후 관광", "sight"),
                ("19:00", "저녁", "food"),
                ("21:00", "숙소", "hotel")
            ]
        else:
            schedule_template = [
                ("10:00", "오전 관광", "sight"),
                ("12:30", "점심", "food"),
                ("15:00", "오후 관광", "sight"),
                ("18:30", "저녁", "food"),
                ("21:00", "숙소", "hotel")
            ]

        for d in range(1, duration + 1):
            day_places = []
            last_place = None 
            
            for time, type_name, p_type in schedule_template:
                # 후보군 선택
                if p_type == "food": candidates = pool_foods
                elif p_type == "hotel": candidates = pool_hotels
                else: candidates = pool_sights
                
                if not candidates: continue 
                
                selected = None
                
                if last_place is None:
                    selected = candidates[0]
                else:
                    last_lat = last_place['lat']
                    last_lng = last_place['lng']
                    
                    # [최적화 수정] API 호출 제거 -> 하버사인 거리로만 선택 (속도 < 1초)
                    candidates.sort(key=lambda p: haversine_distance(last_lat, last_lng, p['lat'], p['lng']))
                    
                    # 가장 가까운 곳 선택 (API 호출 X)
                    selected = candidates[0]
                
                if selected:
                    candidates.remove(selected) 
                    day_places.append(make_place(time, type_name, selected))
                    # 숙소는 다음날 출발지가 되므로 last_place로 업데이트
                    last_place = selected 
            
            days.append({"day": d, "places": day_places})
            
        all_scores = [p['raw_score'] for d in days for p in d['places']]
        avg_score = int(sum(all_scores) / len(all_scores)) if all_scores else 80
        
        final_plans.append({
            "theme": theme['name'], "desc": theme['desc'], "score": avg_score, "tags": user_styles, "days": days
        })
    return final_plans

def make_place(time, type_name, db_row):
    img = db_row.get('img_url')
    if not img: img = "https://source.unsplash.com/400x300/?travel"
    
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

# --- [4] 메인 화면 ---
if "form_data" in st.session_state:
    data = st.session_state["form_data"]
elif "user_input" not in st.session_state:
    st.session_state["user_input"] = {
        "dep_city": "서울", "dest_city": "제주", "start_date": date.today(), 
        "end_date": date.today() + timedelta(days=1), "people": 2, "style": ["맛집", "힐링"]
    }
    data = st.session_state["user_input"]
else:
    data = st.session_state["user_input"]

start = data.get('start_date')
if isinstance(start, str): start = date.fromisoformat(start)
end = data.get('end_date')
if isinstance(end, str): end = date.fromisoformat(end)
duration = (end - start).days + 1

is_korea = check_is_domestic(data['dest_city'])

col1, col2 = st.columns([7, 3])
with col1:
    location_badge = "🇰🇷 국내여행" if is_korea else "✈️ 해외여행"
    st.markdown(f"""
    <div class="main-header">
        <span class="title-badge">{location_badge}</span>
        <h1>{data['dest_city']} {duration}일 여행 코스</h1>
        <p style="color:#666;">{start} ~ {end} ({data['people']}명) · 선호 스타일: <b>{', '.join(data['style'])}</b></p>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        # [기능 추가] 새로고침 (DB 업데이트 없이 결과만 섞기)
        if st.button("🎲 다시 추천", use_container_width=True):
            if "plans" in st.session_state: del st.session_state["plans"]
            st.rerun()
    with c_btn2:
        if st.button("🔄 DB 업데이트", use_container_width=True):
            backend.init_db() 
            # [수정] '숙소' 키워드 강제 추가하여 호텔 데이터 수집
            keywords = ["가볼만한곳", "명소", "숙소", "호텔"] + data['style']
            with st.spinner(f"📡 {data['dest_city']} 데이터 수집 중..."):
                backend.fetch_all_data(data['dest_city'], keywords, is_domestic=True)
                backend.fetch_all_data(data['dest_city'], keywords, is_domestic=False)
            
            if "plans" in st.session_state: del st.session_state["plans"]
            st.rerun()

if "plans" not in st.session_state:
    with st.spinner("🚀 5초 안에 최적의 동선을 계산합니다..."):
        generated = generate_plans(data, duration)
        
    if generated:
        st.session_state["plans"] = generated
        st.rerun()
    else:
        st.warning("⚠️ 저장된 데이터가 없습니다. 우측 상단 '🔄 DB 업데이트' 버튼을 눌러주세요!")

if "plans" in st.session_state:
    plans = st.session_state["plans"]
    tabs = st.tabs([p['theme'] for p in plans])
    
    for i, tab in enumerate(tabs):
        plan = plans[i]
        with tab:
            st.markdown(f"""
            <div style="padding:10px 0; display:flex; align-items:center; gap:10px;">
                <span style="font-size:1.1rem; font-weight:bold;">🎯 추천 적합도: <span style="color:#1a73e8;">{plan['score']}%</span></span>
                <span style="color:#666;">| {plan['desc']}</span>
            </div>
            """, unsafe_allow_html=True)
            
            day_options = ["전체 동선"] + [f"{d['day']}일차" for d in plan['days']]
            selected_day_label = st.radio("📅 지도에 표시할 일정", day_options, horizontal=True, key=f"day_sel_{i}", label_visibility="collapsed")

            map_markers = []
            map_path = []
            
            if selected_day_label == "전체 동선":
                target_days = plan['days']
            else:
                target_day_num = int(selected_day_label.replace("일차", ""))
                target_days = [d for d in plan['days'] if d['day'] == target_day_num]
            
            for d in target_days:
                for p in d['places']:
                    if p['lat'] and p['lng']:
                        map_markers.append({"lat": p['lat'], "lng": p['lng'], "title": p['name']})
                        map_path.append({"lat": p['lat'], "lng": p['lng']})
            
            if is_korea:
                map_col1, map_col2 = st.columns([8, 2])
                with map_col2:
                    map_type = st.radio("지도 선택", ["Kakao Map", "Google Map"], horizontal=True, label_visibility="collapsed", key=f"map_sel_{i}")
                
                if map_type == "Google Map":
                    if GOOGLE_MAPS_JS_KEY: components.html(render_google_map(map_markers, map_path), height=400)
                    else: st.warning("Google Maps JS Key가 없습니다.")
                else:
                    components.html(render_kakao_map(map_markers, map_path), height=400)
            else:
                st.caption(f"🌍 {data['dest_city']} 지역은 Google Maps로 표시됩니다.")
                if GOOGLE_MAPS_JS_KEY: components.html(render_google_map(map_markers, map_path), height=400)
                else: st.warning("⚠️ 지도를 보려면 Google Maps JS Key를 입력해주세요.")
            
            st.divider()
            
            # --- 카드 리스트 출력 ---
            for day in plan['days']:
                st.caption(f"📅 Day {day['day']}")
                if not day['places']: st.info("일정이 비어있습니다.")
                for place in day['places']:
                    img_html = f"<img src='{place['img']}' style='width:80px; height:80px; object-fit:cover; border-radius:8px;'>" if place['img'] else ""
                    booking_url = get_booking_url(place['name']) # 예약 링크 생성
                    
                    st.markdown(f"""
                    <div class="place-card">
                        <div class="place-time">{place['time']}<br><small style="color:#888;">{place['type']}</small></div>
                        {img_html}
                        <div class="place-info">
                            <div class="place-name">
                                <a href="{place['url']}" target="_blank" style="color:#333;text-decoration:none;">{place['name']}</a>
                            </div>
                            <div class="place-desc">{place['desc']}</div>
                            <a href="{booking_url}" target="_blank" class="booking-btn">📅 예약/상세보기</a>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)