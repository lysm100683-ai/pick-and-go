import streamlit as st
import requests
import json
import googlemaps
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from urllib.parse import unquote
import pandas as pd


# --- 아래 코드를 추가하세요 ---
DB_NAME = "travel_db"  # 실제 구글 스프레드시트 파일 이름과 똑같이 적어야 합니다.
# ---------------------------

# ==========================================
# 👇 [필수] API 키 설정 (Streamlit Secrets에서 가져옴)
# ==========================================
try:
    MY_KAKAO_KEY = st.secrets["KAKAO_REST_KEY"]
    MY_GOOGLE_KEY = st.secrets["GOOGLE_API_KEY"]
    MY_TOUR_KEY = st.secrets["TOUR_API_KEY"]
    MY_AMADEUS_ID = st.secrets["AMADEUS_ID"]
    MY_AMADEUS_SECRET = st.secrets["AMADEUS_SECRET"]
    # 구글 시트 인증 정보 (Secrets에 통째로 넣을 예정)
    GOOGLE_SHEET_CREDENTIALS = st.secrets["gcp_service_account"]
except:
    # 로컬 테스트용 (여기에 본인 키 입력)
    MY_KAKAO_KEY = ""   # (예: a1b2c3d...)
    MY_GOOGLE_KEY = ""      # 구글 키 (없으면 비워두세요)
    MY_TOUR_KEY = ""        # 관광공사 키 (없으면 비워두세요)
    MY_AMADEUS_ID = ""      # 아마데우스 ID (없으면 비워두세요)
    MY_AMADEUS_SECRET = ""  # 아마데우스 Secret (없으면 비워두세요)
    # 로컬에서는 json 파일 경로를 적거나 해야 하지만, 
    # 배포 위주로 설명드리므로 로컬 테스트 시에는 secrets.toml을 활용하는 것을 권장합니다.
    import json
    import os
    
    json_file_path = "service_account.json" 
    
    if os.path.exists(json_file_path):
        with open(json_file_path, "r", encoding="utf-8") as f:
            GOOGLE_SHEET_CREDENTIALS = json.load(f)
    else:
        # 파일이 없으면 빈 딕셔너리로 두어 NameError 방지 (단, 실행 시 에러 남)
        print("❌ 경고: service_account.json 파일을 찾을 수 없습니다.")
        GOOGLE_SHEET_CREDENTIALS = {}

# 구글 시트 연결 함수
def get_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # Streamlit Cloud 배포 환경
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(GOOGLE_SHEET_CREDENTIALS), scope)
    client = gspread.authorize(creds)
    # 시트 이름이 'travel_db'인 파일을 엽니다. (파일 이름 정확해야 함!)
    return client.open("travel_db").sheet1

# DB 초기화 (구글 시트는 헤더만 있으면 되므로 패스)
def init_db():
    pass 

# 데이터 저장 (Upsert 구현: ID가 있으면 수정, 없으면 추가)
def save_place(data):
    try:
        sheet = get_sheet()
        # 모든 데이터 가져오기 (ID 확인용)
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        
        # 데이터 준비
        row_data = [
            str(data['id']), data['source'], data['name'], data['city'], data['category'],
            float(data['lat']), float(data['lng']), data['address'], float(data['rating']),
            data['img_url'], data.get('desc', ''), str(datetime.now())
        ]

        # 이미 존재하는 ID인지 확인
        if not df.empty and str(data['id']) in df['id'].astype(str).values:
            # 존재하면 업데이트 (행 찾아서 덮어쓰기 - API 호출 줄이려고 일단 생략하거나 append만 해도 됨)
            # 구글 시트 API 제한 때문에, 여기서는 간단하게 '없는 것만 추가'로 구현합니다.
            pass 
        else:
            # 없으면 추가
            sheet.append_row(row_data)
            print(f"💾 구글시트 저장: {data['name']}")
            
    except Exception as e:
        print(f"❌ 구글시트 저장 실패: {e}")

# --- [API 호출 함수들] (기존과 로직 동일, save_place만 바뀜) ---
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
        for p in res.json()['response']['body']['items']['item']:
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
    fetch_google(city, keywords)
    if is_domestic:
        fetch_kakao(city, keywords)
        if "관광" in str(keywords): fetch_tourapi(city)
    else:
        if lat != 0: fetch_amadeus(city, lat, lng)

# 데이터를 구글 시트에서 한 번에 긁어오는 함수
def get_places(city, category_filter=None, limit=50):
    try:
        sheet = get_sheet()
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        
        if df.empty: return []
        
        # 도시 필터링
        filtered_df = df[df['city'].astype(str).str.contains(city)]
        
        # 리스트 딕셔너리로 변환
        return filtered_df.to_dict('records')
    except Exception as e:
        print(f"시트 읽기 오류: {e}")
        return []

# --- [backend.py 맨 아래에 추가] ---

def get_real_duration_kakao(origin_lat, origin_lng, dest_lat, dest_lng):
    """
    카카오 모빌리티 API를 사용하여 자동차 이동 시간을 초(seconds) 단위로 반환
    """
    if not MY_KAKAO_KEY: return 999999 # 키 없으면 무시
    
    url = "https://apis-navi.kakaomobility.com/v1/directions"
    headers = {"Authorization": f"KakaoAK {MY_KAKAO_KEY}"}
    
    # 카카오 네비는 "경도(lng),위도(lat)" 순서로 입력받습니다.
    params = {
        "origin": f"{origin_lng},{origin_lat}",
        "destination": f"{dest_lng},{dest_lat}",
        "priority": "RECOMMEND" # 추천경로
    }
    
    try:
        res = requests.get(url, headers=headers, params=params)
        data = res.json()
        # duration은 초 단위
        duration = data['routes'][0]['summary']['duration']
        return duration
    except:
        return 999999 # 에러 시 아주 큰 값 반환

# --- [backend.py 맨 아래에 추가] ---

def get_real_duration_google(origin_lat, origin_lng, dest_lat, dest_lng):
    """
    구글 Distance Matrix API를 사용하여 이동 시간(초)을 반환
    """
    if not MY_GOOGLE_KEY: return 999999
    
    try:
        # googlemaps 클라이언트 생성 (이미 상단에 import googlemaps 되어 있어야 함)
        gmaps = googlemaps.Client(key=MY_GOOGLE_KEY)
        
        # 거리 행렬 조회 (mode='driving' 또는 'walking', 'transit')
        # 해외 여행지 특성에 맞춰 'driving'(차량) 또는 'walking'(도보) 권장
        result = gmaps.distance_matrix(
            origins=(origin_lat, origin_lng),
            destinations=(dest_lat, dest_lng),
            mode="driving" 
        )
        
        # 응답 파싱
        element = result['rows'][0]['elements'][0]
        if element['status'] == 'OK':
            # duration['value']는 초(seconds) 단위
            return element['duration']['value']
        else:
            return 999999
    except Exception as e:
        print(f"Google Maps API Error: {e}")
        return 999999