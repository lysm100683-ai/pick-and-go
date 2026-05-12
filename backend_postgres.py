# backend_postgres.py - PostGIS를 활용한 새로운 backend 모듈
"""
PostgreSQL + PostGIS 기반 백엔드 모듈
기존 backend.py의 SQLite 대신 PostGIS 네이티브 쿼리를 사용합니다.
"""
from sqlalchemy import func, and_, or_
from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_MakePoint, ST_X, ST_Y, ST_GeomFromEWKB
from geoalchemy2 import WKTElement
from db.connection import get_db_session
from db.models import Place, MovementCache
from config import Config
from datetime import datetime, timedelta
import concurrent.futures
import requests
import googlemaps
import logging
import re

# 로거 설정
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. 영업 상태 확인
# ---------------------------------------------------------------------------
def check_place_status(lat: float, lng: float, name: str) -> bool:
    """
    Google Places API를 통해 장소의 현재 영업 여부를 확인.
    API 키 미설정 또는 조회 실패 시 True(통과)를 반환하여 필터링을 우회.

    Args:
        lat, lng: 장소 좌표
        name: 장소명 (검색 쿼리용)

    Returns:
        True = 영업 중 (또는 불명), False = 현재 영업 안 함
    """
    if not Config.GMAPS_API_KEY or Config.GMAPS_API_KEY == 'YOUR_GOOGLE_MAPS_API_KEY':
        return True  # API 키 없으면 모든 장소 통과

    try:
        gmaps = googlemaps.Client(key=Config.GMAPS_API_KEY)

        # ① Find Place로 place_id 획득
        find_result = gmaps.find_place(
            input=f"{name} {lat},{lng}",
            input_type="textquery",
            fields=["place_id"],
            location_bias=f"circle:500@{lat},{lng}"
        )
        candidates = find_result.get("candidates", [])
        if not candidates:
            return True

        place_id = candidates[0]["place_id"]

        # ② Place Details로 opening_hours 확인
        details = gmaps.place(
            place_id=place_id,
            fields=["opening_hours"]
        )
        opening_hours = details.get("result", {}).get("opening_hours", {})

        # open_now 필드가 있으면 그 값 사용, 없으면 통과
        return opening_hours.get("open_now", True)

    except Exception as e:
        logger.debug(f"check_place_status 조회 실패 ({name}): {e} — 통과 처리")
        return True


# ---------------------------------------------------------------------------
# 2. 장소명 — 영문 상호명/장소명은 원본 그대로 유지
# ---------------------------------------------------------------------------
def translate_place_name(name: str) -> str:
    """
    장소명은 번역하지 않고 원본 반환.
    (영문 상호명·브랜드명은 원문 유지 정책)
    """
    return name if name else name


# ---------------------------------------------------------------------------
# 3. 주소 한국어 변환 — Google Geocoding API(language=ko) 우선, fallback deep-translator
# ---------------------------------------------------------------------------
def translate_address(address: str) -> str:
    """
    영문 주소를 한국식 표기로 변환.
    - 이미 한국어 포함 시 원본 반환
    - Google Geocoding API(language=ko)로 공식 한국어 주소 획득
    - API 키 없거나 실패 시 deep-translator로 텍스트 번역
    """
    if not address:
        return address
    # 이미 한국어 포함이면 그대로
    if re.search(r'[\uAC00-\uD7A3]', address):
        return address

    # 1순위: Google Geocoding API로 한국어 주소 획득
    if Config.GMAPS_API_KEY and Config.GMAPS_API_KEY != 'YOUR_GOOGLE_MAPS_API_KEY':
        try:
            gmaps = googlemaps.Client(key=Config.GMAPS_API_KEY)
            results = gmaps.geocode(address, language='ko')
            if results:
                return results[0].get('formatted_address', address)
        except Exception as e:
            logger.debug(f"Geocoding 주소 변환 실패 ({address[:30]}): {e}")

    # 2순위: deep-translator fallback
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source='auto', target='ko').translate(address)
        return translated if translated else address
    except Exception as e:
        logger.debug(f"번역 실패 ({address[:30]}): {e} — 원본 반환")
        return address





def get_places(city: str, category_filter: str = None, limit: int = 50) -> list:
    """
    PostGIS를 활용한 장소 조회
    
    Args:
        city: 도시 이름
        category_filter: 카테고리 필터 (선택)
        limit: 최대 결과 수
    
    Returns:
        장소 리스트 (딕셔너리 형태)
    """
    with get_db_session() as session:
        # 🚀 최적화: 좌표 추출을 메인 쿼리에 포함 (N+1 쿼리 방지)
        query = session.query(
            Place,
            func.ST_X(func.ST_GeomFromEWKB(Place.location)).label('lng'),
            func.ST_Y(func.ST_GeomFromEWKB(Place.location)).label('lat')
        ).filter(Place.city.contains(city))
        
        if category_filter:
            query = query.filter(Place.category.contains(category_filter))
        
        # 평점 높은 순으로 정렬
        query = query.order_by(Place.rating.desc()).limit(limit)
        
        results = query.all()
        
        # ORM 객체를 딕셔너리로 변환
        return [
            {
                'id': p.id,
                'source': p.source,
                'name': p.name,
                'city': p.city,
                'category': p.category,
                'lat': lat,
                'lng': lng,
                'address': p.address or '',
                'rating': float(p.rating) if p.rating else 0.0,
                'img_url': p.img_url or '',
                'desc': p.description or ''
            }
            for p, lng, lat in results
        ]


def get_places_within_radius(lat: float, lng: float, radius_meters: int, 
                             city: str = None, min_rating: float = 0.0) -> list:
    """
    🚀 NEW: 특정 위치로부터 반경 내 장소 검색 (PostGIS 네이티브 함수 사용)
    
    Args:
        lat: 중심 위도
        lng: 중심 경도
        radius_meters: 검색 반경 (미터)
        city: 도시 필터 (선택)
        min_rating: 최소 평점 (선택)
    
    Returns:
        거리순으로 정렬된 장소 리스트
    """
    with get_db_session() as session:
        # 중심점 생성 (WGS84, SRID 4326)
        center_wkt = f'SRID=4326;POINT({lng} {lat})'
        center = WKTElement(center_wkt, srid=4326)
        
        # 거리 계산 및 좌표 추출을 메인 쿼리에 포함
        distance = func.ST_Distance(Place.location, center).label('distance')
        
        query = session.query(
            Place,
            distance,
            func.ST_X(func.ST_GeomFromEWKB(Place.location)).label('lng'),
            func.ST_Y(func.ST_GeomFromEWKB(Place.location)).label('lat')
        ).filter(
            func.ST_DWithin(Place.location, center, radius_meters)
        )
        
        # 추가 필터
        if city:
            query = query.filter(Place.city == city)
        if min_rating > 0:
            query = query.filter(Place.rating >= min_rating)
        
        # 거리순 정렬
        query = query.order_by(distance)
        
        results = query.all()
        
        # 결과 변환
        return [
            {
                'id': p.id,
                'name': p.name,
                'source': p.source,
                'city': p.city,
                'category': p.category,
                'lat': p_lat,
                'lng': p_lng,
                'address': p.address or '',
                'rating': float(p.rating) if p.rating else 0.0,
                'img_url': p.img_url or '',
                'desc': p.description or '',
                'distance_km': round(dist / 1000, 2)  # 미터 → 킬로미터
            }
            for p, dist, p_lng, p_lat in results
        ]


def save_place(place_data: dict):
    """
    장소 저장 (PostGIS 포맷)
    
    Args:
        place_data: 장소 정보 딕셔너리
            - id, source, name, city, category
            - lat, lng (좌표)
            - address, rating, img_url, desc
    """
    with get_db_session() as session:
        # 중복 체크
        existing = session.query(Place).filter(Place.id == place_data['id']).first()
        
        if existing:
            # 업데이트
            existing.rating = place_data.get('rating', existing.rating)
            existing.img_url = place_data.get('img_url', existing.img_url)
            existing.updated_at = datetime.now()
        else:
            # 새로 추가
            location_wkt = f'SRID=4326;POINT({place_data["lng"]} {place_data["lat"]})'
            
            new_place = Place(
                id=place_data['id'],
                source=place_data['source'],
                name=place_data['name'],
                city=place_data['city'],
                category=place_data.get('category', ''),
                location=WKTElement(location_wkt, srid=4326),
                address=place_data.get('address', ''),
                rating=place_data.get('rating', 0.0),
                img_url=place_data.get('img_url', ''),
                description=place_data.get('desc', '')
            )
            session.add(new_place)


def get_movement_cache(origin_lat: float, origin_lng: float, 
                       dest_lat: float, dest_lng: float, mode: str) -> int | None:
    """
    이동 시간 캐시 조회 (PostGIS 좌표 사용)
    
    Returns:
        캐시된 이동 시간(초) 또는 None
    """
    with get_db_session() as session:
        origin_wkt = f'SRID=4326;POINT({origin_lng} {origin_lat})'
        dest_wkt = f'SRID=4326;POINT({dest_lng} {dest_lat})'
        
        origin_point = WKTElement(origin_wkt, srid=4326)
        dest_point = WKTElement(dest_wkt, srid=4326)
        
        # 정방향 또는 역방향 캐시 검색 (거리 기반으로 매칭)
        # Config.CACHE_MATCH_TOLERANCE_METERS 이내면 동일 좌표로 간주
        # 180일(6개월) 캐시 유통기한(TTL) 적용 (오래된 데이터는 버리고 새로 API 호출)
        limit_date = datetime.now() - timedelta(days=180)

        cache = session.query(MovementCache).filter(
            or_(
                and_(
                    # 정방향: origin → dest (ST_DWithin으로 공간 인덱스(GiST) 적극 활용)
                    func.ST_DWithin(MovementCache.origin, origin_point, Config.CACHE_MATCH_TOLERANCE_METERS),
                    func.ST_DWithin(MovementCache.destination, dest_point, Config.CACHE_MATCH_TOLERANCE_METERS),
                    MovementCache.mode == mode,
                    MovementCache.created_at >= limit_date
                ),
                and_(
                    # 역방향: dest → origin
                    func.ST_DWithin(MovementCache.origin, dest_point, Config.CACHE_MATCH_TOLERANCE_METERS),
                    func.ST_DWithin(MovementCache.destination, origin_point, Config.CACHE_MATCH_TOLERANCE_METERS),
                    MovementCache.mode == mode,
                    MovementCache.created_at >= limit_date
                )
            )
        ).first()
        
        return cache.duration_seconds if cache else None


def save_movement_cache(origin_lat: float, origin_lng: float, 
                       dest_lat: float, dest_lng: float, 
                       mode: str, duration: int, is_korea: bool):
    """
    이동 시간 캐시 저장 (중복 방지)
    
    Args:
        origin_lat, origin_lng: 출발지 좌표
        dest_lat, dest_lng: 목적지 좌표
        mode: 이동 수단
        duration: 이동 시간 (초)
        is_korea: 한국 여부
    """
    # 이미 캐시된 경우 스킵
    existing = get_movement_cache(origin_lat, origin_lng, dest_lat, dest_lng, mode)
    if existing:
        logger.debug(f"이동 시간 캐시 이미 존재 (duration: {existing}초), 스킵")
        return
    
    with get_db_session() as session:
        origin_wkt = f'SRID=4326;POINT({origin_lng} {origin_lat})'
        dest_wkt = f'SRID=4326;POINT({dest_lng} {dest_lat})'
        
        new_cache = MovementCache(
            origin=WKTElement(origin_wkt, srid=4326),
            destination=WKTElement(dest_wkt, srid=4326),
            mode=mode,
            duration_seconds=duration,
            is_korea=is_korea
        )
        session.add(new_cache)
        logger.info(f"새 이동 시간 캐시 저장: {duration}초 (mode: {mode}, is_korea: {is_korea})")


def cleanup_old_movement_cache(days: int = 180):
    """
    유통기한(TTL)이 지난 과거 이동시간 캐시 데이터를 DB에서 영구 삭제합니다.
    (앱 구동 시나 DB 업데이트 시 비동기적으로 실행하여 DB 찌꺼기를 방지)
    """
    limit_date = datetime.now() - timedelta(days=days)
    try:
        with get_db_session() as session:
            deleted_count = session.query(MovementCache).filter(
                MovementCache.created_at < limit_date
            ).delete()
            session.commit()
            if deleted_count > 0:
                logger.info(f"유통기한 경과된 과거 이동시간 캐시 {deleted_count}건 삭제 완료 ({days}일 초과 데이터).")
    except Exception as e:
        logger.error(f"오래된 이동시간 캐시 삭제 중 오류 발생: {e}", exc_info=True)


# 🚀 기존 backend.py의 API 호출 함수들을 그대로 복사 (travel_logic.py에서 사용)
def get_real_duration_kakao(lat1, lng1, lat2, lng2, mode='driving'):
    """Kakao API를 사용하여 실제 이동 시간을 조회합니다."""
    
    if lat1 == 0.0 or lng1 == 0.0 or lat2 == 0.0 or lng2 == 0.0:
        logger.warning(f"유효하지 않은 좌표: ({lat1}, {lng1}) → ({lat2}, {lng2})")
        return 999999
    
    if not Config.KAKAO_REST_KEY or Config.KAKAO_REST_KEY == "YOUR_KAKAO_REST_API_KEY":
        logger.warning("Kakao API 키가 설정되지 않아 기본값(30분) 반환")
        return 30*60
    
    # 캐시 확인
    cached = get_movement_cache(lat1, lng1, lat2, lng2, mode)
    if cached is not None:
        logger.debug(f"캐시된 이동 시간 사용: {cached}초")
        return cached
    
    # API 호출
    if mode == 'transit':
        url = "https://apis-navi.kakaomobility.com/v1/public-transit/directions"
        params = {
            "origin": f"{lng1},{lat1}",
            "destination": f"{lng2},{lat2}",
            "departure_time": datetime.now().strftime("%Y%m%d%H%M%S")
        }
    else:
        url = "https://apis-navi.kakaomobility.com/v1/directions"
        params = {
            "origin": f"{lng1},{lat1}",
            "destination": f"{lng2},{lat2}",
            "priority": "RECOMMEND"
        }
    
    try:
        res = requests.get(
            url, 
            headers={"Authorization": f"KakaoAK {Config.KAKAO_REST_KEY}"}, 
            params=params, 
            timeout=2
        )
        res.raise_for_status()  # HTTP 에러 발생 시 예외
        
        data = res.json()
        
        duration_seconds = None
        if data.get('routes'):
            duration_seconds = data['routes'][0].get('summary', {}).get('duration')
        
        if duration_seconds is None:
            # result_code 103(경로 없음) 등 Kakao 실패 시 —
            # Google Maps API를 폴백 호출하는 대신, Haversine 직선거리로 이동시간 추정.
            # (도시 내에서는 실제 도로거리의 약 1.3배가 직선거리)
            import math
            R = 6371
            dlat = math.radians(lat2 - lat1)
            dlng = math.radians(lng2 - lng1)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
            dist_km = 2 * R * math.asin(math.sqrt(a))
            speed_kmh = 30 if mode == 'driving' else 4
            duration_seconds = max(300, int(dist_km / speed_kmh * 3600 * 1.3))  # 최소 5분
            logger.info(f"Kakao duration 없음 → Haversine 추정: {dist_km:.2f}km → {duration_seconds}초 (result: {data.get('routes', [{}])[0].get('result_code', '?') if data.get('routes') else data.get('msg', '')})")            
        
        # 쳠시 저장
        save_movement_cache(lat1, lng1, lat2, lng2, mode, duration_seconds, is_korea=True)
        logger.info(f"Kakao API 이동 시간 조회 성공: {duration_seconds}초 (mode: {mode})")
        return duration_seconds
        
    except requests.exceptions.Timeout:
        logger.error(f"Kakao API 타임아웃: ({lat1},{lng1}) → ({lat2},{lng2})")
        return 999999
    except requests.exceptions.HTTPError as e:
        logger.error(f"Kakao API HTTP 에러: {e.response.status_code} - {e.response.text}")
        return 999999
    except requests.exceptions.RequestException as e:
        logger.error(f"Kakao API 요청 실패: {e}", exc_info=True)
        return 999999
    except Exception as e:
        logger.critical(f"Kakao API 예상치 못한 오류: {e}", exc_info=True)
        return 999999


def get_real_duration_google_bulk(lat1, lng1, candidates, mode='driving'):
    """
    Google Distance Matrix API로 여러 목적지까지의 이동 시간을 한 번에 조회
    (기존: gmaps.directions() N번 반복 → 개선: gmaps.distance_matrix() 1번)
    """
    
    if lat1 == 0.0 or lng1 == 0.0:
        logger.warning(f"유효하지 않은 출발지 좌표: ({lat1}, {lng1})")
        return [(999999, p) for p in candidates]
    
    if not Config.GMAPS_API_KEY or Config.GMAPS_API_KEY == "YOUR_GOOGLE_MAPS_API_KEY":
        logger.warning("Google Maps API 키가 설정되지 않아 기본값(30분) 반환")
        return [(30*60, p) for p in candidates]
    
    gmaps = googlemaps.Client(key=Config.GMAPS_API_KEY)
    results_map = {}   # dest index → duration
    uncached_indices = []  # 쳠시 미스 candidates의 원래 index

    # 1단계: 쳠시에서 먼저 확인
    for i, p in enumerate(candidates):
        if p['lat'] == 0.0 or p['lng'] == 0.0:
            results_map[i] = (999999, p)
            continue
        cached = get_movement_cache(lat1, lng1, p['lat'], p['lng'], mode)
        if cached is not None:
            logger.debug(f"쳠시된 이동 시간 사용: {p.get('name', 'Unknown')} - {cached}초")
            results_map[i] = (cached, p)
        else:
            uncached_indices.append(i)

    # 2단계: 쳠시 미스는 Distance Matrix API 단일 호출로 일괄 조회
    if uncached_indices:
        uncached_places = [candidates[i] for i in uncached_indices]
        try:
            matrix = gmaps.distance_matrix(
                origins=[f"{lat1},{lng1}"],
                destinations=[f"{p['lat']},{p['lng']}" for p in uncached_places],
                mode=mode,
                departure_time=datetime.now()
            )
            logger.info(f"Google Distance Matrix API 1회 호출로 {len(uncached_places)}개 검색 완료")

            row = matrix.get('rows', [{}])[0]
            for j, p in enumerate(uncached_places):
                orig_i = uncached_indices[j]
                try:
                    element = row['elements'][j]
                    if element['status'] == 'OK':
                        duration_seconds = element['duration']['value']
                    else:
                        logger.warning(f"Google Matrix 요소 실패 ({element.get('status')}): {p.get('name', 'Unknown')}")
                        duration_seconds = 999999
                except (KeyError, IndexError) as e:
                    logger.warning(f"Google Matrix 재파싱 오류: {e}")
                    duration_seconds = 999999

                if duration_seconds != 999999:
                    save_movement_cache(lat1, lng1, p['lat'], p['lng'], mode, duration_seconds, is_korea=False)
                results_map[orig_i] = (duration_seconds, p)

        except Exception as e:
            logger.error(f"Google Distance Matrix API 오류: {e}", exc_info=True)
            for i, p in zip(uncached_indices, uncached_places):
                results_map[i] = (999999, p)

    # 원래 순서 유지
    return [results_map[i] for i in range(len(candidates))]


# ---------------------------------------------------------------------------
# 데이터 수집 함수 (기존 backend.py에서 이식, SQLite→PostGIS 교체)
# ---------------------------------------------------------------------------

# 수집 데이터 임시 버퍼 (save_bulk_data() 호출 전까지 DB 미저장)
_temp_data_buffer: list = []


def _buffer_place(data: dict):
    """
    수집된 장소 데이터를 메모리 버퍼에 임시 저장.
    save_bulk_data() 호출 시 일괄 UPSERT됩니다.
    """
    global _temp_data_buffer
    if not any(item['id'] == data['id'] for item in _temp_data_buffer):
        data.setdefault('desc', '')
        data.setdefault('rating', 0.0)
        data.setdefault('address', '')
        data.setdefault('img_url', '')
        _temp_data_buffer.append(data)


def save_bulk_data() -> int:
    """
    버퍼에 쌓인 장소 데이터를 PostgreSQL에 일괄 UPSERT합니다.
    중복 id는 rating, img_url만 갱신합니다.

    Returns:
        UPSERT된 건수
    """
    global _temp_data_buffer
    if not _temp_data_buffer:
        return 0

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    rows = []
    for data in _temp_data_buffer:
        lat = float(data.get('lat', 0.0))
        lng = float(data.get('lng', 0.0))
        if lat == 0.0 or lng == 0.0:
            continue  # 좌표 없는 데이터 제외
        rows.append({
            'id':          str(data['id']),
            'source':      data['source'],
            'name':        data['name'],
            'city':        data['city'],
            'category':    data.get('category', ''),
            'location':    WKTElement(f'SRID=4326;POINT({lng} {lat})', srid=4326),
            'address':     data.get('address', ''),
            'rating':      float(data.get('rating', 0.0)),
            'img_url':     data.get('img_url', ''),
            'description': data.get('desc', ''),
        })

    if not rows:
        _temp_data_buffer = []
        return 0

    # PostgreSQL 바인딩 한계(32767) 기준: 컬럼 9개 → 최대 3000건/배치
    BATCH_SIZE = 3000
    added_count = 0

    try:
        with get_db_session() as session:
            for i in range(0, len(rows), BATCH_SIZE):
                batch = rows[i:i + BATCH_SIZE]
                stmt = pg_insert(Place).values(batch)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['id'],
                    set_={
                        'rating':  stmt.excluded.rating,
                        'img_url': stmt.excluded.img_url,
                    }
                )
                session.execute(stmt)
            added_count = len(rows)
        logger.info(f"save_bulk_data: {added_count}건 UPSERT 완료")
    except Exception as e:
        logger.error(f"save_bulk_data UPSERT 실패: {e}", exc_info=True)
        added_count = 0
    finally:
        _temp_data_buffer = []

    return added_count


def fetch_google(city: str, keywords: list):
    """
    Google Places API로 장소 데이터 수집 → 버퍼(_temp_data_buffer)에 임시 저장
    """
    if not Config.GMAPS_API_KEY or Config.GMAPS_API_KEY == 'YOUR_GOOGLE_MAPS_API_KEY':
        return

    gmaps = googlemaps.Client(key=Config.GMAPS_API_KEY)

    for keyword in keywords:
        try:
            res = gmaps.places(query=f"{city} {keyword}")

            status = res.get('status')
            if status != 'OK' and status != 'ZERO_RESULTS':
                logger.warning(f"[Google API] '{keyword}' 검색 실패. Status: {status}")
            if status != 'OK':
                continue

            for p in res.get('results', []):
                img = ""
                if 'photos' in p:
                    ref = p['photos'][0]['photo_reference']
                    img = (f"https://maps.googleapis.com/maps/api/place/photo"
                           f"?maxwidth=400&photoreference={ref}&key={Config.GMAPS_API_KEY}")

                lat = p['geometry']['location'].get('lat') or 0.0
                lng = p['geometry']['location'].get('lng') or 0.0

                _buffer_place({
                    "id":       f"google_{p['place_id']}",
                    "source":   "google",
                    "name":     p['name'],
                    "city":     city,
                    "category": p.get('types', ['place'])[0],
                    "lat":      lat,
                    "lng":      lng,
                    "address":  p.get('formatted_address', ''),
                    "rating":   p.get('rating', 0.0),
                    "img_url":  img,
                    "desc":     "Google",
                })
        except Exception as e:
            logger.error(f"[Google API] '{keyword}' 처리 중 오류: {e}")


def fetch_kakao(city: str, keywords: list):
    """
    Kakao 로컬 API로 장소 데이터 수집 → 버퍼(_temp_data_buffer)에 임시 저장 (국내 전용)
    """
    if not Config.KAKAO_REST_KEY or Config.KAKAO_REST_KEY == 'YOUR_KAKAO_REST_API_KEY':
        return

    headers = {"Authorization": f"KakaoAK {Config.KAKAO_REST_KEY}"}

    for keyword in keywords:
        try:
            res = requests.get(
                "https://dapi.kakao.com/v2/local/search/keyword.json",
                headers=headers,
                params={"query": f"{city} {keyword}", "size": 15},
                timeout=5,
            )
            for p in res.json().get('documents', []):
                _buffer_place({
                    "id":       f"kakao_{p['id']}",
                    "source":   "kakao",
                    "name":     p['place_name'],
                    "city":     city,
                    "category": p['category_name'].split('>')[-1].strip(),
                    "lat":      float(p.get('y', 0.0)),
                    "lng":      float(p.get('x', 0.0)),
                    "address":  p['road_address_name'],
                    "rating":   0.0,
                    "img_url":  p['place_url'],
                    "desc":     p['phone'],
                })
        except Exception as e:
            logger.error(f"[Kakao API] '{keyword}' 처리 중 오류: {e}")


def fetch_tourapi(city: str):
    """
    한국관광공사 TourAPI로 관광지 데이터 수집 (국내 전용)
    TODO: TourAPI 서비스키 발급 후 구현 필요
          - 국내 관광지 공식 데이터로 Google/Kakao 누락분 보완 목적
          - data.go.kr 에서 '국문관광정보서비스' 신청
    """
    pass


def fetch_all_data(city: str, keywords: list,
                   api_keys=None, lat: float = 0, lng: float = 0,
                   is_domestic: bool = True) -> dict:
    """
    데이터 수집 진입점 — 병렬 수집 후 버퍼를 일괄 UPSERT합니다.

    Args:
        city: 수집 대상 도시
        keywords: 검색 키워드 리스트
        api_keys: (미사용, 하위 호환용)
        lat, lng: 해외 도시 좌표 (미사용, 하위 호환용)
        is_domestic: 국내 여부 (Kakao/TourAPI 호출 여부 결정)

    Returns:
        {"added_count": int, "final_count": int}
    """
    logger.info(f"[Update] '{city}' 데이터 수집 시작...")

    # Google 수집을 키워드별 병렬 처리
    tasks = [lambda k=kw: fetch_google(city, [k]) for kw in keywords]

    if is_domestic:
        fetch_kakao(city, keywords)
        fetch_tourapi(city)
    # fetch_amadeus는 Phase 4 예약 기능 구현 시 추가 예정

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(task) for task in tasks]
        concurrent.futures.wait(futures)

    added_count = save_bulk_data()
    final_count = len(get_places(city))

    logger.info(f"[Finish] '{city}' 완료. 추가: {added_count}건, 최종: {final_count}건")
    return {"added_count": added_count, "final_count": final_count}
