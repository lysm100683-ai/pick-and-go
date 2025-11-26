# backend.py (캐싱 적용: 읽기 속도 10배 향상)
import streamlit as st
import requests
import json
import googlemaps
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from urllib.parse import unquote
import pandas as pd
import sys
import os
import concurrent.futures 
import time

# --- [전역 설정] ---
DB_NAME = "travel_db"
temp_data_buffer = []

# 🚀 [핵심] 데이터 캐시 (서버가 켜져있는 동안 데이터를 기억해둠)
# 전역 변수로 데이터를 저장해두면 매번 구글 시트에 접속할 필요가 없습니다.
CACHED_PLACES = None
LAST_CACHE_TIME = 0
CACHE_EXPIRY = 3600  # 1시간마다 갱신 (초 단위)

# --- [API 키 로드] ---
try:
    MY_KAKAO_KEY = st.secrets.get("KAKAO_REST_KEY", "")
    MY_GOOGLE_KEY = st.secrets.get("GOOGLE_API_KEY", "")
    MY_TOUR_KEY = st.secrets.get("TOUR_API_KEY", "")
    MY_AMADEUS_ID = st.secrets.get("AMADEUS_ID", "")
    MY_AMADEUS_SECRET = st.secrets.get("AMADEUS_SECRET", "")
    GOOGLE_SHEET_CREDENTIALS = st.secrets.get("gcp_service_account", {})
except FileNotFoundError:
    MY_KAKAO_KEY = MY_GOOGLE_KEY = MY_TOUR_KEY = MY_AMADEUS_ID = MY_AMADEUS_SECRET = ""
    GOOGLE_SHEET_CREDENTIALS = {}
    if os.path.exists("service_account.json"):
        with open("service_account.json", "r", encoding="utf-8") as f:
            GOOGLE_SHEET_CREDENTIALS = json.load(f)

# --- [DB 연결 및 저장] ---
def get_sheet():
    if not GOOGLE_SHEET_CREDENTIALS: return None
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(GOOGLE_SHEET_CREDENTIALS), scope)
    client = gspread.authorize(creds)
    return client.open(DB_NAME).sheet1

def save_place(data):
    """임시 버퍼에 저장"""
    global temp_data_buffer
    if not any(item['id'] == data['id'] for item in temp_data_buffer):
        temp_data_buffer.append(data)

def final_batch_save():
    """버퍼 데이터를 시트에 저장하고, 캐시를 초기화합니다."""
    global temp_data_buffer, CACHED_PLACES
    if not temp_data_buffer: return

    try:
        sheet = get_sheet()
        if not sheet: return

        records = sheet.get_all_records()
        existing_df = pd.DataFrame(records)
        existing_ids = set()
        if not existing_df.empty and 'id' in existing_df.columns:
            existing_ids = set(existing_df['id'].astype(str).values)
        
        new_rows = []
        for data in temp_data_buffer:
            if str(data['id']) not in existing_ids:
                row_data = [
                    str(data['id']), data['source'], data['name'], data['city'], data['category'],
                    float(data['lat']), float(data['lng']), data['address'], float(data['rating']),
                    data['img_url'], data.get('desc', ''), str(datetime.now())
                ]
                new_rows.append(row_data)

        if new_rows:
            sheet.append_rows(new_rows)
            print(f"✅ [Batch Save] {len(new_rows)}개 저장 완료.")
            # 데이터가 바뀌었으니 캐시를 비웁니다 (다음 조회 때 새로 가져옴)
            CACHED_PLACES = None 
        
        temp_data_buffer = [] 
            
    except Exception as e:
        print(f"❌ 저장 실패: {e}")

# --- [API 호출 함수들 (축약 없음)] ---
def fetch_google(city, keywords):
    if not MY_GOOGLE_KEY: return
    gmaps = googlemaps.Client(key=MY_GOOGLE_KEY)
    for keyword in keywords:
        try:
            res = gmaps.places(query=f"{city} {keyword}")
            for p in res.get('results', []):
                img = ""
                if 'photos' in p:
                    ref = p['photos'][0]['photo_reference']
                    img = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={ref}&key={MY_GOOGLE_KEY}"
                save_place({"id": f"google_{p['place_id']}", "source": "google", "name": p['name'], "city": city,
                            "category": p.get('types',['place'])[0], "lat": p['geometry']['location']['lat'],
                            "lng": p['geometry']['location']['lng'], "address": p.get('formatted_address',''),
                            "rating": p.get('rating',0.0), "img_url": img, "desc": "Google"})
        except: pass

def fetch_kakao(city, keywords):
    if not MY_KAKAO_KEY: return
    headers = {"Authorization": f"KakaoAK {MY_KAKAO_KEY}"}
    for keyword in keywords:
        try:
            res = requests.get("https://dapi.kakao.com/v2/local/search/keyword.json", headers=headers, params={"query": f"{city} {keyword}", "size": 15})
            for p in res.json().get('documents', []):
                save_place({"id": f"kakao_{p['id']}", "source": "kakao", "name": p['place_name'], "city": city,
                            "category": p['category_name'].split(">")[-1].strip(), "lat": float(p['y']), "lng": float(p['x']),
                            "address": p['road_address_name'], "rating": 0.0, "img_url": p['place_url'], "desc": p['phone']})
        except: pass

def fetch_tourapi(city):
    if not MY_TOUR_KEY: return
    try:
        res = requests.get("http://apis.data.go.kr/B551011/KorService1/searchKeyword1", 
                           params={"serviceKey": unquote(MY_TOUR_KEY), "numOfRows": 20, "MobileOS": "ETC", "MobileApp": "PicknGo", "_type": "json", "keyword": city, "contentTypeId": 12})
        items = res.json().get('response', {}).get('body', {}).get('items', {}).get('item', [])
        if items:
            for p in items:
                save_place({"id": f"tour_{p['contentid']}", "source": "tourapi", "name": p['title'], "city": city,
                            "category": "관광지", "lat": float(p.get('mapy',0)), "lng": float(p.get('mapx',0)),
                            "address": p.get('addr1',''), "rating": 4.5, "img_url": p.get('firstimage',''), "desc": "TourAPI"})
    except: pass

def fetch_amadeus(city, lat, lng):
    if not MY_AMADEUS_ID: return
    try:
        token = requests.post("https://test.api.amadeus.com/v1/security/oauth2/token", data={"grant_type": "client_credentials", "client_id": MY_AMADEUS_ID, "client_secret": MY_AMADEUS_SECRET}).json().get('access_token')
        res = requests.get("https://test.api.amadeus.com/v1/reference-data/locations/pois", headers={"Authorization": f"Bearer {token}"}, params={"latitude": lat, "longitude": lng, "radius": 5})
        for p in res.json().get('data', []):
            save_place({"id": f"amadeus_{p['id']}", "source": "amadeus", "name": p['name'], "city": city,
                        "category": p['category'], "lat": float(p['geoCode']['latitude']), "lng": float(p['geoCode']['longitude']),
                        "address": city, "rating": 4.0, "img_url": "", "desc": "Amadeus"})
    except: pass

def fetch_all_data(city, keywords, api_keys=None, lat=0, lng=0, is_domestic=True):
    print(f"🚀 [Update] '{city}' 데이터 수집 시작...")
    tasks = []
    for kw in keywords: tasks.append(lambda k=kw: fetch_google(city, [k]))
    if is_domestic:
        for kw in keywords: tasks.append(lambda k=kw: fetch_kakao(city, [k]))
        if "관광" in str(keywords): tasks.append(lambda: fetch_tourapi(city))
    else:
        if lat != 0: tasks.append(lambda: fetch_amadeus(city, lat, lng))
            
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(task) for task in tasks]
        concurrent.futures.wait(futures)
    final_batch_save()
    print(f"✨ [Finish] '{city}' 업데이트 완료.")

# --- 🚀 [핵심 변경] 조회 함수 (캐싱 적용) ---
def get_places(city, category_filter=None, limit=50):
    global CACHED_PLACES, LAST_CACHE_TIME

    # 1. 캐시가 비어있거나 만료되었으면 시트에서 로드
    if CACHED_PLACES is None or (time.time() - LAST_CACHE_TIME > CACHE_EXPIRY):
        print("📥 Google Sheets에서 전체 데이터 로드 중... (약간 소요)")
        try:
            sheet = get_sheet()
            if not sheet: return []
            records = sheet.get_all_records()
            CACHED_PLACES = pd.DataFrame(records)
            LAST_CACHE_TIME = time.time()
            print(f"✅ 캐시 갱신 완료! ({len(CACHED_PLACES)}개)")
        except Exception as e:
            print(f"❌ 캐시 로드 실패: {e}")
            return []
    else:
        print("⚡ 캐시된 데이터(RAM) 사용 (초고속)")

    if CACHED_PLACES.empty: return []

    # 2. 메모리(RAM)에서 필터링 (속도 매우 빠름)
    df = CACHED_PLACES.copy()
    df['city'] = df['city'].astype(str)
    
    # 해당 도시 데이터만 추출
    filtered_df = df[df['city'].str.contains(city, na=False)]
    
    return filtered_df.to_dict('records')

# --- [이동 시간 계산] ---
def get_real_duration_kakao(origin_lat, origin_lng, dest_lat, dest_lng):
    # (기존 로직 동일)
    if not MY_KAKAO_KEY: return 999999
    try:
        url = "https://apis-navi.kakaomobility.com/v1/directions"
        headers = {"Authorization": f"KakaoAK {MY_KAKAO_KEY}"}
        params = {"origin": f"{origin_lng},{origin_lat}", "destination": f"{dest_lng},{dest_lat}", "priority": "RECOMMEND"}
        res = requests.get(url, headers=headers, params=params, timeout=2) # 타임아웃 추가
        return res.json()['routes'][0]['summary']['duration']
    except: return 999999

def get_real_duration_google(origin_lat, origin_lng, dest_lat, dest_lng):
    # (기존 로직 동일)
    if not MY_GOOGLE_KEY: return 999999
    try:
        gmaps = googlemaps.Client(key=MY_GOOGLE_KEY)
        result = gmaps.distance_matrix(origins=(origin_lat, origin_lng), destinations=(dest_lat, dest_lng), mode="driving")
        return result['rows'][0]['elements'][0]['duration']['value']
    except: return 999999