# travel_logic/services/hotel_anchor_service.py
"""
Phase 4: 숙소 앵커링 (숙소 위치 확정)

역할: Phase 3의 임시 경로 결과(일별 이동시간 + 마지막 방문 장소)를 분석하여
     이동 부하가 집중된 날의 숙소를 해당 날 방문 지역 중심으로 이동시킨다.

두 가지 상황:
  상황 A: 특정 날에 90분(HOTEL_ANCHOR_TIME_THRESHOLD) 초과 이동 구간 발견
           → 해당 날의 클러스터 중심(centroid) 근처 숙소로 교체
  상황 B: 모든 날 이동시간이 비슷 (초과 없음)
           → 여행 중간 날짜 마지막 방문 장소 근처 숙소로 교체

숙소 탐색 우선순위:
  1. hotel_candidates 풀 중 사용자 star_rating 조건 충족 + 목표 좌표와 Haversine 최소
  2. 1번이 비어있으면 base_hotel 유지 (최최종 폴백)

설계 원칙:
  - num_hotels == 1: 숙소 고정, 앵커링 로직 실행하지 않음
  - num_hotels == 2: 최대 1회 숙소 교체 (여행 절반 지점 or 가장 혼잡한 날 1곳)
  - num_hotels == N: 최대 N-1회 교체, 여행을 N구간으로 분할하여 구간별 최적 숙소
  - max_changes = num_hotels - 1 (교체 횟수 상한)
  - night_hotels: [1박 숙소, 2박 숙소, ..., (num_days-1)박 숙소]
    마지막 날(귀국/귀가)은 숙소 없음 → 리스트 길이 = num_days - 1

[출력 구조 예시] 3박 4일 여행:
  night_hotels[0] = 1일차 → 2일차 사이 숙소 (1박)
  night_hotels[1] = 2일차 → 3일차 사이 숙소 (2박)
  night_hotels[2] = 3일차 → 4일차 사이 숙소 (3박)
"""

import math
from typing import List, Dict, Any, Optional, Tuple

from ..config.constants import HOTEL_ANCHOR_TIME_THRESHOLD


class HotelAnchorService:
    """
    Phase 4: 이동시간 분석 기반 숙소 위치 최적화 서비스.

    plan.md 요구사항:
      num_hotels == 1  → base_hotel 고정 반환 (앵커링 없음)
      num_hotels >= 2  → 90분 초과 날 분석 후 숙소 교체
    """

    @staticmethod
    def determine_hotels(
        num_hotels: int,
        base_hotel: Optional[Dict[str, Any]],
        num_days: int,
        daily_travel_times: List[List[int]],
        centroids: List[Tuple[float, float]],
        last_places_per_day: List[Optional[Dict[str, Any]]],
        hotel_candidates: List[Dict[str, Any]],
        user_data: Dict[str, Any],
    ) -> List[Optional[Dict[str, Any]]]:
        """
        일별 숙소 리스트를 결정한다.

        Args:
            num_hotels:          사용자가 선택한 숙소 수 (1 이면 고정)
            base_hotel:          기본 숙소 (사용자 첫 번째 숙소 또는 공항 폴백)
            num_days:            전체 여행 일수
            daily_travel_times:  Phase 3 결과 — 일별 구간 이동시간(초) 리스트
                                 [[day1 구간1, 구간2, ...], [day2 ...], ...]
            centroids:           Phase 2 결과 — 일별 클러스터 중심 좌표
                                 [(lat, lng), (lat, lng), ...]
            last_places_per_day: Phase 3 결과 — 일별 마지막 방문 장소 (또는 None)
            hotel_candidates:    숙소 후보 풀 (Phase 1 에서 분리된 호텔 리스트)
            user_data:           사용자 입력 (star_rating 등)

        Returns:
            night_hotels: 길이 (num_days - 1) 의 숙소 리스트
                          night_hotels[i] = i+1일차가 끝난 뒤 숙박할 숙소
                          마지막 날은 귀가/귀국이므로 리스트에 포함되지 않음
        """
        num_nights = num_days - 1

        # 숙박이 없는 여행 (당일치기)
        if num_nights <= 0:
            return []

        # ── 케이스 1: 단일 숙소 (앵커링 없음) ──────────────────────
        # num_hotels == 1: 사용자가 고정 숙소를 원하는 경우
        if num_hotels <= 1:
            return [base_hotel] * num_nights

        # ── 케이스 2: 멀티 숙소 — 이동시간 분석 후 앵커링 ─────────
        # max_changes: num_hotels=2 → 1회 교체, num_hotels=3 → 2회 교체
        max_changes = num_hotels - 1

        # 기본값: 모든 박 base_hotel
        night_hotels: List[Optional[Dict[str, Any]]] = [base_hotel] * num_nights

        # 90분(HOTEL_ANCHOR_TIME_THRESHOLD) 초과 날 탐색
        # daily_travel_times[i] = i+1 일차의 구간 이동시간 리스트
        over_threshold_days: List[int] = [
            i
            for i, times in enumerate(daily_travel_times)
            if any(t >= HOTEL_ANCHOR_TIME_THRESHOLD for t in times)
        ]

        if over_threshold_days:
            # ── 상황 A: 이동 부하 큰 날 기준 숙소 교체 (max_changes회까지) ──
            # 가장 심각한 날(최대 구간 이동시간 기준) 순으로 정렬 후 상위 max_changes개만 선택
            over_threshold_days.sort(
                key=lambda i: max(
                    (t for t in daily_travel_times[i] if t >= HOTEL_ANCHOR_TIME_THRESHOLD),
                    default=0,
                ),
                reverse=True,
            )
            days_to_change = sorted(over_threshold_days[:max_changes])

            for s_idx, day_idx in enumerate(days_to_change):
                if day_idx >= num_nights:
                    continue
                centroid = centroids[day_idx] if day_idx < len(centroids) else None
                if not centroid or centroid == (0.0, 0.0):
                    continue
                new_hotel = HotelAnchorService._find_nearest_hotel(
                    centroid[0], centroid[1],
                    hotel_candidates,
                    user_data,
                )
                if new_hotel:
                    # 이 교체 지점부터 다음 교체 지점 전날까지 새 숙소 적용
                    next_day = days_to_change[s_idx + 1] if s_idx + 1 < len(days_to_change) else num_nights
                    for i in range(day_idx, next_day):
                        if i < num_nights:
                            night_hotels[i] = new_hotel

        else:
            # ── 상황 B: 이동 부하 비슷 → 여행을 max_changes+1 구간으로 균등 분할 ──
            # num_hotels=2 → 여행 절반 지점에서 1회 교체
            # num_hotels=3 → 1/3, 2/3 지점에서 2회 교체
            if max_changes >= 1 and num_nights >= 2:
                segment_size = num_nights / (max_changes + 1)
                switch_nights: List[int] = []
                for k in range(1, max_changes + 1):
                    sn = max(1, min(int(round(segment_size * k)), num_nights - 1))
                    if sn not in switch_nights:
                        switch_nights.append(sn)
                switch_nights.sort()

                for s_idx, switch_night in enumerate(switch_nights):
                    last_place = (
                        last_places_per_day[switch_night]
                        if switch_night < len(last_places_per_day)
                        else None
                    )
                    if last_place and last_place.get('lat') and last_place.get('lng'):
                        new_hotel = HotelAnchorService._find_nearest_hotel(
                            float(last_place['lat']),
                            float(last_place['lng']),
                            hotel_candidates,
                            user_data,
                        )
                        if new_hotel:
                            # 이 교체 지점부터 다음 교체 지점 전날까지 적용
                            next_switch = switch_nights[s_idx + 1] if s_idx + 1 < len(switch_nights) else num_nights
                            for i in range(switch_night, next_switch):
                                if i < num_nights:
                                    night_hotels[i] = new_hotel

        return night_hotels

    # ─────────────────────────────────────────────────────────────────
    #  내부 헬퍼
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _find_nearest_hotel(
        target_lat: float,
        target_lng: float,
        hotel_candidates: List[Dict[str, Any]],
        user_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        목표 좌표(target_lat, target_lng)와 가장 가까운 숙소를 반환한다.

        탐색 우선순위:
          1. hotel_candidates 중 star_rating 조건 충족 + Haversine 최소
          2. star_rating 조건 무시하고 Haversine 최소 (완화 폴백)
          3. None 반환 (후보 없음 → 호출부에서 base_hotel 유지)

        Args:
            target_lat:       목표 위도 (클러스터 중심 또는 마지막 장소)
            target_lng:       목표 경도
            hotel_candidates: 숙소 후보 풀
            user_data:        사용자 입력 (star_rating)

        Returns:
            가장 가까운 숙소 dict, 없으면 None
        """
        if not hotel_candidates:
            return None

        min_star = float(user_data.get('star_rating', 3) or 3)

        # ① star_rating 조건 충족 후보로 필터
        qualified = [
            h for h in hotel_candidates
            if float(h.get('rating', 0) or 0) >= min_star
            and float(h.get('lat', 0) or 0) != 0.0
            and float(h.get('lng', 0) or 0) != 0.0
        ]

        # ② 조건 충족 후보 없으면 전체 후보로 완화
        if not qualified:
            qualified = [
                h for h in hotel_candidates
                if float(h.get('lat', 0) or 0) != 0.0
                and float(h.get('lng', 0) or 0) != 0.0
            ]

        if not qualified:
            return None

        # ③ Haversine 거리 최소 숙소 선택
        return min(
            qualified,
            key=lambda h: HotelAnchorService._haversine(
                target_lat, target_lng,
                float(h['lat']), float(h['lng']),
            ),
        )

    @staticmethod
    def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        두 좌표 간 Haversine 구면 거리 계산 (km).

        외부 DistanceService에 의존하지 않고 독립 동작하도록 내부 구현.
        (Phase 4는 API 추가 호출 없이 좌표 계산만으로 숙소를 선택한다)
        """
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlng / 2) ** 2
        )
        return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
