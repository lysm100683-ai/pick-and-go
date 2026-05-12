# services/distance_service.py
"""
거리 계산 및 이동시간 서비스

[최적화 방침]
- 일정 생성 중 외부 API를 수백 번 호출하면 2분+ 소요 문제 발생.
- 후보 선택(bulk) 단계에서는 Haversine 직선거리 추정으로 즉시 처리.
- 최종 표시용(single) 단계에서는 캐시 우선 → 미스 시 Haversine.
- 결과: 외부 API 호출 수백 번 → 거의 0회, 생성 시간 수초 내로 단축.
"""

import math
import sys
import os

# backend 모듈 import를 위한 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import backend_postgres as backend  # DB부: backend_postgres 사용 (PostGIS 기반)


class DistanceService:
    """거리 계산 및 이동시간 조회 담당"""
    
    # 도로계수: 직선거리 × 이 값 = 실제 이동거리 근사치
    # (도심 1.3, 산간/지방 1.5 — 보수적으로 1.3 사용)
    ROAD_FACTOR = 1.3

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Haversine 공식을 사용한 두 좌표 간 직선거리 계산 (km)
        
        Args:
            lat1, lon1: 출발지 좌표
            lat2, lon2: 도착지 좌표
            
        Returns:
            거리 (km). 좌표가 유효하지 않으면 99999 반환.
        """
        try:
            lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
        except Exception:
            return 99999
        
        # 0.0 좌표는 유효하지 않다고 간주
        if lat1 == 0.0 or lon1 == 0.0 or lat2 == 0.0 or lon2 == 0.0:
            return 99999
        
        R = 6371  # 지구 반지름 (km)
        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)
        
        a = math.sin(dLat/2) * math.sin(dLat/2) + math.cos(math.radians(lat1)) \
            * math.cos(math.radians(lat2)) * math.sin(dLon/2) * math.sin(dLon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c

    @staticmethod
    def _haversine_seconds(lat1: float, lng1: float, lat2: float, lng2: float,
                           mode: str = 'driving') -> int:
        """
        직선거리 기반 이동시간 추정 (초 단위, 외부 API 호출 없음)
        
        - driving: 평균 30 km/h (도심 교통 감안)
        - transit/walking: 평균 4 km/h
        - 최소값: 5분(300초)
        """
        dist_km = DistanceService.haversine_distance(lat1, lng1, lat2, lng2)
        if dist_km >= 99999:
            return 999999
        speed_kmh = 30 if mode == 'driving' else 4
        return max(300, int(dist_km * DistanceService.ROAD_FACTOR / speed_kmh * 3600))

    @staticmethod
    def get_travel_time(origin_lat: float, origin_lng: float,
                        dest_lat: float, dest_lng: float,
                        is_korea: bool, mode: str = 'driving') -> int:
        """
        두 지점 간 이동시간 조회 (초 단위)

        [전략]
        1. DB 캐시에 저장된 실제 측정값이 있으면 즉시 반환 (API 호출 없음).
        2. 캐시 미스 시 Haversine 직선거리로 추정값 반환 (API 호출 없음).
           → 일정 생성 속도를 수초 내로 유지하기 위한 결정.

        Args:
            origin_lat, origin_lng: 출발지 좌표
            dest_lat, dest_lng: 도착지 좌표
            is_korea: 국내 여행 여부 (현재는 동일 로직, 향후 분기 가능)
            mode: 이동 수단 ('driving' 또는 'transit')

        Returns:
            이동시간 (초)
        """
        # 1단계: DB 캐시 확인
        try:
            cached = backend.get_movement_cache(origin_lat, origin_lng, dest_lat, dest_lng, mode)
            if cached is not None:
                return cached
        except Exception:
            pass

        # 2단계: 캐시 미스 → Haversine 추정 (즉시, 외부 API 호출 없음)
        return DistanceService._haversine_seconds(origin_lat, origin_lng, dest_lat, dest_lng, mode)

    @staticmethod
    def get_travel_times_bulk(origin_lat: float, origin_lng: float,
                              destinations: list, is_korea: bool,
                              mode: str = 'driving') -> list:
        """
        한 출발지에서 여러 후보 목적지까지의 이동시간을 일괄 추정.

        [전략] 후보 선택(최적화) 단계용 함수이므로 정확도보다 속도가 중요.
        → 외부 API 호출 없이 Haversine 직선거리로 즉시 추정.
        → API를 수백 번 호출하던 구조를 완전히 제거하여 생성 시간 단축.

        Args:
            origin_lat, origin_lng: 출발지 좌표
            destinations: 목적지 리스트 (각 항목: {'lat': float, 'lng': float, ...})
            is_korea: 국내 여행 여부 (현재 로직 동일, 향후 분기 가능)
            mode: 이동 수단

        Returns:
            [(이동시간_초, 목적지_dict), ...] 리스트 (원래 순서 유지)
        """
        results = []
        for dest in destinations:
            est = DistanceService._haversine_seconds(
                origin_lat, origin_lng, dest.get('lat', 0.0), dest.get('lng', 0.0), mode
            )
            results.append((est, dest))
        return results

