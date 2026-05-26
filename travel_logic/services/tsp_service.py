# travel_logic/services/tsp_service.py
"""
Phase 3: 1차 경로 최적화 (Nearest Neighbor TSP + 2-Opt)

개선 이력:
  v1: Nearest Neighbor Heuristic (최적 대비 최대 25% 오차)
  v2: 아래 4가지 개선 적용
    ① Dynamic TOP_N  - 장소 수에 따라 후보 필터 크기 자동 조정
    ② 2-Opt 후처리  - 교차 경로 제거, 이동거리 5~15% 추가 단축
    ③ end_point     - 숙소 복귀를 고려한 Round-trip 최적화
    ④ find_best_meal_insertion() - 경로 우회 최소화 식사 위치 선택

알고리즘: Nearest Neighbor → 2-Opt (Haversine 기반, API 추가 호출 없음)
복잡도: O(N²) Nearest Neighbor + O(N²) 2-Opt (실용 범위 N≤20에서 수ms)

입력: places      (하루 방문 후보 관광지 리스트)
      start_point (출발지: 숙소 또는 공항)
      end_point   (복귀지: 당일 숙박 호텔. None이면 Round-trip 미고려)
출력: ordered_places (최적 방문 순서)
      travel_times   (구간별 이동시간 초 리스트)
      total_time     (총 이동시간 합계 초)
"""

import math
from typing import List, Dict, Any, Tuple, Optional

from .distance_service import DistanceService


class TSPService:
    """
    Nearest Neighbor + 2-Opt 기반 1차 경로 최적화 서비스.

    [v2 개선 사항]
      ① Dynamic TOP_N  : 장소 수에 따라 API 후보 필터 동적 조정
      ② 2-Opt 후처리  : Haversine 기반 교차 제거 (API 추가 호출 없음)
      ③ end_point      : 하루 종료 후 숙소 복귀 거리를 경로 최적화에 반영
      ④ find_best_meal_insertion() : 식사 장소를 경로 우회 최소 위치에 삽입
    """

    def __init__(self, distance_service: DistanceService):
        self.distance_service = distance_service

    # ─────────────────────────────────────────────────────────────
    #  ① Dynamic TOP_N
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _get_filter_n(total_places: int) -> int:
        """
        장소 수에 따라 직선거리 선행 필터 크기를 동적으로 결정.
        - 장소가 적으면 전체 조회 (후보 누락 없음)
        - 장소가 많으면 일부만 조회 (API 비용 절감)
        """
        if total_places <= 5:
            return total_places     # 전체 조회
        if total_places <= 15:
            return 8
        if total_places <= 30:
            return 12
        return 15                   # 30개 초과: 상위 15개

    # ─────────────────────────────────────────────────────────────
    #  공개 메서드 — solve()
    # ─────────────────────────────────────────────────────────────

    def solve(
        self,
        places: List[Dict[str, Any]],
        start_point: Optional[Dict[str, Any]],
        is_korea: bool,
        travel_mode: str,
        end_point: Optional[Dict[str, Any]] = None,   # ③ Round-trip 복귀지
        haversine_only: bool = False,                  # ④ True면 실제 API 호출 없이 Haversine만 사용
    ) -> Tuple[List[Dict[str, Any]], List[int], int]:
        """
        Nearest Neighbor + 2-Opt 알고리즘으로 하루 방문 순서를 최적화한다.

        Args:
            places:         하루 방문할 관광지 리스트
            start_point:    출발지(숙소/공항). None이면 Haversine Greedy 폴백.
            is_korea:       국내 여행 여부 (True → KakaoAPI, False → GoogleAPI)
            travel_mode:    'driving' | 'transit'
            end_point:      하루 종료 후 복귀할 숙소. None이면 Round-trip 미고려.
                            2-Opt 시 마지막 장소 → end_point 이동거리를 비용에 포함.
            haversine_only: True면 실제 API 호출 없이 Haversine 직선거리로만 NN 수행.
                            Phase 3 pre-run처럼 대소 판별만 필요할 때 사용 (API 비용 절감).

        Returns:
            ordered_places: 최적 방문 순서로 정렬된 장소 리스트
            travel_times:   구간별 이동시간(초) 리스트 (Haversine 근사)
            total_time:     총 이동시간 합계(초)

        [알고리즘 순서]
          ① Nearest Neighbor: 현재 위치에서 가장 가까운 미방문 장소 반복 선택
             - 직선거리 Dynamic TOP_N으로 후보 필터 → bulk 이동시간 조회(캐시 우선)
          ② 2-Opt: Haversine 기반 교차 제거 (API 추가 호출 없음)
             - end_point 있으면 마지막→end_point 복귀 거리도 비용에 포함
        """
        if not places:
            return [], [], 0

        # 출발점 좌표 검증 — 없거나 0.0이면 Haversine Greedy로 대체
        sp_lat = (start_point or {}).get('lat', 0.0) or 0.0
        sp_lng = (start_point or {}).get('lng', 0.0) or 0.0
        if not start_point or sp_lat == 0.0 or sp_lng == 0.0:
            return self._haversine_greedy(places), [], 0

        # ── ① Nearest Neighbor ───────────────────────────────────
        unvisited: List[Dict[str, Any]] = places[:]
        ordered:   List[Dict[str, Any]] = []
        current = start_point

        while unvisited:
            # Dynamic TOP_N 선행 필터
            top_n = min(self._get_filter_n(len(unvisited)), len(unvisited))
            candidates_sorted = sorted(
                unvisited,
                key=lambda p: self.distance_service.haversine_distance(
                    current.get('lat', 0.0), current.get('lng', 0.0),
                    p['lat'], p['lng'],
                )
            )
            top_candidates = candidates_sorted[:top_n]

            if haversine_only:
                # Haversine 최단 거리 장소를 바로 선택 (API 호출 없음)
                best_place = top_candidates[0]
            else:
                # bulk 실제 이동시간 조회 (캐시 → API)
                results = self.distance_service.get_travel_times_bulk(
                    current.get('lat', 0.0), current.get('lng', 0.0),
                    top_candidates, is_korea, travel_mode,
                )
                results.sort(key=lambda x: x[0])
                _, best_place = results[0]

            ordered.append(best_place)
            unvisited.remove(best_place)
            current = best_place

        # ── ② 2-Opt (Haversine 기반, API 추가 호출 없음) ─────────
        if len(ordered) >= 3:
            ordered = self._two_opt_haversine(ordered, end_point)

        # 최종 travel_times: Haversine 근사(캐시 없는 새 구간 대비 빠른 계산)
        travel_times = self._calc_haversine_times(
            start_point, ordered, is_korea
        )

        return ordered, travel_times, sum(travel_times)

    # ─────────────────────────────────────────────────────────────
    #  공개 메서드 — ④ find_best_meal_insertion()
    # ─────────────────────────────────────────────────────────────

    def find_best_meal_insertion(
        self,
        meal_candidates: List[Dict[str, Any]],
        prev_place: Optional[Dict[str, Any]],
        next_place: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        식사 장소를 현재 경로에 우회 최소 지점으로 삽입한다.

        prev_place → [meal] → next_place 구간에서
        detour = dist(prev→meal) + dist(meal→next) - dist(prev→next) 가 최소인 장소 반환.

        Args:
            meal_candidates: 후보 식사 장소 리스트 (visited 필터 후)
            prev_place:      직전 방문 장소 (현재 위치)
            next_place:      TSP 큐의 다음 관광지 (peek, pop 아님)

        Returns:
            detour가 최소인 식사 장소. 후보 없으면 None.
        """
        if not meal_candidates:
            return None
        # 기준점이 없으면 첫 번째 반환 (fallback)
        if not prev_place or not next_place:
            return meal_candidates[0]

        prev_lat = prev_place.get('lat', 0.0)
        prev_lng = prev_place.get('lng', 0.0)
        next_lat = next_place.get('lat', 0.0)
        next_lng = next_place.get('lng', 0.0)

        direct = self.distance_service.haversine_distance(
            prev_lat, prev_lng, next_lat, next_lng
        )

        best_place:  Optional[Dict[str, Any]] = None
        best_detour: float = float('inf')

        for meal in meal_candidates:
            m_lat = meal.get('lat', 0.0)
            m_lng = meal.get('lng', 0.0)
            d1 = self.distance_service.haversine_distance(prev_lat, prev_lng, m_lat, m_lng)
            d2 = self.distance_service.haversine_distance(m_lat, m_lng, next_lat, next_lng)
            detour = d1 + d2 - direct
            if detour < best_detour:
                best_detour = detour
                best_place  = meal

        return best_place

    # ─────────────────────────────────────────────────────────────
    #  내부 헬퍼
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _two_opt_haversine(
        places: List[Dict[str, Any]],
        end_point: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        ② 2-Opt: Haversine 직선거리 기반 교차 경로 제거.

        - API 추가 호출 없이 순수 수학 계산만 사용 → 비용 없음
        - end_point 있으면 총 거리에 마지막→end_point 복귀 거리 포함
          (Round-trip 최적화: 숙소에서 멀리 떨어진 장소를 마지막으로 두지 않음)
        - O(N²) 반복, N≤20에서 수ms 이내 수렴
        """
        if len(places) <= 2:
            return places

        def _hav(p1: Dict, p2: Dict) -> float:
            R = 6371.0
            dlat = math.radians(p2['lat'] - p1['lat'])
            dlng = math.radians(p2['lng'] - p1['lng'])
            a = (
                math.sin(dlat / 2) ** 2
                + math.cos(math.radians(p1['lat']))
                * math.cos(math.radians(p2['lat']))
                * math.sin(dlng / 2) ** 2
            )
            return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

        def total_dist(route: List[Dict]) -> float:
            d = sum(_hav(route[i], route[i + 1]) for i in range(len(route) - 1))
            if end_point:
                d += _hav(route[-1], end_point)
            return d

        route = places[:]
        improved = True
        while improved:
            improved = False
            for i in range(len(route) - 1):
                for j in range(i + 2, len(route)):
                    # i+1 ~ j 구간 역전 시도
                    new_route = route[:i + 1] + route[i + 1:j + 1][::-1] + route[j + 1:]
                    if total_dist(new_route) < total_dist(route) - 1e-9:
                        route = new_route
                        improved = True
        return route

    @staticmethod
    def _calc_haversine_times(
        start: Dict[str, Any],
        ordered: List[Dict[str, Any]],
        is_korea: bool,   # [L-1] 국내(75km/h) / 해외(50km/h) 속도 상수 분기
    ) -> List[int]:
        """
        2-Opt 후 재정렬된 경로의 구간별 이동시간을 Haversine 근사로 계산.
        [H-4 fix] 45km/h (기존 60km/h): Haversine은 직선거리이므로 실제 도로 대비
        20-40% 짧음. 45km/h로 낮춰 보수적(큰) 이동시간을 추정하여
        Phase 4 호텔 앵커링 기준(90분 임계치)이 적절히 발동되도록 조정.
        """
        # [L-1] 국내: 도로망 밀집, 속도 제한 높음 → 75km/h 기준
        #        해외: 도시 구조 다양, 교통 혼잡 → 50km/h 기준
        #        haversine_only pre-run 목적이므로 45km/h 보정 유지 (보수적 추정)
        SPEED_KMH = 45.0 if not is_korea else 42.0  # 국내도 직선거리 보정 적용

        def _hav(lat1, lng1, lat2, lng2) -> float:
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

        times: List[int] = []
        prev = start
        for place in ordered:
            km = _hav(
                prev.get('lat', 0.0), prev.get('lng', 0.0),
                place['lat'], place['lng'],
            )
            times.append(int(km / SPEED_KMH * 3600))
            prev = place
        return times

    @staticmethod
    def _haversine_greedy(
        places: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        start_point 없을 때 폴백: Haversine 직선거리 기반 Greedy 정렬.
        API 호출 없이 빠르게 근사 최적 순서를 반환한다.
        첫 번째 장소를 기준점으로 삼아 남은 장소를 가장 가까운 순으로 연결.
        """
        if not places:
            return []

        def _hav(lat1, lng1, lat2, lng2) -> float:
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

        unvisited = places[:]
        ordered   = [unvisited.pop(0)]

        while unvisited:
            cur     = ordered[-1]
            nearest = min(
                unvisited,
                key=lambda p: _hav(cur['lat'], cur['lng'], p['lat'], p['lng'])
            )
            ordered.append(nearest)
            unvisited.remove(nearest)

        return ordered
