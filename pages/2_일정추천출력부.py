# pages/2_일정추천출력부.py
# =========================================================
# 📌 [Frontend] 서버 결과 시각화 (지도 + 일정 리스트)
# =========================================================
import streamlit as st
import streamlit.components.v1 as components 
import pandas as pd
import json

# 1. 페이지 설정
st.set_page_config(page_title="추천 결과", page_icon="🗺️", layout="wide")

# ==========================================
# 👇 지도 키 설정 (Streamlit Secrets에서 가져오기)
# ==========================================
try:
    # secrets.toml에 키가 없으면 빈 값으로 처리하여 에러 방지
    KAKAO_MAPS_JS_KEY = st.secrets.get("KAKAO_JS_KEY", "")
    GOOGLE_MAPS_JS_KEY = st.secrets.get("GOOGLE_JS_KEY", "")
except FileNotFoundError:
    KAKAO_MAPS_JS_KEY = ""
    GOOGLE_MAPS_JS_KEY = ""

# --- [지도 렌더링 함수 복구] ---
def render_kakao_map(markers, path):
    if not markers: 
        avg_lat, avg_lng = 33.450701, 126.570667
    else:
        avg_lat = sum([m['lat'] for m in markers]) / len(markers)
        avg_lng = sum([m['lng'] for m in markers]) / len(markers)
    
    # 마커 및 경로 데이터 JSON 변환
    markers_json = json.dumps(markers)
    path_json = json.dumps(path)

    html = f"""
    <div id="map" style="width:100%;height:450px;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.1);"></div>
    <script type="text/javascript" src="//dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_MAPS_JS_KEY}"></script>
    <script>
        var container = document.getElementById('map');
        var options = {{ center: new kakao.maps.LatLng({avg_lat}, {avg_lng}), level: 9 }};
        var map = new kakao.maps.Map(container, options);
        
        var markers = {markers_json};
        var path = {path_json};
        
        // 경로 그리기 (Polyline)
        if (path.length > 0) {{
            var linePath = path.map(p => new kakao.maps.LatLng(p.lat, p.lng));
            var polyline = new kakao.maps.Polyline({{
                path: linePath,
                strokeWeight: 5,
                strokeColor: '#0068C3',
                strokeOpacity: 0.8,
                strokeStyle: 'solid'
            }});
            polyline.setMap(map);
        }}

        // 마커 생성
        if (markers.length > 0) {{
            var bounds = new kakao.maps.LatLngBounds();
            markers.forEach((m, i) => {{
                var position = new kakao.maps.LatLng(m.lat, m.lng);
                var marker = new kakao.maps.Marker({{ map: map, position: position, title: m.title }});
                
                // 인포윈도우 (숫자 표시)
                var content = '<div style="padding:5px;font-size:12px;font-weight:bold;color:black;">' + (i+1) + '. ' + m.title + '</div>';
                var iw = new kakao.maps.InfoWindow({{ content: content }});
                kakao.maps.event.addListener(marker, 'mouseover', () => iw.open(map, marker));
                kakao.maps.event.addListener(marker, 'mouseout', () => iw.close());
                
                bounds.extend(position);
            }});
            if (markers.length > 1) {{ map.setBounds(bounds); }}
        }}
    </script>
    """
    return html

def render_google_map(markers, path):
    if not markers: return "<div style='padding:20px;'>📍 표시할 데이터가 없습니다.</div>"
    avg_lat = sum([m['lat'] for m in markers]) / len(markers)
    avg_lng = sum([m['lng'] for m in markers]) / len(markers)
    
    markers_json = json.dumps(markers)
    path_json = json.dumps(path)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><style>#map {{ height: 450px; width: 100%; border-radius: 12px; }} html,body {{ height:100%; margin:0; }}</style></head>
    <body>
    <div id="map"></div>
    <script>
        function initMap() {{
            const map = new google.maps.Map(document.getElementById("map"), {{ zoom: 12, center: {{ lat: {avg_lat}, lng: {avg_lng} }} }});
            const markers = {markers_json};
            const path = {path_json};
            
            // 경로 그리기
            const polyline = new google.maps.Polyline({{
                path: path, map: map, strokeColor: "#0068C3", strokeWeight: 5
            }});
            
            const bounds = new google.maps.LatLngBounds();
            
            // 마커 찍기
            markers.forEach((m, i) => {{
                const pos = {{ lat: m.lat, lng: m.lng }};
                new google.maps.Marker({{
                    position: pos, map: map, label: (i+1).toString(), title: m.title
                }});
                bounds.extend(pos);
            }});
            
            if (markers.length > 1) {{ map.fitBounds(bounds); }}
        }}
    </script>
    <script src="https://maps.googleapis.com/maps/api/js?key={GOOGLE_MAPS_JS_KEY}&callback=initMap" async defer></script>
    </body></html>"""
    return html

# --- [간단 유틸] 국내/해외 판별 (프론트엔드용) ---
def is_domestic(city_name):
    korean_cities = ["서울", "부산", "제주", "인천", "강릉", "경주", "여수", "속초", "대구", "대전", "광주"]
    return any(k in city_name for k in korean_cities) or "한국" in city_name

# --- [CSS 스타일] ---
st.markdown("""
<style>
    .place-card {
        padding: 15px; 
        border: 1px solid #e0e0e0; 
        border-radius: 12px; 
        margin-bottom: 12px; 
        background-color: #ffffff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        transition: 0.2s;
    }
    .place-card:hover { transform: translateY(-2px); box-shadow: 0 5px 10px rgba(0,0,0,0.1); }
    .time-badge { background-color: #e3f2fd; color: #1565c0; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.8rem; margin-right: 6px; }
    .type-badge { color: #666; font-size: 0.8rem; border: 1px solid #eee; padding: 1px 6px; border-radius: 4px; }
    .booking-btn {
        display: inline-block; margin-top: 8px; padding: 6px 12px; 
        background-color: #03c75a; color: white !important; 
        text-decoration: none; border-radius: 6px; font-size: 0.8rem; font-weight: bold;
    }
    .booking-btn:hover { opacity: 0.9; }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 🚀 메인 로직 시작
# ==========================================

# 1. 데이터 수신 확인
if "api_result" not in st.session_state:
    st.warning("⚠️ 생성된 일정이 없습니다. 메인 페이지에서 먼저 조건을 입력해주세요.")
    if st.button("⬅️ 입력 화면으로 돌아가기"):
        st.switch_page("1_여행조건입력부.py")
    st.stop()

# 2. 데이터 꺼내기
data = st.session_state["api_result"]
plans = data.get("plans", [])
dest_city = st.session_state["form_data"].get("dest_city", "")
is_korea = is_domestic(dest_city)

# 3. 헤더
st.title(f"🗺️ {dest_city} 여행 코스 ({len(plans)}개 안)")
st.caption("FastAPI 서버가 분석한 최적의 동선입니다.")

if not plans:
    st.error("조건에 맞는 일정을 찾지 못했습니다.")
else:
    # 4. 탭 생성 (테마별)
    tabs = st.tabs([f"{p['theme']}" for p in plans])
    
    for i, tab in enumerate(tabs):
        plan = plans[i]
        with tab:
            # (1) 테마 설명
            st.info(f"💡 **컨셉:** {plan['desc']} (추천 적합도: {plan['score']}점)")
            
            # (2) 지도/리스트 레이아웃 분할
            col_map, col_list = st.columns([5, 4]) 
            
            # (3) 일차 선택 (라디오 버튼)
            day_options = ["전체 동선"] + [f"{d['day']}일차" for d in plan['days']]
            selected_day_label = st.radio(
                "📅 지도에 표시할 일정", day_options, 
                horizontal=True, key=f"day_sel_{i}", label_visibility="collapsed"
            )

            # (4) 지도용 데이터 필터링
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

            # (5) 지도 렌더링 (국내: 카카오/구글 선택, 해외: 구글)
            with col_map:
                if is_korea:
                    map_type = st.radio("지도 선택", ["Kakao Map", "Google Map"], horizontal=True, label_visibility="collapsed", key=f"map_type_{i}")
                    if map_type == "Kakao Map":
                        components.html(render_kakao_map(map_markers, map_path), height=450)
                    else:
                        components.html(render_google_map(map_markers, map_path), height=450)
                else:
                    st.caption("🌍 해외 지역은 Google Maps로 표시됩니다.")
                    components.html(render_google_map(map_markers, map_path), height=450)

            # (6) 일정 리스트 출력
            with col_list:
                for day in plan['days']:
                    with st.expander(f"📅 Day {day['day']} 상세 일정", expanded=True):
                        for place in day['places']:
                            st.markdown(f"""
                            <div class="place-card">
                                <div>
                                    <span class="time-badge">{place['time']}</span>
                                    <span class="type-badge">{place['type']}</span>
                                </div>
                                <div style="font-size:1.1rem; font-weight:800; margin:4px 0;">{place['name']}</div>
                                <div style="font-size:0.9rem; color:#555; margin-bottom:6px;">{place['desc']}</div>
                                <a href="{place['url']}" target="_blank" class="booking-btn">🔗 상세/예약</a>
                            </div>
                            """, unsafe_allow_html=True)

            st.divider()
            
            # (7) 예약 버튼
            if st.button(f"📅 이 코스로 예약 진행", key=f"btn_book_{i}", use_container_width=True):
                st.toast("✅ 예약 시스템으로 연결됩니다... (추후 연동)")