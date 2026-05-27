"""
scripts/collect_overseas.py — 해외 여행지 데이터 수집 → Supabase 저장

사용법:
    # Overture Maps (무료, 대용량) — DuckDB 필요: pip install duckdb
    python -X utf8 scripts/collect_overseas.py --source overture --city 도쿄
    python -X utf8 scripts/collect_overseas.py --source overture --city 오사카 --limit 5000

    # OSM Overpass API (무료, 즉시)
    python -X utf8 scripts/collect_overseas.py --source osm --city 파리

    # Google Places API (유료, 품질 최고) — GMAPS_API_KEY 필요
    python -X utf8 scripts/collect_overseas.py --source google --city 뉴욕

    # 여러 도시 한 번에
    python -X utf8 scripts/collect_overseas.py --source osm --city 도쿄 오사카 파리 뉴욕

지원 도시:
    [해외] 도쿄, 오사카, 교토, 후쿠오카, 삿포로, 방콕, 싱가포르, 발리, 세부, 다낭,
           파리, 런던, 바르셀로나, 로마, 암스테르담, 뉴욕, 하와이, 라스베가스,
           홍콩, 타이페이, 베이징, 상하이, 쿠알라룸푸르, 하노이, 호치민, 마닐라,
           두바이, 시드니, 취리히, 이스탄불, LA, 샌프란시스코, 밴쿠버
    [국내] 서울, 부산, 제주, 인천, 대구, 대전, 광주, 울산, 수원, 강릉,
           경주, 전주, 여수, 속초, 춘천, 가평, 양평, 포항, 거제, 남해,
           통영, 군산, 목포, 순천, 안동, 청주, 충주, 천안, 세종
    (CITY_CONFIG에 bbox 추가하면 무제한 확장)

DB 삽입 방식:
    - 기존 db/connection.py + db/models.py 그대로 사용
    - Supabase = PostgreSQL → SQLAlchemy 직접 연결, 별도 API 불필요
    - ON CONFLICT (id) DO NOTHING → 중복 삽입 무시, 재실행 안전
"""

import sys
import os
import io
import time
import hashlib
import argparse
import math
from typing import List, Dict, Any, Optional, Tuple

# Windows 터미널 한글 깨짐 방지
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
elif hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from db.connection import get_db_session


# ──────────────────────────────────────────────────────────────
#  도시 설정 (bbox: south, west, north, east)
# ──────────────────────────────────────────────────────────────
CITY_CONFIG: Dict[str, Dict[str, Any]] = {
    # 일본
    "도쿄":    {"bbox": (35.52, 139.45, 35.82, 139.92), "country": "JP", "en": "Tokyo"},
    "오사카":  {"bbox": (34.55, 135.37, 34.78, 135.65), "country": "JP", "en": "Osaka"},
    "교토":    {"bbox": (34.93, 135.63, 35.10, 135.82), "country": "JP", "en": "Kyoto"},
    "후쿠오카":{"bbox": (33.52, 130.32, 33.72, 130.55), "country": "JP", "en": "Fukuoka"},
    "삿포로":  {"bbox": (42.98, 141.22, 43.22, 141.52), "country": "JP", "en": "Sapporo"},
    # 동남아
    "방콕":    {"bbox": (13.60, 100.33, 13.95, 100.70), "country": "TH", "en": "Bangkok"},
    "싱가포르":{"bbox": (1.22,  103.62, 1.47,  104.00), "country": "SG", "en": "Singapore"},
    "발리":    {"bbox": (-8.85, 114.97, -8.10, 115.50), "country": "ID", "en": "Bali"},
    "세부":    {"bbox": (10.22, 123.79, 10.48, 124.05), "country": "PH", "en": "Cebu"},
    "다낭":    {"bbox": (15.95, 108.14, 16.15, 108.30), "country": "VN", "en": "Da Nang"},
    # 유럽
    "파리":    {"bbox": (48.82, 2.25,   48.91, 2.42),   "country": "FR", "en": "Paris"},
    "런던":    {"bbox": (51.45, -0.25,  51.57, 0.00),   "country": "GB", "en": "London"},
    "바르셀로나":{"bbox":(41.32, 2.05,  41.47, 2.25),   "country": "ES", "en": "Barcelona"},
    "로마":    {"bbox": (41.82, 12.42,  41.96, 12.58),  "country": "IT", "en": "Rome"},
    "암스테르담":{"bbox":(52.33, 4.84,  52.43, 4.97),   "country": "NL", "en": "Amsterdam"},
    # 미주
    "뉴욕":    {"bbox": (40.58, -74.10, 40.85, -73.72), "country": "US", "en": "New York"},
    "하와이":  {"bbox": (21.24, -158.15, 21.55, -157.65), "country": "US", "en": "Honolulu"},
    "라스베가스":{"bbox":(36.07, -115.30, 36.30, -115.07), "country": "US", "en": "Las Vegas"},
    # ── Phase 2: 해외 추가 도시 ────────────────────────────────
    # 중화권
    "홍콩":       {"bbox": (22.19, 113.84, 22.57, 114.33), "country": "HK", "en": "HongKong"},
    "타이페이":   {"bbox": (24.97, 121.45, 25.21, 121.68), "country": "TW", "en": "Taipei"},
    "베이징":     {"bbox": (39.75, 116.18, 40.04, 116.58), "country": "CN", "en": "Beijing"},
    "상하이":     {"bbox": (31.00, 121.25, 31.40, 121.65), "country": "CN", "en": "Shanghai"},
    # 동남아 추가
    "쿠알라룸푸르":{"bbox":(3.07,  101.60,  3.24, 101.78), "country": "MY", "en": "KualaLumpur"},
    "하노이":     {"bbox": (20.93, 105.73, 21.10, 105.91), "country": "VN", "en": "Hanoi"},
    "호치민":     {"bbox": (10.67, 106.58, 10.87, 106.80), "country": "VN", "en": "HoChiMinh"},
    "마닐라":     {"bbox": (14.50, 120.95, 14.70, 121.10), "country": "PH", "en": "Manila"},
    # 중동·오세아니아
    "두바이":     {"bbox": (24.79,  54.89, 25.36,  55.57), "country": "AE", "en": "Dubai"},
    "시드니":     {"bbox": (-34.17, 150.52,-33.43, 151.34), "country": "AU", "en": "Sydney"},
    # 유럽 추가
    "취리히":     {"bbox": (47.31,   8.44, 47.43,   8.63), "country": "CH", "en": "Zurich"},
    "이스탄불":   {"bbox": (40.85,  28.57, 41.20,  29.23), "country": "TR", "en": "Istanbul"},
    # 북미 추가
    "LA":         {"bbox": (33.70,-118.67, 34.34,-117.90), "country": "US", "en": "LosAngeles"},
    "샌프란시스코":{"bbox":(37.67,-122.52, 37.83,-122.33), "country": "US", "en": "SanFrancisco"},
    "밴쿠버":     {"bbox": (49.18,-123.27, 49.32,-123.02), "country": "CA", "en": "Vancouver"},
    # ── 국내 도시 (OSM으로 수집 가능) ────────────────────────────
    "서울":   {"bbox": (37.42, 126.76, 37.70, 127.18), "country": "KR", "en": "Seoul"},
    "부산":   {"bbox": (35.05, 128.95, 35.22, 129.13), "country": "KR", "en": "Busan"},
    "제주":   {"bbox": (33.25, 126.15, 33.57, 126.94), "country": "KR", "en": "Jeju"},
    "인천":   {"bbox": (37.37, 126.56, 37.60, 126.78), "country": "KR", "en": "Incheon"},
    "대구":   {"bbox": (35.78, 128.48, 35.93, 128.70), "country": "KR", "en": "Daegu"},
    "대전":   {"bbox": (36.27, 127.33, 36.43, 127.49), "country": "KR", "en": "Daejeon"},
    "광주":   {"bbox": (35.08, 126.84, 35.21, 127.00), "country": "KR", "en": "Gwangju"},
    "울산":   {"bbox": (35.47, 129.16, 35.61, 129.39), "country": "KR", "en": "Ulsan"},
    "수원":   {"bbox": (37.22, 126.97, 37.34, 127.08), "country": "KR", "en": "Suwon"},
    "강릉":   {"bbox": (37.71, 128.84, 37.82, 128.98), "country": "KR", "en": "Gangneung"},
    "경주":   {"bbox": (35.77, 129.18, 35.88, 129.32), "country": "KR", "en": "Gyeongju"},
    "전주":   {"bbox": (35.77, 127.08, 35.87, 127.18), "country": "KR", "en": "Jeonju"},
    "여수":   {"bbox": (34.68, 127.63, 34.79, 127.79), "country": "KR", "en": "Yeosu"},
    "속초":   {"bbox": (38.17, 128.53, 38.24, 128.62), "country": "KR", "en": "Sokcho"},
    "춘천":   {"bbox": (37.84, 127.68, 37.95, 127.79), "country": "KR", "en": "Chuncheon"},
    "가평":   {"bbox": (37.80, 127.49, 37.90, 127.59), "country": "KR", "en": "Gapyeong"},
    "양평":   {"bbox": (37.47, 127.47, 37.55, 127.59), "country": "KR", "en": "Yangpyeong"},
    "포항":   {"bbox": (35.97, 129.31, 36.08, 129.44), "country": "KR", "en": "Pohang"},
    "거제":   {"bbox": (34.82, 128.56, 34.93, 128.72), "country": "KR", "en": "Geoje"},
    "남해":   {"bbox": (34.77, 127.85, 34.90, 127.99), "country": "KR", "en": "Namhae"},
    "통영":   {"bbox": (34.82, 128.38, 34.89, 128.48), "country": "KR", "en": "Tongyeong"},
    "군산":   {"bbox": (35.94, 126.68, 36.01, 126.78), "country": "KR", "en": "Gunsan"},
    "목포":   {"bbox": (34.78, 126.36, 34.83, 126.44), "country": "KR", "en": "Mokpo"},
    "순천":   {"bbox": (34.93, 127.47, 35.01, 127.56), "country": "KR", "en": "Suncheon"},
    "안동":   {"bbox": (36.54, 128.68, 36.62, 128.78), "country": "KR", "en": "Andong"},
    "청주":   {"bbox": (36.59, 127.43, 36.68, 127.54), "country": "KR", "en": "Cheongju"},
    "충주":   {"bbox": (36.95, 127.88, 37.04, 127.99), "country": "KR", "en": "Chungju"},
    "천안":   {"bbox": (36.78, 127.12, 36.86, 127.22), "country": "KR", "en": "Cheonan"},
    "세종":   {"bbox": (36.44, 127.23, 36.54, 127.33), "country": "KR", "en": "Sejong"},
}


# ──────────────────────────────────────────────────────────────
#  카테고리 매핑 (외부 소스 → 프로젝트 내부 카테고리)
# ──────────────────────────────────────────────────────────────
OVERTURE_CATEGORY_MAP = {
    # 음식점
    "restaurant": "음식점", "food": "음식점", "eat_and_drink": "음식점",
    "fast_food": "음식점", "cafe": "카페", "coffee_shop": "카페",
    "bakery": "카페", "bar": "바/주점", "pub": "바/주점",
    # 숙소
    "hotel": "호텔", "accommodation": "숙소", "hostel": "게스트하우스",
    "motel": "모텔", "resort": "리조트", "lodging": "숙소",
    # 관광
    "tourist_attraction": "관광", "attraction": "관광",
    "museum": "관광", "park": "관광", "beach": "관광",
    "landmark": "관광", "monument": "관광", "temple": "관광",
    "shopping": "쇼핑", "mall": "쇼핑", "market": "쇼핑",
}

OSM_CATEGORY_MAP = {
    # amenity 태그
    "restaurant": "음식점", "fast_food": "음식점", "food_court": "음식점",
    "cafe": "카페", "bakery": "카페", "coffee_shop": "카페",
    "bar": "바/주점", "pub": "바/주점", "nightclub": "바/주점",
    "hotel": "호텔", "hostel": "게스트하우스", "motel": "모텔",
    "guest_house": "게스트하우스",
    # tourism 태그
    "attraction": "관광", "museum": "관광", "artwork": "관광",
    "viewpoint": "관광", "zoo": "관광", "theme_park": "관광",
    "gallery": "관광", "aquarium": "관광",
    # leisure 태그
    "park": "관광", "beach_resort": "관광", "nature_reserve": "관광",
    # shop 태그
    "mall": "쇼핑", "supermarket": "쇼핑", "department_store": "쇼핑",
    "market": "쇼핑",
}

GOOGLE_CATEGORY_MAP = {
    "restaurant": "음식점", "food": "음식점", "meal_delivery": "음식점",
    "cafe": "카페", "bakery": "카페",
    "bar": "바/주점", "night_club": "바/주점",
    "lodging": "호텔", "campground": "숙소",
    "tourist_attraction": "관광", "museum": "관광", "park": "관광",
    "zoo": "관광", "amusement_park": "관광", "aquarium": "관광",
    "art_gallery": "관광", "church": "관광", "hindu_temple": "관광",
    "mosque": "관광", "natural_feature": "관광",
    "shopping_mall": "쇼핑", "store": "쇼핑", "clothing_store": "쇼핑",
}

# 수집 대상 카테고리 (관광·식사·카페·숙소만, 불필요한 카테고리 제외)
COLLECT_CATEGORIES = {
    "음식점", "카페", "관광", "호텔", "숙소", "리조트",
    "게스트하우스", "모텔", "쇼핑", "바/주점",
}


# ──────────────────────────────────────────────────────────────
#  공통 유틸리티
# ──────────────────────────────────────────────────────────────

def make_place_id(source: str, raw_id: str) -> str:
    """소스 + 원본 ID → 프로젝트 내부 ID 생성 (중복 방지)"""
    return f"{source}_{raw_id[:80]}"


def make_place_id_from_coords(source: str, name: str, lat: float, lng: float) -> str:
    """이름 + 좌표 해시로 ID 생성 (원본 ID 없는 소스용)"""
    raw = f"{name}{lat:.5f}{lng:.5f}"
    h = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"{source}_{h}"


def wkt_point(lng: float, lat: float) -> str:
    """PostGIS WKT POINT 문자열 생성"""
    return f"SRID=4326;POINT({lng} {lat})"


def bulk_upsert(rows: List[Dict[str, Any]], dry_run: bool = False) -> int:
    """
    places 테이블에 bulk upsert.
    ON CONFLICT (id) DO NOTHING → 이미 있는 장소는 건너뜀 (재실행 안전).

    Args:
        rows: 삽입할 Place 딕셔너리 리스트
        dry_run: True면 DB 삽입 없이 카운트만 반환

    Returns:
        실제로 삽입된 행 수
    """
    if not rows:
        return 0
    if dry_run:
        print(f"  [DRY-RUN] {len(rows)}개 삽입 예정 (실제 삽입 안 함)")
        return 0

    sql = text("""
        INSERT INTO places (
            id, source, name, city, category, sub_category,
            location, address, rating, review_count, img_url, description
        ) VALUES (
            :id, :source, :name, :city, :category, :sub_category,
            ST_GeogFromText(:location), :address, :rating, :review_count,
            :img_url, :description
        )
        ON CONFLICT (id) DO NOTHING
    """)

    inserted = 0
    with get_db_session() as session:
        for i in range(0, len(rows), 500):  # 500건씩 배치
            batch = rows[i:i + 500]
            result = session.execute(sql, batch)
            inserted += result.rowcount

    return inserted


# ──────────────────────────────────────────────────────────────
#  소스 1: Overture Maps (DuckDB + S3)
# ──────────────────────────────────────────────────────────────

OVERTURE_RELEASE = "2024-12-18.0"  # 최신 릴리스로 교체 가능 (https://docs.overturemaps.org/release/)

def collect_overture(city: str, limit: int = 3000) -> List[Dict[str, Any]]:
    """
    Overture Maps S3에서 DuckDB로 직접 쿼리 → 장소 목록 반환.

    필요: pip install duckdb
    비용: 완전 무료 (AWS S3 공개 버킷, 서명 불필요)
    """
    try:
        import duckdb
    except ImportError:
        print("  [오류] duckdb가 없습니다: pip install duckdb")
        return []

    cfg = CITY_CONFIG.get(city)
    if not cfg:
        print(f"  [오류] '{city}'는 CITY_CONFIG에 없습니다.")
        return []

    s, w, n, e = cfg["bbox"]
    city_en = cfg["en"]

    print(f"  Overture S3 쿼리 중... ({city} bbox: {s},{w} ~ {n},{e})")

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET s3_region='us-west-2';")

    query = f"""
    SELECT
        id,
        names.primary                        AS name,
        categories.primary                   AS category_raw,
        geometry.x                           AS lng,
        geometry.y                           AS lat,
        COALESCE(websites[1], '')            AS website,
        COALESCE(phones[1], '')              AS phone
    FROM read_parquet(
        's3://overturemaps-us-west-2/release/{OVERTURE_RELEASE}/theme=places/type=place/*',
        hive_partitioning=1
    )
    WHERE bbox.minx >= {w} AND bbox.maxx <= {e}
      AND bbox.miny >= {s} AND bbox.maxy <= {n}
      AND names.primary IS NOT NULL
    LIMIT {limit}
    """

    try:
        rows_raw = con.execute(query).fetchall()
    except Exception as e_q:
        print(f"  [오류] Overture 쿼리 실패: {e_q}")
        print("  TIP: 릴리스 날짜가 변경되었을 수 있습니다 → OVERTURE_RELEASE 상수 수정")
        return []

    rows: List[Dict[str, Any]] = []
    skipped = 0
    for raw_id, name, cat_raw, lng, lat, website, phone in rows_raw:
        if not name or not lat or not lng:
            skipped += 1
            continue

        category = OVERTURE_CATEGORY_MAP.get(str(cat_raw or "").lower(), "")
        if category not in COLLECT_CATEGORIES:
            skipped += 1
            continue

        rows.append({
            "id":           make_place_id("overture", str(raw_id)),
            "source":       "overture",
            "name":         str(name)[:200],
            "city":         city,
            "category":     category,
            "sub_category": str(cat_raw or "")[:100],
            "location":     wkt_point(float(lng), float(lat)),
            "address":      "",
            "rating":       0.0,
            "review_count": 0,
            "img_url":      str(website)[:500] if website else "",
            "description":  "",
        })

    print(f"  수집: {len(rows)}개 / 스킵(좌표없음·카테고리무관): {skipped}개")
    return rows


# ──────────────────────────────────────────────────────────────
#  소스 2: OpenStreetMap Overpass API
# ──────────────────────────────────────────────────────────────

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_ALT = "https://overpass.kumi.systems/api/interpreter"  # 백업 서버

def collect_osm(city: str, limit: int = 2000) -> List[Dict[str, Any]]:
    """
    OSM Overpass API로 도시 내 POI 수집.

    비용: 완전 무료
    rate limit: 요청 간 2~3초 sleep 필요 (서버 과부하 방지)
    """
    try:
        import requests
    except ImportError:
        print("  [오류] requests가 없습니다: pip install requests")
        return []

    cfg = CITY_CONFIG.get(city)
    if not cfg:
        print(f"  [오류] '{city}'는 CITY_CONFIG에 없습니다.")
        return []

    s, w, n, e = cfg["bbox"]

    # Overpass QL 쿼리 — 음식점·카페·숙소·관광지·쇼핑몰 수집
    query = f"""
    [out:json][timeout:90];
    (
      node["amenity"~"restaurant|fast_food|food_court|cafe|bar|pub|nightclub|hotel|hostel|motel|guest_house"]({s},{w},{n},{e});
      node["tourism"~"attraction|museum|artwork|viewpoint|zoo|theme_park|gallery|aquarium"]({s},{w},{n},{e});
      node["leisure"~"park|beach_resort|nature_reserve"]({s},{w},{n},{e});
      node["shop"~"mall|department_store|supermarket"]({s},{w},{n},{e});
    );
    out body {limit};
    """

    print(f"  OSM Overpass 쿼리 중... ({city})")
    for attempt, url in enumerate([OVERPASS_URL, OVERPASS_ALT]):
        try:
            resp = requests.post(url, data={"data": query}, timeout=120)
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
            break
        except Exception as e_req:
            print(f"  [경고] {url} 실패: {e_req}")
            if attempt == 1:
                print("  [오류] OSM 서버 모두 응답 없음")
                return []
            time.sleep(3)

    rows: List[Dict[str, Any]] = []
    skipped = 0
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("name:ko") or tags.get("name:en")
        lat  = el.get("lat")
        lng  = el.get("lon")

        if not name or not lat or not lng:
            skipped += 1
            continue

        # 카테고리 결정 (amenity > tourism > leisure > shop 순)
        cat_raw = (
            tags.get("amenity") or tags.get("tourism")
            or tags.get("leisure") or tags.get("shop") or ""
        )
        category = OSM_CATEGORY_MAP.get(cat_raw, "")
        if not category:
            skipped += 1
            continue

        # 별점은 OSM에 없음 — 0으로 저장 (나중에 Google enrichment 가능)
        rows.append({
            "id":           make_place_id("osm", str(el.get("id", ""))),
            "source":       "osm",
            "name":         str(name)[:200],
            "city":         city,
            "category":     category,
            "sub_category": cat_raw[:100],
            "location":     wkt_point(float(lng), float(lat)),
            "address":      tags.get("addr:full") or tags.get("addr:street") or "",
            "rating":       float(tags.get("stars", 0) or 0),
            "review_count": 0,
            "img_url":      tags.get("website") or tags.get("url") or "",
            "description":  tags.get("description") or "",
        })

    print(f"  수집: {len(rows)}개 / 스킵(이름없음·카테고리무관): {skipped}개")
    return rows


# ──────────────────────────────────────────────────────────────
#  소스 3: Google Places API (New — 유료, 품질 최고)
# ──────────────────────────────────────────────────────────────

GOOGLE_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"

# 수집할 타입 목록 (Google Place Types)
GOOGLE_PLACE_TYPES = [
    "tourist_attraction", "museum", "park", "art_gallery",
    "restaurant", "cafe", "bakery",
    "lodging",
    "shopping_mall", "night_club",
]

def collect_google(city: str, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Google Places API (New) Nearby Search로 도시 내 POI 수집.

    비용: 월 $200 크레딧 → 약 6,250건 무료 (초과 시 $0.032/건)
    필요: .env에 GMAPS_API_KEY 설정
    """
    try:
        import requests
    except ImportError:
        print("  [오류] requests가 없습니다: pip install requests")
        return []

    api_key = os.getenv("GMAPS_API_KEY")
    if not api_key:
        print("  [오류] GMAPS_API_KEY 환경변수가 없습니다.")
        return []

    cfg = CITY_CONFIG.get(city)
    if not cfg:
        print(f"  [오류] '{city}'는 CITY_CONFIG에 없습니다.")
        return []

    s, w, n, e = cfg["bbox"]
    # bbox 중심 + 반경 계산
    center_lat = (s + n) / 2
    center_lng = (w + e) / 2
    radius_m   = int(_haversine_km(s, w, n, e) * 500)  # bbox 대각선 절반 (m)
    radius_m   = min(radius_m, 50_000)                  # Google 최대 50km

    rows: List[Dict[str, Any]] = []
    seen_ids: set = set()
    per_type_limit = max(20, limit // len(GOOGLE_PLACE_TYPES))

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.primaryType,"
            "places.location,places.formattedAddress,"
            "places.rating,places.userRatingCount,"
            "places.photos,places.websiteUri,places.editorialSummary"
        ),
    }

    print(f"  Google Places API 수집 중... ({city}, {len(GOOGLE_PLACE_TYPES)}개 타입)")

    for place_type in GOOGLE_PLACE_TYPES:
        if len(rows) >= limit:
            break

        payload = {
            "includedTypes": [place_type],
            "maxResultCount": min(per_type_limit, 20),  # Google 최대 20/요청
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": center_lat, "longitude": center_lng},
                    "radius": float(radius_m),
                }
            },
            "languageCode": "ko",
        }

        try:
            resp = requests.post(GOOGLE_NEARBY_URL, json=payload, headers=headers, timeout=30)
            if resp.status_code == 429:
                print(f"    Rate limit 도달, 10초 대기...")
                time.sleep(10)
                resp = requests.post(GOOGLE_NEARBY_URL, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            places_data = resp.json().get("places", [])
        except Exception as e_g:
            print(f"    [{place_type}] 오류: {e_g}")
            time.sleep(2)
            continue

        for p in places_data:
            raw_id = p.get("id", "")
            if raw_id in seen_ids:
                continue
            seen_ids.add(raw_id)

            loc  = p.get("location", {})
            lat  = loc.get("latitude")
            lng  = loc.get("longitude")
            if not lat or not lng:
                continue

            name = p.get("displayName", {}).get("text") or ""
            if not name:
                continue

            cat_raw  = p.get("primaryType", "")
            category = GOOGLE_CATEGORY_MAP.get(cat_raw, "관광")

            # 사진 URL (첫 번째 사진만)
            photos   = p.get("photos", [])
            img_url  = ""
            if photos:
                photo_name = photos[0].get("name", "")
                if photo_name:
                    img_url = (
                        f"https://places.googleapis.com/v1/{photo_name}/media"
                        f"?maxWidthPx=800&key={api_key}"
                    )

            rows.append({
                "id":           make_place_id("google", raw_id),
                "source":       "google",
                "name":         str(name)[:200],
                "city":         city,
                "category":     category,
                "sub_category": cat_raw[:100],
                "location":     wkt_point(float(lng), float(lat)),
                "address":      p.get("formattedAddress") or "",
                "rating":       float(p.get("rating") or 0),
                "review_count": int(p.get("userRatingCount") or 0),
                "img_url":      img_url[:500],
                "description":  (p.get("editorialSummary") or {}).get("text") or "",
            })

        print(f"    [{place_type}] {len(places_data)}개 → 누적 {len(rows)}개")
        time.sleep(1)  # rate limit 예방

    print(f"  수집 완료: {len(rows)}개")
    return rows


# ──────────────────────────────────────────────────────────────
#  내부 유틸
# ──────────────────────────────────────────────────────────────

def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1-a))


# ──────────────────────────────────────────────────────────────
#  메인
# ──────────────────────────────────────────────────────────────

SOURCE_FUNCS = {
    "overture": collect_overture,
    "osm":      collect_osm,
    "google":   collect_google,
}

def main():
    parser = argparse.ArgumentParser(
        description="해외 여행지 데이터 수집 → Supabase 저장",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source", choices=["overture", "osm", "google"], default="osm",
        help="데이터 소스 (기본: osm)",
    )
    parser.add_argument(
        "--city", nargs="+", required=True,
        help="수집할 도시명 (예: 도쿄 오사카 파리)",
    )
    parser.add_argument(
        "--limit", type=int, default=2000,
        help="도시당 최대 수집 수 (기본: 2000)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="DB 삽입 없이 수집 결과만 확인",
    )
    parser.add_argument(
        "--list-cities", action="store_true",
        help="지원 도시 목록 출력",
    )
    args = parser.parse_args()

    if args.list_cities:
        print("\n지원 도시 목록:")
        for k, v in CITY_CONFIG.items():
            print(f"  {k:<12} ({v['en']}, {v['country']})")
        print()
        return

    collect_fn = SOURCE_FUNCS[args.source]
    total_inserted = 0

    for city in args.city:
        print(f"\n{'='*55}")
        print(f"  [{args.source.upper()}] {city} 수집 시작 (최대 {args.limit:,}개)")
        print(f"{'='*55}")

        rows = collect_fn(city, limit=args.limit)
        if not rows:
            print(f"  수집된 데이터 없음 — 스킵")
            continue

        if args.dry_run:
            # dry-run: 샘플 출력
            print(f"\n  [DRY-RUN] 샘플 (상위 5개):")
            for r in rows[:5]:
                print(f"    {r['name']:<25} {r['category']:<10} {r['location'][:40]}")
            print(f"  → 총 {len(rows)}개 삽입 예정 (DB 삽입 안 함)\n")
        else:
            print(f"  DB 삽입 중... ({len(rows):,}개)")
            inserted = bulk_upsert(rows, dry_run=False)
            total_inserted += inserted
            skipped = len(rows) - inserted
            print(f"  완료: 신규 삽입 {inserted:,}개 / 중복 스킵 {skipped:,}개")

        # 도시 간 과도한 요청 방지
        if len(args.city) > 1:
            time.sleep(2)

    if not args.dry_run and len(args.city) > 1:
        print(f"\n{'='*55}")
        print(f"  전체 신규 삽입: {total_inserted:,}개")
        print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
