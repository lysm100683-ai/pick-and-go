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
from datetime import datetime
import concurrent.futures
import requests
import googlemaps
import logging
import re

# 로거 설정
logger = logging.getLogger(__name__)

# ─── 성능 최적화: googlemaps 클라이언트 싱글톤 ───────────────────────
# 매 호출마다 Client()를 새로 생성하면 "queries_quota" 로그가 반복되고
# 초기화 오버헤드가 쌓여 100초+ 지연의 원인이 됨 → 모듈 로드 시 1회만 생성
_gmaps_client_instance: object | None = None

def _get_gmaps_client():
    """googlemaps.Client 싱글톤 반환. API 키 미설정 시 None 반환."""
    global _gmaps_client_instance
    if _gmaps_client_instance is None:
        if Config.GMAPS_API_KEY and Config.GMAPS_API_KEY != 'YOUR_GOOGLE_MAPS_API_KEY':
            try:
                _gmaps_client_instance = googlemaps.Client(key=Config.GMAPS_API_KEY)
            except Exception as e:
                logger.warning(f"[GmapsClient] 초기화 실패: {e}")
    return _gmaps_client_instance


# ─── 성능 최적화: 주소 번역 결과 캐시 ───────────────────────────────
# translate_address()가 _make_place()에서 장소마다 호출되므로
# 동일 주소 반복 번역 방지를 위해 간단한 in-memory 캐시 적용
_addr_translation_cache: dict = {}


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

    # 캐시 확인 (동일 영문 주소 반복 번역 방지)
    if address in _addr_translation_cache:
        return _addr_translation_cache[address]

    # 1순위: Google Geocoding API로 한국어 주소 획득 (싱글톤 클라이언트 재사용)
    gmaps = _get_gmaps_client()
    if gmaps:
        try:
            results = gmaps.geocode(address, language='ko')
            if results:
                translated = results[0].get('formatted_address', address)
                _addr_translation_cache[address] = translated
                return translated
        except Exception as e:
            logger.debug(f"Geocoding 주소 변환 실패 ({address[:30]}): {e}")

    # 2순위: deep-translator fallback
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source='auto', target='ko').translate(address)
        result = translated if translated else address
        _addr_translation_cache[address] = result
        return result
    except Exception as e:
        logger.debug(f"번역 실패 ({address[:30]}): {e} — 원본 반환")
        return address





def get_places(city: str, category_filter: str = None, limit: int = 200) -> list:
    """
    PostGIS를 활용한 장소 조회
    
    Args:
        city: 도시 이름
        category_filter: 카테고리 필터 (선택)
        limit: 최대 결과 수
    
    Returns:
        장소 리스트 (딕셔너리 형태)
    """
    from datetime import datetime, timezone  # 경과일 계산용
    
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
        # ★ limit 기본값 200: extract_top_n(일수×5) 이후에도 충분한 풀이 남도록
        #   limit=50 하드캡이면 cafes, foods가 부족해 fallback 장소가 배치될 수 있음
        query = query.order_by(Place.rating.desc()).limit(limit)
        
        results = query.all()
        now = datetime.now(timezone.utc)
        
        # ORM 객체를 딕셔너리로 변환
        places = []
        for p, lng, lat in results:
            # verified_at 기준 경과 일수 계산
            # None(미확인) → days_since_verified = None (프론트에서 고위험 처리)
            days_since_verified = None
            if p.verified_at:
                vat = p.verified_at
                if vat.tzinfo is None:
                    vat = vat.replace(tzinfo=timezone.utc)
                days_since_verified = (now - vat).days
            
            # updated_at 기준 경과 일수 (점수 최신성 보정용)
            days_since_updated = None
            if p.updated_at:
                uat = p.updated_at
                if uat.tzinfo is None:
                    uat = uat.replace(tzinfo=timezone.utc)
                days_since_updated = (now - uat).days
            
            places.append({
                'id':                   p.id,
                'source':               p.source,
                'name':                 p.name,
                'city':                 p.city,
                'category':             p.category,
                'sub_category':         p.sub_category or '',
                'lat':                  lat,
                'lng':                  lng,
                'address':              p.address or '',
                'rating':               float(p.rating) if p.rating else 0.0,
                'review_count':         int(p.review_count) if p.review_count else 0,
                # ★ 별점 분포 데이터 (scoring_service._distribution_bonus()에서 사용)
                'rating_5star':         int(p.rating_5star) if p.rating_5star else 0,
                'rating_4star':         int(p.rating_4star) if p.rating_4star else 0,
                'rating_3star':         int(p.rating_3star) if p.rating_3star else 0,
                'rating_2star':         int(p.rating_2star) if p.rating_2star else 0,
                'rating_1star':         int(p.rating_1star) if p.rating_1star else 0,
                'img_url':              p.img_url or '',
                'desc':                 p.description or '',
                # 영업 상태 경고용 필드
                'verified_at':          p.verified_at.isoformat() if p.verified_at else None,
                'days_since_verified':  days_since_verified,
                # 점수 최신성 보정용 필드
                'updated_at':           p.updated_at.isoformat() if p.updated_at else None,
                'days_since_updated':   days_since_updated,
            })
        
        return places


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
        # ST_DWithin → GIST 인덱스(idx_movement_cache_origin/destination) 활용 (ST_Distance < 는 풀 스캔)
        cache = session.query(MovementCache).filter(
            or_(
                and_(
                    # 정방향: origin → dest
                    func.ST_DWithin(MovementCache.origin, origin_point, Config.CACHE_MATCH_TOLERANCE_METERS),
                    func.ST_DWithin(MovementCache.destination, dest_point, Config.CACHE_MATCH_TOLERANCE_METERS),
                    MovementCache.mode == mode
                ),
                and_(
                    # 역방향: dest → origin
                    func.ST_DWithin(MovementCache.origin, dest_point, Config.CACHE_MATCH_TOLERANCE_METERS),
                    func.ST_DWithin(MovementCache.destination, origin_point, Config.CACHE_MATCH_TOLERANCE_METERS),
                    MovementCache.mode == mode
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
    try:
        existing = get_movement_cache(origin_lat, origin_lng, dest_lat, dest_lng, mode)
    except Exception:
        existing = None
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


# 🚀 기존 backend.py의 API 호출 함수들을 그대로 복사 (travel_logic.py에서 사용)
def get_real_duration_kakao(lat1, lng1, lat2, lng2, mode='driving'):
    """Kakao API를 사용하여 실제 이동 시간을 조회합니다."""
    
    if lat1 == 0.0 or lng1 == 0.0 or lat2 == 0.0 or lng2 == 0.0:
        logger.warning(f"유효하지 않은 좌표: ({lat1}, {lng1}) → ({lat2}, {lng2})")
        return 999999
    
    if not Config.KAKAO_REST_KEY or Config.KAKAO_REST_KEY == "YOUR_KAKAO_REST_API_KEY":
        logger.warning("Kakao API 키가 설정되지 않아 기본값(30분) 반환")
        return 30*60
    
    # 캐시 확인 (movement_cache 테이블 미존재 시 ProgrammingError 방어)
    try:
        cached = get_movement_cache(lat1, lng1, lat2, lng2, mode)
        if cached is not None:
            logger.debug(f"캐시된 이동 시간 사용: {cached}초")
            return cached
    except Exception as e:
        logger.warning(f"movement_cache 조회 실패 (테이블 미존재?): {e}")

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
            logger.warning(f"Kakao API 응답에 duration 없음: {data}")
            return 999999
        
        # 캐시 저장
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
    """Google Directions API를 사용하여 여러 목적지까지의 이동 시간을 조회"""
    
    if lat1 == 0.0 or lng1 == 0.0:
        logger.warning(f"유효하지 않은 출발지 좌표: ({lat1}, {lng1})")
        return [(999999, p) for p in candidates]
    
    if not Config.GMAPS_API_KEY or Config.GMAPS_API_KEY == "YOUR_GOOGLE_MAPS_API_KEY":
        logger.warning("Google Maps API 키가 설정되지 않아 기본값(30분) 반환")
        return [(30*60, p) for p in candidates]

    # 싱글톤 클라이언트 사용 (매 호출마다 새 Client 생성 방지)
    gmaps = _get_gmaps_client()
    if gmaps is None:
        return [(30*60, p) for p in candidates]
    results = []
    
    for p in candidates:
        if p['lat'] == 0.0 or p['lng'] == 0.0:
            logger.warning(f"유효하지 않은 목적지 좌표: {p.get('name', 'Unknown')} ({p['lat']}, {p['lng']})")
            results.append((999999, p))
            continue
        
        # 캐시 확인 (movement_cache 테이블 미존재 시 방어)
        try:
            cached = get_movement_cache(lat1, lng1, p['lat'], p['lng'], mode)
        except Exception as e:
            logger.warning(f"movement_cache 조회 실패: {e}")
            cached = None
        if cached is not None:
            logger.debug(f"캐시된 이동 시간 사용: {p.get('name', 'Unknown')} - {cached}초")
            results.append((cached, p))
            continue

        try:
            directions_result = gmaps.directions(
                origin=f"{lat1},{lng1}",
                destination=f"{p['lat']},{p['lng']}",
                mode=mode,
                departure_time=datetime.now()
            )
            
            duration_seconds = 999999
            if directions_result and directions_result[0]['legs']:
                duration_seconds = directions_result[0]['legs'][0]['duration']['value']
            else:
                logger.warning(f"Google API 응답에 경로 없음: {p.get('name', 'Unknown')}")
            
            save_movement_cache(lat1, lng1, p['lat'], p['lng'], mode, duration_seconds, is_korea=False)
            results.append((duration_seconds, p))
            logger.info(f"Google API 이동 시간 조회 성공: {p.get('name', 'Unknown')} - {duration_seconds}초")
            
        except googlemaps.exceptions.ApiError as e:
            logger.error(f"Google API 에러 ({p.get('name', 'Unknown')}): {e}")
            results.append((999999, p))
        except googlemaps.exceptions.Timeout:
            logger.error(f"Google API 타임아웃: {p.get('name', 'Unknown')}")
            results.append((999999, p))
        except Exception as e:
            logger.error(f"Google API 예상치 못한 오류 ({p.get('name', 'Unknown')}): {e}", exc_info=True)
            results.append((999999, p))
    
    return results




# ===========================================================================
#  데이터 수집 함수 (Google Places API + Kakao Local API)
#  review_count(리뷰 수)를 포함하여 DB에 저장
# ===========================================================================

def _upsert_place(session, place_data: dict) -> bool:
    """
    장소 데이터를 DB에 Upsert (없으면 INSERT, 있으면 UPDATE).

    중복 기준: id (primary key)
    기존 장소의 rating·review_count·description은 새 값으로 갱신.
    verified_at은 수집 시점으로 갱신 (방금 수집 = 영업 확인 완료와 동일).

    Returns:
        True  = 신규 삽입
        False = 기존 업데이트
    """
    from geoalchemy2 import WKTElement as WKT

    existing = session.query(Place).filter(Place.id == place_data['id']).first()
    now = datetime.utcnow()

    # PostGIS POINT(lng lat) 형식
    location_wkt = WKT(
        f"POINT({place_data['lng']} {place_data['lat']})",
        srid=4326
    )

    if existing:
        existing.rating        = place_data.get('rating', existing.rating)
        # review_count: 더 큰 값 유지 (Kakao 0값이 Google 수집분 덮어쓰기 방지)
        new_review = place_data.get('review_count', 0) or 0
        existing.review_count  = max(existing.review_count or 0, new_review)
        existing.description   = place_data.get('desc', existing.description)
        existing.sub_category  = place_data.get('sub_category', existing.sub_category)
        existing.img_url       = place_data.get('img_url', existing.img_url)
        existing.address       = place_data.get('address', existing.address)
        # ★ 별점 분포: 누적(+) 방식으로 저장
        #   이유: 수집할 때마다 상위 5개 리뷰 샘플이 쌓이므로,
        #         회차가 많아질수록 더 신뢰할 수 있는 경향 파악 가능
        existing.rating_5star  = (existing.rating_5star or 0) + (place_data.get('rating_5star', 0) or 0)
        existing.rating_4star  = (existing.rating_4star or 0) + (place_data.get('rating_4star', 0) or 0)
        existing.rating_3star  = (existing.rating_3star or 0) + (place_data.get('rating_3star', 0) or 0)
        existing.rating_2star  = (existing.rating_2star or 0) + (place_data.get('rating_2star', 0) or 0)
        existing.rating_1star  = (existing.rating_1star or 0) + (place_data.get('rating_1star', 0) or 0)
        existing.updated_at    = now
        existing.verified_at   = now
        return False

    else:
        new_place = Place(
            id           = place_data['id'],
            source       = place_data['source'],
            name         = place_data['name'],
            city         = place_data['city'],
            category     = place_data.get('category', ''),
            sub_category = place_data.get('sub_category', ''),
            location     = location_wkt,
            address      = place_data.get('address', ''),
            rating       = place_data.get('rating', 0.0),
            review_count = place_data.get('review_count', 0),
            rating_5star = place_data.get('rating_5star', 0),
            rating_4star = place_data.get('rating_4star', 0),
            rating_3star = place_data.get('rating_3star', 0),
            rating_2star = place_data.get('rating_2star', 0),
            rating_1star = place_data.get('rating_1star', 0),
            img_url      = place_data.get('img_url', ''),
            description  = place_data.get('desc', ''),
            verified_at  = now,
        )
        session.add(new_place)
        return True


def fetch_google(city: str, keywords: list, is_domestic: bool = False) -> dict:
    """
    Google Places API (Text Search)로 장소 수집 후 DB Upsert.

    수집 필드:
      - name, lat, lng, rating, user_ratings_total(→review_count),
        formatted_address, photos, types

    세부 카테고리 매핑 (types 기반):
      restaurant → 음식점,  cafe → 카페/디저트,
      tourist_attraction / museum / park → 명소/관광,
      lodging → 숙소,  bar / night_club → 술집

    Args:
        city:       도시명 (DB city 필드값)
        keywords:   검색 키워드 리스트
        is_domestic: 국내 여부 (현재는 동일 로직, 추후 분기 예정)

    Returns:
        {"added_count": int, "updated_count": int, "error": str | None}
    """
    if not Config.GMAPS_API_KEY or Config.GMAPS_API_KEY == 'YOUR_GOOGLE_MAPS_API_KEY':
        logger.warning("[fetch_google] GMAPS_API_KEY 미설정 — 수집 건너뜀")
        return {"added_count": 0, "updated_count": 0, "error": "API key not set"}

    # Google Places types → sub_category 매핑 테이블
    TYPE_TO_SUB = {
        "restaurant":          "음식점",
        "food":                "음식점",
        "meal_takeaway":       "음식점",
        "cafe":                "커피전문점",
        "bakery":              "베이커리",
        "bar":                 "이자카야",
        "night_club":          "이자카야",
        "lodging":             "호텔",
        "tourist_attraction":  "랜드마크",
        "museum":              "미술/박물관",
        "park":                "자연경관",
        "amusement_park":      "테마파크",
        "shopping_mall":       "백화점/몰",
        "department_store":    "백화점/몰",
        "market":              "전통시장",
        "art_gallery":         "미술/박물관",
        "spa":                 "자연경관",
        "aquarium":            "테마파크",
        "zoo":                 "테마파크",
    }

    # 싱글톤 클라이언트 사용 (데이터 수집도 동일 인스턴스 재사용)
    gmaps_client = _get_gmaps_client()
    if gmaps_client is None:
        return {"added_count": 0, "updated_count": 0, "error": "API client not initialized"}
    added_count = 0
    updated_count = 0

    for keyword in keywords:
        try:
            # Google Places Text Search API 호출
            response = gmaps_client.places(query=keyword, language='ko')
            results  = response.get('results', [])

            with get_db_session() as session:
                for place in results:
                    # ── 필수 필드 존재 확인 ─────────────────────────────
                    geometry = place.get('geometry', {}).get('location', {})
                    lat = geometry.get('lat')
                    lng = geometry.get('lng')
                    if not lat or not lng:
                        continue

                    # ── sub_category 결정 (types 중 첫 번째 매핑 우선) ──
                    types       = place.get('types', [])
                    sub_cat     = next(
                        (TYPE_TO_SUB[t] for t in types if t in TYPE_TO_SUB),
                        ''
                    )
                    # types에서 대분류 category 결정
                    if any(t in ('restaurant', 'food', 'meal_takeaway', 'bar', 'night_club') for t in types):
                        category = '음식점'
                    elif any(t in ('cafe', 'bakery') for t in types):
                        category = '카페/디저트'
                    elif any(t in ('lodging',) for t in types):
                        category = '숙소'
                    else:
                        category = '명소/관광'

                    # ── 이미지 URL ──────────────────────────────────────
                    photos    = place.get('photos', [])
                    photo_ref = photos[0].get('photo_reference', '') if photos else ''
                    img_url   = (
                        f"https://maps.googleapis.com/maps/api/place/photo"
                        f"?maxwidth=400&photoreference={photo_ref}&key={Config.GMAPS_API_KEY}"
                        if photo_ref else ''
                    )

                    # ★ Place Details API 호출으로 상위 5개 리뷰의 별점 수집
                    # Text Search는 리뷰 데이터 미포함 → place_id로 Details 호출
                    rating_dist = {'rating_5star': 0, 'rating_4star': 0,
                                   'rating_3star': 0, 'rating_2star': 0, 'rating_1star': 0}
                    place_id = place.get('place_id', '')
                    if place_id:
                        try:
                            details = gmaps_client.place(
                                place_id=place_id,
                                fields=['reviews'],
                                language='ko'
                            ).get('result', {})
                            for review in details.get('reviews', []):
                                stars = int(review.get('rating', 0))
                                if stars == 5: rating_dist['rating_5star'] += 1
                                elif stars == 4: rating_dist['rating_4star'] += 1
                                elif stars == 3: rating_dist['rating_3star'] += 1
                                elif stars == 2: rating_dist['rating_2star'] += 1
                                elif stars == 1: rating_dist['rating_1star'] += 1
                        except Exception as detail_err:
                            logger.debug(f"[fetch_google] Details 호출 실패 ({place_id}): {detail_err}")

                    place_data = {
                        'id':           f"google_{place.get('place_id', '')}",
                        'source':       'google',
                        'name':         place.get('name', ''),
                        'city':         city,
                        'category':     category,
                        'sub_category': sub_cat,
                        'lat':          lat,
                        'lng':          lng,
                        'address':      place.get('formatted_address', ''),
                        'rating':       float(place.get('rating', 0.0)),
                        'review_count': int(place.get('user_ratings_total', 0)),
                        # ★ 별점 분포 (Place Details 상위 5개 리뷰 샘플)
                        **rating_dist,
                        'img_url':      img_url,
                        'desc':         ', '.join(types[:3]),
                    }

                    is_new = _upsert_place(session, place_data)
                    if is_new:
                        added_count += 1
                    else:
                        updated_count += 1

        except googlemaps.exceptions.ApiError as e:
            logger.error(f"[fetch_google] API 오류 ({keyword}): {e}")
        except Exception as e:
            logger.error(f"[fetch_google] 예상치 못한 오류 ({keyword}): {e}", exc_info=True)

    logger.info(f"[fetch_google] '{city}' 수집 완료 — 신규: {added_count}, 갱신: {updated_count}")
    return {"added_count": added_count, "updated_count": updated_count, "error": None}


def fetch_kakao(city: str, keywords: list) -> dict:
    """
    Kakao Local API (keyword/category 검색)로 장소 수집 후 DB Upsert.

    수집 필드:
      - place_name, x(lng), y(lat), road_address_name,
        category_group_code(→category), place_url

    Kakao category_group_code → sub_category 매핑:
      FD6(음식점), CE7(카페), CS2(편의점→제외),
      AT4(관광명소), CT1(문화시설), AD5(숙박), OL7(주유소→제외),
      SO1(병원→제외), MT1(마트→제외)

    참고: Kakao는 review_count를 공식 API에서 제공하지 않음.
         후기 수는 0으로 저장하고, Google 수집분에서 보완.

    Returns:
        {"added_count": int, "updated_count": int, "error": str | None}
    """
    if not Config.KAKAO_REST_KEY or Config.KAKAO_REST_KEY == 'YOUR_KAKAO_REST_API_KEY':
        logger.warning("[fetch_kakao] KAKAO_REST_KEY 미설정 — 수집 건너뜀")
        return {"added_count": 0, "updated_count": 0, "error": "API key not set"}

    # Kakao category_group_code → (category, sub_category) 매핑
    CODE_TO_CAT = {
        'FD6': ('음식점',     '음식점'),
        'CE7': ('카페/디저트','커피전문점'),
        'AT4': ('명소/관광',  '랜드마크'),
        'CT1': ('명소/관광',  '미술/박물관'),
        'AD5': ('숙소',       '호텔'),
    }
    SKIP_CODES = {'CS2', 'OL7', 'SO1', 'MT1', 'HP8', 'PM9'}  # 제외 카테고리

    headers     = {"Authorization": f"KakaoAK {Config.KAKAO_REST_KEY}"}
    url         = "https://dapi.kakao.com/v2/local/search/keyword.json"
    added_count = 0
    updated_count = 0

    for keyword in keywords:
        try:
            page = 1
            while page <= 3:  # 최대 3페이지 (페이지당 15개 = 최대 45개/키워드)
                params = {
                    "query": keyword,
                    "size":  15,
                    "page":  page,
                }
                resp = requests.get(url, headers=headers, params=params, timeout=5)

                if resp.status_code != 200:
                    logger.warning(f"[fetch_kakao] HTTP {resp.status_code} ({keyword})")
                    break

                data     = resp.json()
                docs     = data.get('documents', [])
                meta     = data.get('meta', {})

                with get_db_session() as session:
                    for doc in docs:
                        # ── 필수 필드 확인 ──────────────────────────────
                        try:
                            lat = float(doc.get('y', 0))
                            lng = float(doc.get('x', 0))
                        except (ValueError, TypeError):
                            continue
                        if not lat or not lng:
                            continue

                        # ── 카테고리 코드 필터링 ────────────────────────
                        code = doc.get('category_group_code', '')
                        if code in SKIP_CODES:
                            continue

                        cat, sub_cat = CODE_TO_CAT.get(code, ('명소/관광', ''))

                        # category_name에서 세부 카테고리 정제
                        cat_name = doc.get('category_name', '')
                        if '한식' in cat_name:   sub_cat = '한식'
                        elif '일식' in cat_name: sub_cat = '일식'
                        elif '중식' in cat_name: sub_cat = '중식'
                        elif '양식' in cat_name: sub_cat = '양식'
                        elif '분식' in cat_name: sub_cat = '분식'
                        elif '해산물' in cat_name or '횟집' in cat_name: sub_cat = '해산물'
                        elif '고기' in cat_name or '구이' in cat_name:   sub_cat = '고기/구이'
                        elif '베이커리' in cat_name or '빵' in cat_name: sub_cat = '베이커리'
                        elif '호텔' in cat_name:  sub_cat = '호텔'
                        elif '펜션' in cat_name:  sub_cat = '호텔'
                        elif '박물관' in cat_name or '미술관' in cat_name: sub_cat = '미술/박물관'
                        elif '공원' in cat_name:  sub_cat = '자연경관'
                        elif '테마파크' in cat_name or '놀이공원' in cat_name: sub_cat = '테마파크'
                        elif '시장' in cat_name:  sub_cat = '전통시장'

                        place_data = {
                            'id':           f"kakao_{doc.get('id', '')}",
                            'source':       'kakao',
                            'name':         doc.get('place_name', ''),
                            'city':         city,
                            'category':     cat,
                            'sub_category': sub_cat,
                            'lat':          lat,
                            'lng':          lng,
                            'address':      doc.get('road_address_name', '') or doc.get('address_name', ''),
                            'rating':       0.0,         # Kakao는 평점 미제공 → 0
                            # ★ Kakao 공식 API는 review_count 미제공 → 0으로 저장
                            #    Google 수집분에서 동일 장소 데이터로 보완됨
                            'review_count': 0,
                            'img_url':      doc.get('place_url', ''),
                            'desc':         cat_name,
                        }

                        is_new = _upsert_place(session, place_data)
                        if is_new:
                            added_count += 1
                        else:
                            updated_count += 1

                # 마지막 페이지 확인
                if meta.get('is_end', True):
                    break
                page += 1

        except requests.exceptions.Timeout:
            logger.error(f"[fetch_kakao] 타임아웃 ({keyword})")
        except Exception as e:
            logger.error(f"[fetch_kakao] 예상치 못한 오류 ({keyword}): {e}", exc_info=True)

    logger.info(f"[fetch_kakao] '{city}' 수집 완료 — 신규: {added_count}, 갱신: {updated_count}")
    return {"added_count": added_count, "updated_count": updated_count, "error": None}


def fetch_all_data(city: str, keywords: list, is_domestic: bool = True) -> dict:
    """
    Google과 Kakao를 병렬로 실행하여 장소 데이터를 수집.
    국내 여행지는 Kakao를 우선 수집하고, Google로 보완.
    해외 여행지는 Google만 수집.

    Args:
        city:        도시명
        keywords:    검색 키워드 리스트
        is_domestic: True = 국내 (Kakao+Google), False = 해외 (Google만)

    Returns:
        {"added_count": int, "updated_count": int, "sources": list}
    """
    total_added   = 0
    total_updated = 0
    sources_used  = []

    if is_domestic:
        # 국내: Kakao + Google 병렬 수집
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_kakao  = executor.submit(fetch_kakao,  city, keywords)
            future_google = executor.submit(fetch_google, city, keywords, is_domestic)

            kakao_result  = future_kakao.result()
            google_result = future_google.result()

        if not kakao_result.get('error'):
            total_added   += kakao_result.get('added_count',   0)
            total_updated += kakao_result.get('updated_count', 0)
            sources_used.append('kakao')

        if not google_result.get('error'):
            total_added   += google_result.get('added_count',   0)
            total_updated += google_result.get('updated_count', 0)
            sources_used.append('google')
    else:
        # 해외: Google만 수집
        google_result = fetch_google(city, keywords, is_domestic=False)
        if not google_result.get('error'):
            total_added   += google_result.get('added_count',   0)
            total_updated += google_result.get('updated_count', 0)
            sources_used.append('google')

    logger.info(
        f"[fetch_all_data] '{city}' 전체 수집 완료 — "
        f"신규: {total_added}, 갱신: {total_updated}, 소스: {sources_used}"
    )
    return {
        "added_count":   total_added,
        "updated_count": total_updated,
        "sources":       sources_used,
    }

