# pages/2_일정추천출력부.py
# =========================================================
# 📌 [Frontend] 서버 결과 시각화 — 리디자인 버전
# =========================================================
import streamlit as st
import streamlit.components.v1 as components
import json
import requests
import os
import sys

# [1] 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir  = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import backend_postgres as backend
import travel_logic as logic
from datetime import date

# [2] 페이지 설정
st.set_page_config(page_title="Pick&Go | 여행 일정 추천", page_icon="🗺️", layout="wide")

GENERATE_API_URL = "http://127.0.0.1:8000/api/v1/generate"

try:
    KAKAO_MAPS_JS_KEY  = st.secrets["KAKAO_JS_KEY"]
    GOOGLE_MAPS_JS_KEY = st.secrets["GOOGLE_JS_KEY"]
except:
    KAKAO_MAPS_JS_KEY  = ""
    GOOGLE_MAPS_JS_KEY = ""

# ──────────────────────────────────────────
# 지도 렌더링 함수
# ──────────────────────────────────────────
def render_kakao_map(markers, path):
    if not markers:
        avg_lat, avg_lng = 33.450701, 126.570667
    else:
        avg_lat = sum(m["lat"] for m in markers) / len(markers)
        avg_lng = sum(m["lng"] for m in markers) / len(markers)
    html = f"""
    <div id="map" style="width:100%;height:420px;border-radius:12px;overflow:hidden;"></div>
    <script type="text/javascript" src="//dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_MAPS_JS_KEY}"></script>
    <script>
        var map = new kakao.maps.Map(document.getElementById('map'),
            {{center: new kakao.maps.LatLng({avg_lat},{avg_lng}), level:9}});
        var path={json.dumps(path)}, markers={json.dumps(markers)};
        if(path.length>0){{
            new kakao.maps.Polyline({{path:path.map(p=>new kakao.maps.LatLng(p.lat,p.lng)),
                strokeWeight:4,strokeColor:'#3B82F6',strokeOpacity:0.85,strokeStyle:'solid'}}).setMap(map);
        }}
        if(markers.length>0){{
            var bounds=new kakao.maps.LatLngBounds();
            markers.forEach((m,i)=>{{
                var pos=new kakao.maps.LatLng(m.lat,m.lng);
                var marker=new kakao.maps.Marker({{map,position:pos,title:m.title}});
                var iw=new kakao.maps.InfoWindow({{content:'<div style="padding:5px 8px;font-size:12px;font-weight:700;color:#1e3a8a;">'+(i+1)+'. '+m.title+'</div>'}});
                kakao.maps.event.addListener(marker,'mouseover',()=>iw.open(map,marker));
                kakao.maps.event.addListener(marker,'mouseout',()=>iw.close());
                bounds.extend(pos);
            }});
            if(markers.length>1) map.setBounds(bounds);
        }}
    </script>"""
    return html

def render_google_map(markers, path):
    if not markers:
        return "<div style='padding:20px;color:#999;'>📍 표시할 데이터가 없습니다.</div>"
    avg_lat = sum(m["lat"] for m in markers) / len(markers)
    avg_lng = sum(m["lng"] for m in markers) / len(markers)
    html = f"""<!DOCTYPE html><html><head>
    <style>#map{{height:420px;width:100%;border-radius:12px;}}html,body{{height:100%;margin:0;}}</style></head><body>
    <div id="map"></div>
    <script>
    function initMap(){{
        const map=new google.maps.Map(document.getElementById("map"),{{zoom:12,center:{{lat:{avg_lat},lng:{avg_lng}}}}});
        const pts={json.dumps(path)};
        new google.maps.Polyline({{path:pts,map,strokeColor:"#3B82F6",strokeWeight:4}});
        const bounds=new google.maps.LatLngBounds();
        {json.dumps(markers)}.forEach((m,i)=>{{
            new google.maps.Marker({{position:{{lat:m.lat,lng:m.lng}},map,label:(i+1).toString(),title:m.title}});
            bounds.extend({{lat:m.lat,lng:m.lng}});
        }});
        if({json.dumps(markers)}.length>1) map.fitBounds(bounds);
    }}
    </script>
    <script src="https://maps.googleapis.com/maps/api/js?key={GOOGLE_MAPS_JS_KEY}&callback=initMap" async defer></script>
    </body></html>"""
    return html

# ──────────────────────────────────────────
# 전역 CSS
# ──────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }

/* 상단 요약 배지 */
.info-pill {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-right: 6px;
    margin-bottom: 4px;
}
.pill-blue   { background:#EFF6FF; color:#1D4ED8; border:1px solid #BFDBFE; }
.pill-green  { background:#F0FDF4; color:#15803D; border:1px solid #BBF7D0; }
.pill-purple { background:#FAF5FF; color:#7E22CE; border:1px solid #E9D5FF; }
.pill-amber  { background:#FFFBEB; color:#B45309; border:1px solid #FDE68A; }

/* 일정 점수 바 */
.score-bar-wrap { background:#F1F5F9; border-radius:8px; height:8px; margin:6px 0 14px; }
.score-bar      { height:8px; border-radius:8px; background:linear-gradient(90deg,#3B82F6,#6366F1); }

/* 장소 카드 */
.place-card {
    padding: 14px 16px;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    margin-bottom: 10px;
    background: #FFFFFF;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    transition: all 0.18s;
}
.place-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(59,130,246,0.12);
    border-color: #93C5FD;
}
.time-badge {
    background:#EFF6FF; color:#1D4ED8;
    padding:2px 8px; border-radius:4px;
    font-weight:700; font-size:0.75rem; margin-right:6px;
}
.type-badge {
    color:#64748B; font-size:0.75rem;
    border:1px solid #E2E8F0; padding:1px 7px; border-radius:4px;
}
.place-name { font-size:1rem; font-weight:700; margin:6px 0 3px; color:#0F172A; }
.place-desc { font-size:0.85rem; color:#64748B; margin-bottom:8px; line-height:1.5; }
.detail-btn {
    display:inline-block; padding:5px 12px;
    background:#3B82F6; color:#fff !important;
    text-decoration:none; border-radius:6px;
    font-size:0.78rem; font-weight:600;
    transition:background 0.15s;
}
.detail-btn:hover { background:#2563EB; }

/* 일정 없음 카드 */
.empty-card {
    padding:40px; text-align:center;
    border:2px dashed #CBD5E1; border-radius:16px;
    color:#94A3B8; font-size:1rem;
}

/* 탭 강조 */
button[data-baseweb="tab"] { font-weight:600 !important; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────
# 데이터 수신 확인
# ──────────────────────────────────────────
if "api_result" not in st.session_state or "form_data" not in st.session_state:
    st.markdown("""
    <div class="empty-card">
        🗺️ 생성된 일정이 없습니다.<br>
        <span style="font-size:0.85rem;color:#CBD5E1;">입력 화면에서 여행 조건을 설정해 주세요.</span>
    </div>""", unsafe_allow_html=True)
    if st.button("⬅️ 입력 화면으로", use_container_width=True):
        st.switch_page("1_여행조건입력부.py")
    st.stop()

user_data = st.session_state["form_data"]
data_api  = st.session_state["api_result"]
plans     = data_api.get("plans", [])
dest_city = user_data.get("dest_city", "")

# 날짜 / 기간 계산
start = user_data.get("start_date")
end   = user_data.get("end_date")
if isinstance(start, str): start = date.fromisoformat(start)
if isinstance(end,   str): end   = date.fromisoformat(end)
duration  = (end - start).days + 1
is_korea  = logic.check_is_domestic(dest_city)
flag      = "🇰🇷" if is_korea else "🌏"

# ──────────────────────────────────────────
# 헤더 영역
# ──────────────────────────────────────────
hcol1, hcol2 = st.columns([7, 3])
with hcol1:
    st.markdown(f"## {flag} {dest_city} {duration}일 여행 일정 추천")
    styles_str = " · ".join(user_data.get("style", []))
    st.markdown(
        f'<span class="info-pill pill-blue">📅 {start} ~ {end}</span>'
        f'<span class="info-pill pill-green">👥 {user_data.get("people",2)}명</span>'
        f'<span class="info-pill pill-purple">🎨 {styles_str}</span>'
        f'<span class="info-pill pill-amber">💰 {user_data.get("budget_level","중")} 예산</span>',
        unsafe_allow_html=True,
    )

with hcol2:
    st.markdown("<br>", unsafe_allow_html=True)
    r1, r2 = st.columns(2)
    with r1:
        if st.button("🔄 다시 추천받기", use_container_width=True, type="primary"):
            with st.spinner("새로운 일정을 생성 중입니다..."):
                try:
                    resp = requests.post(GENERATE_API_URL, json=user_data)
                    if resp.status_code == 200:
                        st.session_state["api_result"] = resp.json()
                        st.rerun()
                    else:
                        st.error(f"생성 실패 ({resp.status_code})")
                except Exception as e:
                    st.error(str(e))
    with r2:
        if st.button("⬅️ 조건 수정", use_container_width=True):
            st.switch_page("1_여행조건입력부.py")

st.divider()

# ──────────────────────────────────────────
# 일정 없음 처리
# ──────────────────────────────────────────
if not plans:
    st.markdown('<div class="empty-card">😕 조건에 맞는 일정을 찾지 못했습니다.<br><span style="font-size:0.85rem;">조건을 바꿔 다시 시도해보세요.</span></div>', unsafe_allow_html=True)
    st.stop()

# ──────────────────────────────────────────
# 일정 탭 출력
# ──────────────────────────────────────────
tabs = st.tabs([f"{'⭐' if i==0 else '📋'} {p['theme']}" for i, p in enumerate(plans)])

for i, tab in enumerate(tabs):
    plan = plans[i]
    with tab:

        # 일정 요약 행
        sc1, sc2, sc3 = st.columns([5, 3, 2])
        with sc1:
            st.markdown(f"**{plan.get('desc', '')}**")
            tags = " ".join([f"`{t}`" for t in plan.get("tags", [])])
            st.markdown(tags)
        with sc2:
            score = plan.get("score", 0)
            st.markdown(
                f"**추천 적합도** &nbsp; <span style='color:#3B82F6;font-size:1.1rem;font-weight:800;'>{score}%</span>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="score-bar-wrap"><div class="score-bar" style="width:{score}%;"></div></div>',
                unsafe_allow_html=True,
            )
        with sc3:
            if st.button(f"📅 이 코스로 예약", key=f"book_{i}", use_container_width=True, type="primary"):
                st.toast("✅ 예약 시스템으로 연결됩니다...")

        st.markdown("---")

        # 일자 선택 라디오
        day_labels = ["전체 동선"] + [f"{d['day']}일차" for d in plan["days"]]
        selected_day = st.radio(
            "📅 표시할 일정 선택",
            day_labels, horizontal=True,
            key=f"day_{i}", label_visibility="collapsed"
        )

        map_col, list_col = st.columns([0.58, 0.42])

        # ── 지도 ──
        with map_col:
            if selected_day == "전체 동선":
                target_days = plan["days"]
            else:
                tnum = int(selected_day.replace("일차", ""))
                target_days = [d for d in plan["days"] if d["day"] == tnum]

            map_markers, map_path = [], []
            for d in target_days:
                for p in d["places"]:
                    try:
                        lat, lng = float(p["lat"]), float(p["lng"])
                        if lat != 0.0 and lng != 0.0:
                            map_markers.append({"lat": lat, "lng": lng, "title": p["name"]})
                            map_path.append({"lat": lat, "lng": lng})
                    except (ValueError, TypeError):
                        continue

            if is_korea:
                map_type = st.radio("지도", ["카카오 지도", "구글 지도"],
                                    horizontal=True, key=f"mtype_{i}", label_visibility="collapsed")
                if map_type == "카카오 지도":
                    if KAKAO_MAPS_JS_KEY:
                        components.html(render_kakao_map(map_markers, map_path), height=460)
                    else:
                        components.html(render_google_map(map_markers, map_path), height=460)
                else:
                    if GOOGLE_MAPS_JS_KEY:
                        components.html(render_google_map(map_markers, map_path), height=460)
                    else:
                        st.warning("Google Maps JS Key가 없습니다.")
            else:
                st.caption("🌍 해외 지역은 Google Maps로 표시됩니다.")
                if GOOGLE_MAPS_JS_KEY:
                    components.html(render_google_map(map_markers, map_path), height=460)
                else:
                    st.warning("Google Maps JS Key가 없어 지도를 표시할 수 없습니다.")

        # ── 일정 리스트 ──
        with list_col:
            for day in plan["days"]:
                if selected_day != "전체 동선" and day["day"] != int(selected_day.replace("일차", "")):
                    continue
                with st.expander(f"📅 Day {day['day']} 상세 일정", expanded=True):
                    for place in day["places"]:
                        target_url = place.get("url") or f"https://www.google.com/search?q={place['name']}+{dest_city}"
                        img_tag = ""
                        if place.get("img"):
                            img_tag = f'<img src="{place["img"]}" style="width:100%;border-radius:8px;margin-bottom:8px;max-height:120px;object-fit:cover;" onerror="this.style.display=\'none\'">'
                        st.markdown(f"""
                        <div class="place-card">
                            {img_tag}
                            <div>
                                <span class="time-badge">{place.get('time','')}</span>
                                <span class="type-badge">{place.get('type','')}</span>
                            </div>
                            <div class="place-name">{place.get('name','')}</div>
                            <div class="place-desc">{place.get('desc','')}</div>
                            <a href="{target_url}" target="_blank" class="detail-btn">🔗 상세 보기</a>
                        </div>
                        """, unsafe_allow_html=True)