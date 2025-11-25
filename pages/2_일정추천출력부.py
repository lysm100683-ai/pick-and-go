# 파일 위치: pages/2_일정추천출력부.py
import streamlit as st
import streamlit.components.v1 as components 
import json
from datetime import date, timedelta
import sys
import os

# [1] 경로 설정 및 모듈 가져오기
# pages 폴더 안에 있으므로, 부모 디렉토리(루트)를 path에 추가해야 backend와 travel_logic을 찾을 수 있습니다.
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import backend 
import travel_logic as logic  # [핵심] 분리한 로직 파일 import

# ==========================================
# 👇 지도 키 설정
# ==========================================
try:
    KAKAO_MAPS_JS_KEY = st.secrets["KAKAO_JS_KEY"]
    GOOGLE_MAPS_JS_KEY = st.secrets["GOOGLE_JS_KEY"]
except:
    GOOGLE_MAPS_JS_KEY = ""
    KAKAO_MAPS_JS_KEY = "" 
# ==========================================

st.set_page_config(page_title="픽앤고 결과", page_icon="✈️", layout="wide", initial_sidebar_state="collapsed")

# --- CSS 스타일 (그대로 유지) ---
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

# --- 지도 렌더링 함수 (UI 관련이므로 여기에 남김) ---
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

# -------------------------------------------------------------
# ⚠️ 수정된 부분: 로직 함수들 제거함 (check_is_domestic, generate_plans 등)
# 대신 logic.함수명() 으로 호출합니다.
# -------------------------------------------------------------

# --- [Main] 실행 화면 ---
if "form_data" in st.session_state:
    data = st.session_state["form_data"]
elif "user_input" not in st.session_state:
    # 세션 데이터가 없을 경우 기본값 테스트용
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

# [호출 수정] logic 모듈 사용
is_korea = logic.check_is_domestic(data['dest_city'])

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
        if st.button("🎲 다시 추천", use_container_width=True):
            if "plans" in st.session_state: del st.session_state["plans"]
            st.rerun()
    with c_btn2:
        if st.button("🔄 DB 업데이트", use_container_width=True):
            with st.spinner(f"📡 {data['dest_city']} 데이터 수집 중..."):
                # [호출 수정] logic 모듈 사용
                logic.update_db(data['dest_city'], data['style'])
            
            if "plans" in st.session_state: del st.session_state["plans"]
            st.rerun()

if "plans" not in st.session_state:
    with st.spinner("🚀 5초 안에 최적의 동선을 계산합니다..."):
        # [호출 수정] logic 모듈 사용
        generated = logic.generate_plans(data, duration)
        
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
                    # [호출 수정] logic 모듈 사용
                    booking_url = logic.get_booking_url(place['name']) 
                    
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