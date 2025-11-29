# backend.py (DB 업데이트 후 캐시 초기화 로직 반영)
import streamlit as st
import requests
import json
import googlemaps
from datetime import datetime
from urllib.parse import unquote
import pandas as pd
import sys
import os
import concurrent.futures 
import time
import sqlite3 
import math # math 추가 (일부 로직에서 사용될 수 있음)

# --- [전역 설정] ---
DB_NAME = "travel_data.db" 
temp_data_buffer = []

CACHED_PLACES = None
LAST_CACHE_TIME = 0
CACHE_EXPIRY = 3600 

# API 키 설정 (실제 키로 대체 필요)
try:
    GMAPS_API_KEY = os.environ.get("GMAPS_API_KEY", "YOUR_GOOGLE_MAPS_API_KEY") 
    KAKAO_MAPS_REST_KEY = os.environ.get("KAKAO_REST_KEY", "YOUR_KAKAO_REST_API_KEY") 
except:
    GMAPS_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY"
    KAKAO_MAPS_REST_KEY = "YOUR_KAKAO_REST_API_KEY"
# --- [전역 설정 끝] ---


# --- [DB 연결 및 초기화] ---
def get_db_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    """DB 테이블을 초기화합니다. (places 테이블 및 movement_cache 테이블에 mode 컬럼 추가)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS places (
            id TEXT PRIMARY KEY, source TEXT, name TEXT, city TEXT, category TEXT,
            lat REAL, lng REAL, address TEXT, rating REAL, img_url TEXT,
            desc TEXT, updated_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movement_cache (
            origin_key TEXT,
            dest_key TEXT,
            mode TEXT, 
            duration INTEGER,
            is_korea INTEGER,
            PRIMARY KEY (origin_key, dest_key, mode) 
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- [장소 데이터 저장 및 조회] ---
def save_place(data):
    """임시 버퍼에 저장"""
    global temp_data_buffer
    if not any(item['id'] == data['id'] for item in temp_data_buffer):
        data.setdefault('desc', '')
        data.setdefault('rating', 0.0)
        data.setdefault('address', '')
        data.setdefault('img_url', '')
        data.setdefault('updated_at', str(datetime.now()))
        temp_data_buffer.append(data)

def save_bulk_data():
    """버퍼 데이터를 SQLite DB에 저장하고, 새로 추가된 행의 개수를 반환합니다."""
    global temp_data_buffer
    if not temp_data_buffer: return 0

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        new_rows = []
        new_places_count = 0
        
        for data in temp_data_buffer:
            # 중복 검사 (업데이트 로직은 생략하고, 새 항목만 추가)
            cursor.execute("SELECT id FROM places WHERE id = ?", (str(data['id']),))
            if cursor.fetchone() is None:
                new_rows.append((
                    str(data['id']), data['source'], data['name'], data['city'], data['category'],
                    # 💡 수정: 좌표가 None일 경우 0.0으로 저장 (DB 저장 시점 방어)
                    float(data.get('lat', 0.0)), float(data.get('lng', 0.0)), 
                    data['address'], float(data['rating']),
                    data['img_url'], data.get('desc', ''), str(datetime.now())
                ))
                new_places_count += 1

        if new_rows:
            cursor.executemany("""
                INSERT INTO places VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, new_rows)
            conn.commit()
        
        conn.close()
        temp_data_buffer = [] 
        
        return new_places_count
            
    except Exception as e:
        print(f"❌ SQLite 저장 실패: {e}")
        temp_data_buffer = [] 
        return 0

def force_load_places_cache():
    """FastAPI 시작 시 호출되어 CACHED_PLACES를 강제로 로드합니다."""
    global CACHED_PLACES, LAST_CACHE_TIME
    if CACHED_PLACES is not None:
        return True
        
    print(f"⏳ [Startup] SQLite DB '{DB_NAME}'에서 캐시 선 로드 시작...")
    try:
        conn = get_db_connection()
        query = "SELECT * FROM places"
        CACHED_PLACES = pd.read_sql_query(query, conn)
        conn.close()

        LAST_CACHE_TIME = time.time()
        print(f"✅ [Startup] 캐시 선 로드 완료! ({len(CACHED_PLACES)}개)")
        return True
    except Exception as e:
        print(f"❌ [Startup] DB 캐시 로드 실패: {e}")
        return False


def get_places(city, category_filter=None, limit=50):
    global CACHED_PLACES, LAST_CACHE_TIME

    if CACHED_PLACES is None or (time.time() - LAST_CACHE_TIME > CACHE_EXPIRY):
        if not force_load_places_cache():
            return []
    
    if CACHED_PLACES.empty: return []

    df = CACHED_PLACES.copy()
    
    # 💡 핵심 수정: 좌표 컬럼의 NaN을 0.0으로 대체하여 NoneType 비교를 방지합니다.
    df['lat'] = df['lat'].fillna(0.0)
    df['lng'] = df['lng'].fillna(0.0)
    
    df['city'] = df['city'].astype(str)
    filtered_df = df[df['city'].str.contains(city, na=False)] 
    
    return filtered_df.to_dict('records')


# --- [이동 시간 캐시 함수 유지] ---
def _get_loc_key(lat, lng):
    """위도/경도 쌍을 캐시 키로 변환"""
    # 5자리 반올림으로 충분한 정밀도 확보
    return f"{round(float(lat), 5)},{round(float(lng), 5)}"

def get_movement_cache(origin_lat, origin_lng, dest_lat, dest_lng, mode): # 🚀 mode 추가
    """DB에서 이동 시간을 조회합니다. (정방향/역방향 및 mode 모두 확인)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    origin_key = _get_loc_key(origin_lat, origin_lng)
    dest_key = _get_loc_key(dest_lat, dest_lng)
    
    # 🚀 mode를 조건에 포함
    cursor.execute("""
        SELECT duration FROM movement_cache 
        WHERE (origin_key = ? AND dest_key = ? AND mode = ?) 
        OR (origin_key = ? AND dest_key = ? AND mode = ?)
    """, (origin_key, dest_key, mode, dest_key, origin_key, mode))
    
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    return None

def save_movement_cache(origin_lat, origin_lng, dest_lat, dest_lng, mode, duration, is_korea): # 🚀 mode 추가
    """DB에 이동 시간을 저장합니다."""
    conn = get_db_connection()
    cursor = conn.cursor()
    origin_key = _get_loc_key(origin_lat, origin_lng)
    dest_key = _get_loc_key(dest_lat, dest_lng)
    
    try:
        # 🚀 mode를 저장
        cursor.execute("""
            INSERT OR REPLACE INTO movement_cache (origin_key, dest_key, mode, duration, is_korea) 
            VALUES (?, ?, ?, ?, ?)
        """, (origin_key, dest_key, mode, duration, 1 if is_korea else 0))
        conn.commit()
    except Exception as e:
        print(f"❌ 이동 시간 캐시 저장 실패: {e}")
    finally:
        conn.close()

# --- [API 호출 함수들 유지] ---
def get_real_duration_kakao(lat1, lng1, lat2, lng2, mode='driving'): # 🚀 mode 파라미터 추가
    """Kakao API를 사용하여 실제 이동 시간을 조회합니다. (한국 전용)"""
    
    # 💡 수정: 좌표가 0.0일 경우 (None 처리된 경우) 이동 불가 처리
    if lat1 == 0.0 or lng1 == 0.0 or lat2 == 0.0 or lng2 == 0.0: return 999999
    if KAKAO_MAPS_REST_KEY == "YOUR_KAKAO_REST_API_KEY": return 30*60

    origin_key = _get_loc_key(lat1, lng1)
    dest_key = _get_loc_key(lat2, lng2)
    
    # 🚀 mode를 캐시 조회에 사용
    cached = get_movement_cache(lat1, lng1, lat2, lng2, mode)
    if cached is not None: return cached
    
    
    # 🚀 mode에 따라 API 경로 및 파라미터 변경
    if mode == 'transit':
        # 대중교통 API 사용 (Kakao Public Transit - /v1/public-transit/directions)
        url = "https://apis-navi.kakaomobility.com/v1/public-transit/directions"
        params = {
            "origin": f"{lng1},{lat1}", # Kakao는 lng, lat 순서 사용
            "destination": f"{lng2},{lat2}",
            "departure_time": datetime.now().strftime("%Y%m%d%H%M%S")
        }
    else: # driving (차량/도보)
        # 길찾기 API 사용 (Kakao Direction - /v1/directions)
        url = "https://apis-navi.kakaomobility.com/v1/directions"
        params = {
            "origin": f"{lng1},{lat1}",
            "destination": f"{lng2},{lat2}",
            "priority": "RECOMMEND"
        }

    try:
        res = requests.get(url, headers={"Authorization": f"KakaoAK {KAKAO_MAPS_REST_KEY}"}, params=params, timeout=2)
        data = res.json()
        
        duration_seconds = None
        if data.get('routes'):
            duration_seconds = data['routes'][0].get('summary', {}).get('duration')
            
        if duration_seconds is None: return 999999
        
        # 🚀 mode를 캐시 저장에 사용
        save_movement_cache(lat1, lng1, lat2, lng2, mode, duration_seconds, is_korea=True)
        return duration_seconds
    except Exception as e: 
        return 999999

def get_real_duration_google_bulk(lat1, lng1, candidates, mode='driving'): # 🚀 mode 파라미터 추가
    """Google Directions API를 사용하여 여러 목적지까지의 이동 시간을 병렬로 조회합니다."""
    
    if lat1 == 0.0 or lng1 == 0.0: return [(999999, p) for p in candidates] # 💡 수정: 출발지 좌표가 0.0인 경우
    if GMAPS_API_KEY == "YOUR_GOOGLE_MAPS_API_KEY": return [(30*60, p) for p in candidates]

    gmaps = googlemaps.Client(key=GMAPS_API_KEY)
    
    results = []
    
    for p in candidates:
        # 💡 수정: 목적지 좌표가 0.0인 경우 API 호출 없이 실패 처리
        if p['lat'] == 0.0 or p['lng'] == 0.0:
            results.append((999999, p))
            continue
            
        origin_key = _get_loc_key(lat1, lng1)
        dest_key = _get_loc_key(p['lat'], p['lng'])
        
        # 🚀 mode를 캐시 조회에 사용
        cached = get_movement_cache(lat1, lng1, p['lat'], p['lng'], mode) 
        if cached is not None:
            results.append((cached, p))
            continue
            
        try:
            # 🚀 mode를 directions API에 전달
            directions_result = gmaps.directions(
                origin=f"{lat1},{lng1}",
                destination=f"{p['lat']},{p['lng']}",
                mode=mode, # 👈 mode 적용
                departure_time=datetime.now()
            )
            
            duration_seconds = 999999
            if directions_result and directions_result[0]['legs']:
                duration_seconds = directions_result[0]['legs'][0]['duration']['value']
            
            # 🚀 mode를 캐시 저장에 사용
            save_movement_cache(lat1, lng1, p['lat'], p['lng'], mode, duration_seconds, is_korea=False)
            results.append((duration_seconds, p))

        except Exception as e:
            results.append((999999, p))
            
    return results

# --- [데이터 수집 관련 함수 유지] ---
# backend.py (fetch_google 함수 수정)

def fetch_google(city, keywords):
    MY_GOOGLE_KEY = GMAPS_API_KEY
    if MY_GOOGLE_KEY == "YOUR_GOOGLE_MAPS_API_KEY": return
    gmaps = googlemaps.Client(key=MY_GOOGLE_KEY)
    for keyword in keywords:
        try:
            res = gmaps.places(query=f"{city} {keyword}")
            
            # 🚀 API 응답 상태 진단
            status = res.get('status')
            if status != 'OK' and status != 'ZERO_RESULTS':
                 print(f"⚠️ [Google API WARNING] '{keyword}' 검색 실패. Status: {status}")
            
            if status != 'OK':
                 continue 

            for p in res.get('results', []):
                # ... (기존 save_place 로직 유지) ...
                img = ""
                if 'photos' in p:
                    ref = p['photos'][0]['photo_reference']
                    img = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={ref}&key={MY_GOOGLE_KEY}"
                    
                # 💡 수정: 좌표에 기본값 0.0 지정
                lat = p['geometry']['location'].get('lat')
                lng = p['geometry']['location'].get('lng')

                save_place({"id": f"google_{p['place_id']}", "source": "google", "name": p['name'], "city": city,
                            "category": p.get('types',['place'])[0], "lat": lat or 0.0, "lng": lng or 0.0,
                            "address": p.get('formatted_address',''),
                            "rating": p.get('rating',0.0), "img_url": img, "desc": "Google"})
        except Exception as e: 
             print(f"❌ [Google API Error] '{keyword}' 처리 중 예외 발생: {e}")
             pass

def fetch_kakao(city, keywords):
    MY_KAKAO_KEY = KAKAO_MAPS_REST_KEY
    if MY_KAKAO_KEY == "YOUR_KAKAO_REST_API_KEY": return
    headers = {"Authorization": f"KakaoAK {MY_KAKAO_KEY}"}
    for keyword in keywords:
        try:
            res = requests.get("https://dapi.kakao.com/v2/local/search/keyword.json", headers=headers, params={"query": f"{city} {keyword}", "size": 15})
            for p in res.json().get('documents', []):
                # 💡 수정: 좌표에 기본값 0.0 지정
                lat = float(p.get('y', 0.0))
                lng = float(p.get('x', 0.0))
                
                save_place({"id": f"kakao_{p['id']}", "source": "kakao", "name": p['place_name'], "city": city,
                            "category": p['category_name'].split(">")[-1].strip(), "lat": lat, "lng": lng,
                            "address": p['road_address_name'], "rating": 0.0, "img_url": p['place_url'], "desc": p['phone']})
        except: pass

def fetch_tourapi(city):
    # TourAPI 관련 키 로드 로직은 제외하고 기존 형태 유지
    # ...
    pass

def fetch_amadeus(city, lat, lng):
    # Amadeus 관련 키 로드 로직은 제외하고 기존 형태 유지
    # ...
    pass

# 🚀 2-1. fetch_all_data 함수 수정: DB 업데이트 후 캐시 초기화 및 결과 반환
def fetch_all_data(city, keywords, api_keys=None, lat=0, lng=0, is_domestic=True):
    global CACHED_PLACES, LAST_CACHE_TIME
    
    print(f"🚀 [Update] '{city}' 데이터 수집 시작...")
    
    # 업데이트 전 장소 수 확인
    initial_places = get_places(city)
    initial_count = len(initial_places)
    
    tasks = []
    # 데이터 수집 tasks 리스트 생성 (기존 로직 유지)
    for kw in keywords: tasks.append(lambda k=kw: fetch_google(city, [k]))
    if is_domestic:
        fetch_kakao(city, keywords)
        if "관광" in str(keywords): fetch_tourapi(city)
    else:
        if lat != 0: tasks.append(lambda: fetch_amadeus(city, lat, lng))
            
    # 작업 실행
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(task) for task in tasks]
        # 모든 태스크가 완료될 때까지 기다립니다.
        concurrent.futures.wait(futures) 
    
    # 🚀 데이터 DB에 일괄 저장 및 추가된 개수 확인
    added_count = save_bulk_data()
    
    # 🚀 캐시 무효화: 업데이트 후 반드시 캐시를 초기화하여 다음 호출 시 DB에서 새로 로드하도록 강제
    CACHED_PLACES = None
    LAST_CACHE_TIME = 0
    
    # 업데이트 후 장소 수 확인 (get_places가 이제 새로운 캐시를 로드할 것임)
    final_count = len(get_places(city))
    
    print(f"✨ [Finish] '{city}' 업데이트 완료.")
    print(f"   - 최종 DB 개수: {final_count}, 새로 추가된 장소: {added_count}개")
    
    return {"added_count": added_count, "final_count": final_count}