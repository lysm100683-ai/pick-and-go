# pages/2_일정추천출력부.py (수정)
# =========================================================
# 📌 [Frontend] 서버 결과 시각화 (지도 + 일정 리스트)
# =========================================================
import streamlit as st
import streamlit.components.v1 as components 
import json
import requests
import os # os, sys import 추가
import sys

# [1] 경로 설정 및 모듈 가져오기
# pages 폴더 안에 있으므로, 부모 디렉토리(루트)를 path에 추가해야 backend와 travel_logic을 찾을 수 있습니다.
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import backend 
import travel_logic as logic  # [핵심] 분리한 로직 파일 import
from datetime import date # date import 추가

# 2. FastAPI 서버 주소
GENERATE_API_URL = "http://127.0.0.1:8000/api/v1/generate"

# ==========================================
# 👇 지도 키 설정
# ==========================================
# (이 부분은 수정 없이 유지)
try:
    KAKAO_MAPS_JS_KEY = st.secrets["KAKAO_JS_KEY"]
    GOOGLE_MAPS_JS_KEY = st.secrets["GOOGLE_JS_KEY"]
except:
    GOOGLE_MAPS_JS_KEY = ""
    KAKAO_MAPS_JS_KEY = "" 
# ==========================================

# --- [지도 렌더링 함수 유지] ---
# (render_kakao_map, render_google_map 함수는 수정 없이 유지)
def render_kakao_map(markers, path):
    if not markers: avg_lat, avg_lng = 33.450701, 126.570667
    else:
        avg_lat = sum([m['lat'] for m in markers]) / len(markers)
        avg_lng = sum([m['lng'] for m in markers]) / len(markers)
    
    markers_json = json.dumps(markers)
    path_json = json.dumps(path)

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
# --- [지도 렌더링 함수 유지 끝] ---


# --- [CSS 스타일 유지] ---
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
if "api_result" not in st.session_state or "form_data" not in st.session_state:
    st.warning("⚠️ 생성된 일정이 없습니다. 메인 페이지에서 먼저 조건을 입력해주세요.")
    if st.button("⬅️ 입력 화면으로 돌아가기"):
        st.switch_page("1_여행조건입력부.py")
    st.stop()
    
# 💡 핵심 수정: 사용자 입력 데이터는 'form_data'에서 가져옵니다.
user_data = st.session_state["form_data"] 
data_api = st.session_state["api_result"]
plans = data_api.get("plans", [])
dest_city = user_data.get("dest_city", "")

# --- 🚀 2. "다시 추천받기" 기능 구현 ---
if st.button("다른 일정을 다시 추천받기 🔄", type="primary", use_container_width=True):
    # form_data를 직접 사용
    if user_data:
        with st.spinner("📡 새로운 일정을 생성 중입니다..."):
            try:
                response = requests.post(GENERATE_API_URL, json=user_data)
                
                if response.status_code == 200:
                    st.session_state["api_result"] = response.json()
                    st.success("✅ 새로운 일정 생성 완료!")
                    st.rerun() 
                else:
                    error_detail = response.json().get("detail", "알 수 없는 오류")
                    st.error(f"❌ 일정 생성 실패 (Code: {response.status_code}): {error_detail}")
                
            except requests.exceptions.ConnectionError:
                st.error("❌ 서버 연결 실패: FastAPI 서버가 실행 중인지 확인해 주세요.")
            except Exception as e:
                st.error(f"❌ 예상치 못한 오류 발생: {e}")
    else:
        st.error("일정 생성에 필요한 조건 데이터가 없습니다. 입력 페이지로 돌아가세요.")

st.markdown("---")


# 2. 데이터 꺼내기 및 계산
if not plans:
    st.error("조건에 맞는 일정을 찾지 못했습니다.")
else:
    # 날짜 계산
    start = user_data.get('start_date')
    if isinstance(start, str): start = date.fromisoformat(start)
    end = user_data.get('end_date')
    if isinstance(end, str): end = date.fromisoformat(end)
    duration = (end - start).days + 1
    
    # 💡 핵심 수정: logic 모듈의 check_is_domestic 함수 사용
    is_korea = logic.check_is_domestic(dest_city)

    # 3. 헤더
    st.title(f"🗺️ {dest_city} 여행 코스 ({len(plans)}개 안)")
    st.caption("FastAPI 서버가 분석한 최적의 동선입니다.")


    col1, col2 = st.columns([7, 3])
    with col1:
        location_badge = "🇰🇷 국내여행" if is_korea else "✈️ 해외여행"
        st.markdown(f"""
        <div class="main-header">
            <span class="title-badge">{location_badge}</span>
            <h1>{dest_city} {duration}일 여행 코스</h1>
            <p style="color:#666;">{start} ~ {end} ({user_data['people']}명) · 선호 스타일: <b>{', '.join(user_data['style'])}</b></p>
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
                with st.spinner(f"📡 {dest_city} 데이터 수집 중..."):
                    # [호출 수정] logic 모듈 사용
                    logic.update_db(dest_city, user_data['style'])
                
                if "plans" in st.session_state: del st.session_state["plans"]
                st.rerun()


    # 4. 일정 탭 출력 (api_result의 plans 사용)
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
            map_col, list_col = st.columns([0.6, 0.4])
            
            with map_col:
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
                        # p['lat']과 p['lng']의 유효성 검사 추가 (DB에서 누락될 수 있음)
                        try:
                            lat = float(p['lat'])
                            lng = float(p['lng'])
                            # 좌표가 0.0이 아닌 유효한 값일 때만 지도에 추가 (0.0은 데이터 누락 처리된 값)
                            if lat != 0.0 and lng != 0.0:
                                map_markers.append({"lat": lat, "lng": lng, "title": p['name']})
                                map_path.append({"lat": lat, "lng": lng})
                        except (ValueError, TypeError):
                            continue # 좌표가 유효하지 않으면 건너뜀
                
                # 지도 선택 UI는 지도 위에 배치
                map_col1, map_col2 = st.columns([8, 2])
                with map_col2:
                    map_type = st.radio("지도 선택", ["Google Map", "Kakao Map"] if is_korea else ["Google Map"], horizontal=True, label_visibility="collapsed", key=f"map_sel_{i}")
                
                
                if is_korea:
                    if map_type == "Kakao Map":
                        if KAKAO_MAPS_JS_KEY: components.html(render_kakao_map(map_markers, map_path), height=450)
                        else: st.warning("Kakao Maps JS Key가 없습니다. Google Map을 사용합니다.")
                    
                    if map_type == "Google Map" or not KAKAO_MAPS_JS_KEY:
                        if GOOGLE_MAPS_JS_KEY: components.html(render_google_map(map_markers, map_path), height=450)
                        else: st.warning("Google Maps JS Key가 없어 지도를 표시할 수 없습니다.")
                else:
                    # 해외 지역은 Google Map으로 통일
                    st.caption("🌍 해외 지역은 Google Maps로 표시됩니다.")
                    if GOOGLE_MAPS_JS_KEY: components.html(render_google_map(map_markers, map_path), height=450)
                    else: st.warning("Google Maps JS Key가 없어 지도를 표시할 수 없습니다.")

            # (6) 일정 리스트 출력 (list_col 사용)
            with list_col:
                for day in plan['days']:
                    with st.expander(f"📅 Day {day['day']} 상세 일정", expanded=True):
                        for place in day['places']:
                            # 🚀 3. 상세/예약 버튼 수정: 장소 URL로 직접 연결
                            # place['url']이 없을 경우, Google 검색 링크 제공 (Fallback)
                            target_url = place['url'] if place['url'] else f"https://www.google.com/search?q={place['name']}+{dest_city}"

                            st.markdown(f"""
                            <div class="place-card">
                                <div>
                                    <span class="time-badge">{place['time']}</span>
                                    <span class="type-badge">{place['type']}</span>
                                </div>
                                <div style="font-size:1.1rem; font-weight:800; margin:4px 0;">{place['name']}</div>
                                <div style="font-size:0.9rem; color:#555; margin-bottom:6px;">{place['desc']}</div>
                                <a href="{target_url}" target="_blank" class="booking-btn">🔗 상세/예약</a>
                            </div>
                            """, unsafe_allow_html=True)

            st.divider()
            
            # (7) 예약 버튼 (예약 확정 API는 사용하지 않으므로, 이 버튼은 그대로 유지)
            if st.button(f"📅 이 코스로 예약 진행", key=f"btn_book_{i}", use_container_width=True):
                st.toast("✅ 예약 시스템으로 연결됩니다... (추후 연동)")