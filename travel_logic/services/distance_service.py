# services/distance_service.py
"""
거리 계산 및 이동시간 서비스
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

    def __init__(self):
        # [성능 최적화] 인메모리 이동시간 캐시
        # - DB 캐시(PostGIS) 조회 전에 먼저 확인 → DB 왕복 없이 즉시 반환
        # - 4개 테마가 같은 좌표쌍을 반복 조회할 때 특히 효과적
        # - 소수점 4자리 반올림: 약 11m 오차 이내 → 실용상 동일 구간으로 처리
        self._time_cache: dict = {}

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Haversine 공식을 사용한 두 좌표 간 거리 계산 (km)
        
        Args:
            lat1, lon1: 출발지 좌표
            lat2, lon2: 도착지 좌표
            
        Returns:
            거리 (km)
        """
        try:
            lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
        except (ValueError, TypeError):
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
        distance = R * c
        
        return distance
    
    def get_travel_time(self, origin_lat: float, origin_lng: float, 
                       dest_lat: float, dest_lng: float,
                       is_korea: bool, mode: str = 'driving') -> int:
        """
        두 지점 간 이동시간 조회 (초 단위)

        [성능 최적화] 인메모리 캐시를 먼저 확인하여 DB·API 왕복 최소화.
        캐시 키는 소수점 4자리 반올림(약 11m 오차 허용)으로 부동소수점 미스매치 방지.
        
        Args:
            origin_lat, origin_lng: 출발지 좌표
            dest_lat, dest_lng: 목적지 좌표
            is_korea: 국내 여행 여부
            mode: 이동 수단 ('driving' 또는 'transit')
            
        Returns:
            이동시간 (초)
        """
        # 인메모리 캐시 키 (소수점 4자리 반올림으로 부동소수점 오차 제거)
        cache_key = (
            round(origin_lat, 4), round(origin_lng, 4),
            round(dest_lat, 4),   round(dest_lng, 4),
            mode,
        )
        if cache_key in self._time_cache:
            return self._time_cache[cache_key]

        if is_korea:
            result = backend.get_real_duration_kakao(
                origin_lat, origin_lng, dest_lat, dest_lng, mode=mode
            )
        else:
            results = backend.get_real_duration_google_bulk(
                origin_lat, origin_lng, 
                [{'lat': dest_lat, 'lng': dest_lng}], 
                mode=mode
            )
            result = results[0][0] if results else 999999

        # 인메모리 캐시 저장 (999999 오류값은 캐싱 제외 — 재시도 허용)
        if result != 999999:
            self._time_cache[cache_key] = result

        return result
    
    @staticmethod
    def get_travel_times_bulk(origin_lat: float, origin_lng: float,
                              destinations: list, is_korea: bool, 
                              mode: str = 'driving') -> list:
        """
        한 출발지에서 여러 목적지까지의 이동시간을 일괄 조회
        
        Args:
            origin_lat, origin_lng: 출발지 좌표
            destinations: 목적지 리스트 (각 항목은 {'lat': float, 'lng': float} 형태)
            is_korea: 국내 여행 여부
            mode: 이동 수단
            
        Returns:
            [(이동시간, 목적지), ...] 리스트
        """
        if is_korea:
            # Kakao API는 개별 호출 필요
            import concurrent.futures
            results = []
            
            def get_time(dest):
                return backend.get_real_duration_kakao(
                    origin_lat, origin_lng, dest['lat'], dest['lng'], mode=mode
                )
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_map = {executor.submit(get_time, d): d for d in destinations}
                for future in concurrent.futures.as_completed(future_map):
                    dest = future_map[future]
                    try:
                        results.append((future.result(), dest))
                    except Exception:
                        results.append((999999, dest))
            
            return results
        else:
            # Google API는 일괄 조회 가능
            return backend.get_real_duration_google_bulk(
                origin_lat, origin_lng, destinations, mode=mode
            )
