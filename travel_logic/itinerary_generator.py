# itinerary_generator.py
"""
여행 일정 생성 메인 로직
"""

import random
import sys
import os
from datetime import date, timedelta, datetime, time
from typing import List, Dict, Any, Optional

# backend 모듈 import를 위한 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import backend_postgres as backend  # DB부: backend_postgres 사용 (PostGIS 기반)

from .config import VISIT_TIMES, LUNCH_START_RANGE, DINNER_START_RANGE
from .config.constants import (
    HOTEL_CATEGORIES, CANDIDATE_POOL_RATIO, AIRPORT_COORDS,
    PLACE_STALE_WARNING_DAYS, PLACE_STALE_HIGH_RISK_DAYS,
    # Phase 5: 타임박싱 상수
    PACE_MAX_PLACES, COMPANION_STAY_MULTIPLIER,
    CUTOFF_HOUR, TRANSIT_LAST_HOUR,
)
from .domain import check_is_domestic
from .services import ScoringService, DistanceService, OptimizationService, DBService, ClusteringService, TSPService, HotelAnchorService
from .strategies import CoreStrategy, FoodieStrategy, NatureStrategy, ActiveStrategy
from .exceptions import InsufficientPlacesError


class ItineraryGenerator:
    """여행 일정 생성기"""
    
    def __init__(self):
        self.scoring_service = ScoringService()
        self.distance_service = DistanceService()
        self.optimization_service = OptimizationService(self.distance_service)
        self.tsp_service = TSPService(self.distance_service)  # Phase 3: 1차 경로 최적화
        # Phase 4: HotelAnchorService는 상태 없는 정적 메서드만 사용 (인스턴스 불필요)
        self.db_service = DBService()
        
        # 테마별 전략 매핑
        self.strategies = {
            "✨ 핵심 코스": CoreStrategy(),
            "🍽️ 식도락 & 힐링": FoodieStrategy(),
            "🌿 자연 & 관광": NatureStrategy(),
            "🔥 액티브 & 핫플": ActiveStrategy()
        }
    
    def generate(self, user_data: Dict[str, Any], duration: int) -> List[Dict[str, Any]]:
        """
        여행 일정 생성
        
        Args:
            user_data: 사용자 입력 데이터
            duration: 여행 기간 (일)
            
        Returns:
            테마별 일정 리스트
        """
        city = user_data.get('dest_city')
        if not city:
            return []

        # 데이터 자동 업데이트 (필요시)
        if not self.db_service.ensure_data_exists(city, user_data.get('style', [])):
            return []

        # ── [Phase 1] 필터링 & 점수화 ──────────────────────────────
        # _categorize_places에서 extract_top_n을 쓰려면 duration이 필요.
        # user_data에 _duration 키로 전달 (외부 API 계약 변경 없이 내부 전달)
        user_data['_duration'] = duration

        # 데이터 로드 → hard_filter → 점수 계산 & 정렬
        places = self._load_and_preprocess_places(city, user_data)
        if not places:
            return []

        # 숙소 별도 풀 분리 → extract_top_n → categorize_visits
        sights, foods, cafes, hotels, airport_place = self._categorize_places(
            places, user_data
        )

        # ── [Phase 2] 지리적 K-Means 클러스터링 ────────────────────
        # 관광지(sights)를 여행 일수 기준으로 지리적 군집으로 분류.
        # - 각 클러스터 = 해당 날 방문할 권역 (강남권, 강북권 등)
        # - _generate_for_theme()에서 날짜별로 해당 클러스터만 사용
        # - foods/cafes는 이동 중 유연하게 삽입되으므로 전체 풀 유지

        # ── [장소 부족 감지] Phase 1 통과 후 관광지 수가 일수에 미달 시 ──────
        # 모듈이 InsufficientPlacesError를 직접 raise → API가 직접 사용자에게 안내
        min_required = max(duration, 1)
        if len(sights) < min_required:
            raise InsufficientPlacesError(
                city=city,
                available=len(sights),
                required=min_required,
                budget_level=user_data.get('budget_level', '중'),
                relaxed=bool(user_data.get('_relax_filter', False)),
            )

        # ── [개선점 D] Seeded K-Means: 앵커 포인트 구성 ──────────────────
        # 공항(첫날 출발지)과 멀티호텔(이동 여행) 좌표를 초기 중심점으로 사용.
        # 단일 숙소(num_hotels=1) 경우 모든 클러스터가 같은 점으로 수렴하므로 시드 없이 진행.
        kmeans_anchors = []
        if airport_place:
            kmeans_anchors.append(airport_place)   # 첫날: 공항 → 클러스터 앵커
        if user_data.get('num_hotels', 1) > 1 and hotels:
            top_hotels = sorted(hotels, key=lambda h: h.get('score', 0), reverse=True)
            remaining = max(0, duration - len(kmeans_anchors))
            kmeans_anchors.extend(top_hotels[:remaining])

        sight_clusters, day_centroids = ClusteringService.cluster_by_day(
            sights, duration,
            anchor_points=kmeans_anchors if kmeans_anchors else None,
        )

        # 테마별 일정 생성
        final_plans = []
        is_korea = check_is_domestic(city)

        # ── [Phase 3 사전 실행] 일별 이동시간 + 마지막 방문 장소 수집 ────────
        # Phase 4 숙소 앵커링 판단을 위해 base_hotel 기준으로 전 날짜 TSP를 사전 실행.
        # 테마 독립적이므로 한 번만 실행하여 모든 테마에 공유한다.
        _local_transport = str(user_data.get('local_transport', '자차') or '자차')
        _travel_mode_pre = 'driving' if _local_transport in ('렌트카', '자차') else 'transit'

        # base_hotel: Phase 4 앵커링의 기준점 — 실제 숙소를 사용해야 함
        # ※ 공항은 출발/도착 지점이지 숙소가 아님. 비행 여행이라도 hotels[0]을 base로 사용.
        #   (이전 버그: airport_place를 base_hotel로 사용 → 모든 박이 공항으로 지정되는 문제)
        base_hotel: Optional[Dict[str, Any]] = hotels[0] if hotels else airport_place

        daily_travel_times_p3: List[List[int]] = []
        last_places_per_day: List[Optional[Dict[str, Any]]] = []

        for _day_idx in range(duration):
            _pre_pool = (
                sight_clusters[_day_idx]
                if sight_clusters and _day_idx < len(sight_clusters) and sight_clusters[_day_idx]
                else sights
            )
            _day_start = (
                airport_place
                if (_day_idx == 0 and '항공' in user_data.get('transport', []) and airport_place)
                else base_hotel
            )
            if _pre_pool:
                _ordered, _times, _ = self.tsp_service.solve(
                    _pre_pool[:],
                    start_point=_day_start,
                    end_point=_day_start,
                    is_korea=is_korea,
                    travel_mode=_travel_mode_pre,
                    haversine_only=True,   # Phase 3 pre-run: 이동시간 대소 판별만 필요 → Haversine 근사로 충분
                )
                daily_travel_times_p3.append(list(_times))
                last_places_per_day.append(_ordered[-1] if _ordered else None)
            else:
                daily_travel_times_p3.append([])
                last_places_per_day.append(None)

        # ── [Phase 4] 숙소 앵커링: 이동시간 분석 후 박별 숙소 위치 확정 ────
        # 90분 초과 날 → 해당 날 클러스터 중심 근처 숙소로 교체 (상황 A)
        # 전 날 비슷  → 여행 중간 날 마지막 장소 근처 숙소로 교체 (상황 B)
        # num_hotels == 1 → 앵커링 없이 base_hotel 고정 반환
        night_stay_hotels: List[Optional[Dict[str, Any]]] = HotelAnchorService.determine_hotels(
            num_hotels=user_data.get('num_hotels', 1),
            base_hotel=base_hotel,
            num_days=duration,
            daily_travel_times=daily_travel_times_p3,
            centroids=day_centroids,
            last_places_per_day=last_places_per_day,
            hotel_candidates=hotels,
            user_data=user_data,
        )

        # 사용자 입력 기반으로 테마 동적 결정
        themes = self._build_themes(user_data, city)

        for theme in themes:
            strategy = self.strategies.get(theme['strategy_key'], self.strategies["✨ 핵심 코스"])

            days = self._generate_for_theme(
                theme, strategy, duration, sights, sight_clusters, foods, cafes,
                hotels, airport_place, user_data, is_korea,
                night_stay_hotels=night_stay_hotels,  # [Phase 4] 확정된 박별 숙소
            )
            
            final_plans.append({
                "theme": theme['name'],
                "desc": theme['desc'],
                "score": self._calc_theme_score(days, user_data, theme['strategy_key']),
                "tags": user_data.get('style', []),
                "days": days
            })
        
        return final_plans
    
    def _load_and_preprocess_places(
        self, 
        city: str, 
        user_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        [Phase 1 — Step A] DB에서 장소 로드 → 중복 제거 → hard_filter → 점수 계산 & 정렬

        반환값은 score 내림차순으로 정렬된 전체 장소 리스트.
        숙소/방문 장소 분리는 _categorize_places()에서 수행.
        """
        places = backend.get_places(city)

        # ── 1단계: 이름 없는 장소 제거 + 중복 제거 ──────────────
        unique_places = []
        seen_names = set()
        for p in places:
            if not p.get('name'):
                continue
            clean_name = ''.join(filter(str.isalnum, p['name'])).lower()
            if clean_name not in seen_names:
                seen_names.add(clean_name)
                unique_places.append(p)

        # ── 2단계: [Phase 1] hard_filter — 예산·좌표·배리어프리 ──
        #    - 예산 수준별 최소 평점 미충족 즉시 제거
        #    - 좌표(lat/lng)가 0.0 이거나 없는 장소 제거
        #    - 배리어프리 조건은 DB 태그 없어 현재 pass (TourAPI 연동 후 활성)
        hard_filtered = self.scoring_service.hard_filter(unique_places, user_data)

        # ── 3단계: 점수 계산 & 내림차순 정렬 ─────────────────────
        scored_places = []
        for p in hard_filtered:
            score, tags = self.scoring_service.calculate_score(p, user_data)
            p['score'] = score
            p['matched_tags'] = tags
            scored_places.append(p)

        scored_places.sort(key=lambda x: x['score'], reverse=True)

        return scored_places
    
    def _categorize_places(
        self, 
        places: List[Dict[str, Any]], 
        user_data: Dict[str, Any]
    ) -> tuple:
        """
        [Phase 1 — Step B] 장소를 숙소 풀 / 방문 후보 풀로 분리한 뒤
        방문 후보에서 extract_top_n → categorize_visits 수행.

        plan.md 설계 원칙:
          ★ 숙소는 star_rating 조건만 적용, top_N 제한 없이 별도 풀로 관리
            (이유: top_N 안에 숙소 0개일 경우 Phase 4 앵커링 불가 방지)
          ★ 방문 장소(관광·식당·카페)만 점수 순위로 top_N 추출
          ★ HOTEL_CATEGORIES 상수로 숙소 분류 기준 일원화
        """
        city = user_data.get('dest_city', '')

        # ── 공항 설정: AIRPORT_COORDS 딕셔너리 방식 (하드코딩 제거) ──
        #    미등록 도시 → airport_place = None
        airport_place = None
        if '항공' in user_data.get('transport', []):
            coords = AIRPORT_COORDS.get(city)
            if coords:
                airport_place = {
                    "id": "airport_start",
                    "source": "system",
                    "name": coords['name'],
                    "city": city,
                    "category": "airport",
                    "lat": coords['lat'],
                    "lng": coords['lng'],
                    "address": "공항 출발/도착",
                    "rating": 5.0,
                    "img_url": "",
                    "score": 100,
                    "desc": "여행 시작/마무리 지점"
                }
            else:
                # 미등록 도시: 공항 정보 없음 (None 유지)
                pass

        # ── [Phase 1] 숙소 별도 풀: HOTEL_CATEGORIES 상수 기반 + star_rating 조건 ──
        min_hotel_rating = float(user_data.get('star_rating', 3))
        hotels = [
            p for p in places
            if (
                any(kw in str(p.get('category', '')) for kw in HOTEL_CATEGORIES)
                and float(p.get('rating', 0)) >= min_hotel_rating
            )
        ]

        # ── [Phase 1] 방문 장소만 남김 (숙소 제외) ──────────────────
        hotel_ids = {p.get('id') for p in hotels}
        non_hotels = [p for p in places if p.get('id') not in hotel_ids]

        # ── [Phase 1] extract_top_n: 여행일수 × CANDIDATE_POOL_RATIO 개만 추출 ──
        #    places는 이미 score 내림차순 정렬되어 있음
        num_days = user_data.get('_duration', len(non_hotels) // CANDIDATE_POOL_RATIO or 1)
        candidate_pool = self.scoring_service.extract_top_n(non_hotels, num_days)

        # ── [Phase 1] categorize_visits: 관광·식당·카페로 분류 ───────
        sights, foods, cafes = self.scoring_service.categorize_visits(
            candidate_pool, user_data
        )

        # 예비 후보 (분류 결과가 빈 경우 fallback)
        if not sights:
            sights = non_hotels[:20]
        if not foods:
            foods = non_hotels[:15]
        if not cafes:
            cafes = non_hotels[:5]
        if not hotels:
            hotels = [airport_place] if airport_place else []

        return sights, foods, cafes, hotels, airport_place
    
    def _generate_for_theme(
        self,
        theme: Dict[str, str],
        strategy: Any,
        duration: int,
        all_sights: List[Dict],
        sight_clusters: List[List[Dict]],  # [Phase 2] 날짜별 관광지 클러스터
        all_foods: List[Dict],
        all_cafes: List[Dict],
        all_hotels: List[Dict],
        airport_place: Optional[Dict],
        user_data: Dict[str, Any],
        is_korea: bool,
        night_stay_hotels: Optional[List[Optional[Dict]]] = None,  # [Phase 4] 확정된 박별 숙소
    ) -> List[Dict[str, Any]]:
        """테마별 일정 생성"""
        # [Phase 1 완료 후 전달된 장소들] score 기준 재정렬 (안전 보장)
        # ※ check_place_status() 호출 제거:
        #     Phase 1 hard_filter의 평점 조건으로 폐업 장소 자연 필터링됨
        #     (Google API 2회 호출 → 비용·속도 문제 해결)
        all_sights.sort(key=lambda x: x.get('score', 0), reverse=True)
        all_foods.sort(key=lambda x: x.get('score', 0), reverse=True)
        all_cafes.sort(key=lambda x: x.get('score', 0), reverse=True)

        # 장소 풀 생성 및 셔플
        # pool_sights: sight_clusters가 없을 경우를 대비한 fallback 전체 풀
        pool_sights, pool_foods, pool_cafes = all_sights[:], all_foods[:], all_cafes[:]
        random.shuffle(pool_sights)
        random.shuffle(pool_foods)
        random.shuffle(pool_cafes)
        
        # 전략에 따른 장소 개수 결정
        distribution = strategy.get_place_distribution(user_data)
        num_sights = distribution['sights']
        num_foods = distribution['foods']
        num_cafes = distribution['cafes']
        
        # 일일 스케줄 생성
        daily_schedule = self._create_daily_schedule(num_sights, num_foods, num_cafes)
        
        # local_transport는 문자열(str) 타입
        # 예: "렌트카", "자차", "대중교통" 등
        local_transport = str(user_data.get('local_transport', '자차') or '자차')
        is_driving = local_transport in ('렌트카', '자차')
        travel_mode = 'driving' if is_driving else 'transit'
        
        # 전략 가중치
        strategy_weights = strategy.get_weights()

        # ── [Phase 5] 타임박싱 파라미터 계산 ──────────────────────────
        # ① PACE Cut-off: 일정 강도별 하루 최대 관광지 방문 수
        pace = str(user_data.get('pace', '보통') or '보통')
        _pace_limit = PACE_MAX_PLACES.get(pace, (2, 3))
        max_sights_per_day: int = (
            _pace_limit if isinstance(_pace_limit, int) else _pace_limit[1]
        )

        # [BUG-4 fix] 전략이 반환한 num_sights가 PACE 상한을 초과하면
        # 슬롯 수를 재조정하고 daily_schedule도 다시 생성한다.
        if num_sights > max_sights_per_day:
            num_sights = max_sights_per_day
            daily_schedule = self._create_daily_schedule(num_sights, num_foods, num_cafes)

        # ② 동행자별 체류시간 배율 (부모님 동반: ×1.2, 아이 동반: ×1.3)
        companions = user_data.get('companions', [])
        stay_multiplier: float = COMPANION_STAY_MULTIPLIER.get('default', 1.0)
        for companion_key, multiplier in COMPANION_STAY_MULTIPLIER.items():
            if companion_key != 'default' and companion_key in companions:
                stay_multiplier = max(stay_multiplier, multiplier)
        # with_kids=True도 아이 동반으로 처리
        if user_data.get('with_kids', False):
            stay_multiplier = max(stay_multiplier, COMPANION_STAY_MULTIPLIER.get('아이 동반', 1.3))
        
        # ── [Phase 4 결과 수신] 확정된 박별 숙소 사용 ──────────────────────
        # Phase 4(HotelAnchorService)가 이동시간을 분석해 최적 위치로 결정한 숙소 리스트.
        # generate()에서 전달되지 않은 경우(레거시 경로)에는 첫 번째 호텔로 폴백.
        if night_stay_hotels is None:
            _fallback_hotel = all_hotels[0] if all_hotels else None
            night_stay_hotels = [_fallback_hotel] * max(0, duration - 1)

        # last_night_hotel: 현재 날짜의 출발 숙소 (루프 내에서 갱신됨)
        # 1일차 시작: Phase 4가 결정한 첫 번째 박 숙소 (공항은 숙소가 아니므로 hotels 우선)
        # ※ 1일차 "도착 지점" 표시는 아래 d==1 블록에서 airport_place로 별도 처리됨
        last_night_hotel: Optional[Dict[str, Any]] = (
            night_stay_hotels[0] if night_stay_hotels and night_stay_hotels[0]
            else (all_hotels[0] if all_hotels else None)
        )
        
        # 일차별 일정 생성
        days = []
        visited_place_ids = set()
        
        for d in range(1, duration + 1):
            # ── [Phase 2] 해당 일차의 관광지 클러스터 결정 ──────────
            # sight_clusters[d-1]: 해당 날짜의 지리적 권역 장소만 포함
            # fallback: 클러스터가 없거나 비어있으면 전체 pool_sights 사용
            if sight_clusters and (d - 1) < len(sight_clusters) and sight_clusters[d - 1]:
                day_sight_pool = sight_clusters[d - 1]  # 해당 일차 클러스터
            else:
                day_sight_pool = pool_sights  # fallback: 전체 풀

            # ── [Phase 5] 확정 숙소 기준 최종 TSP 재실행 ──────────────────
            # Phase 4가 night_stay_hotels를 확정했으므로,
            # 전날 숙소(d-2번째 박 숙소)를 실제 출발지로 사용하여 TSP 재계산.
            # - 1일차: 항공편이면 공항, 아니면 night_stay_hotels[0] (또는 base_hotel)
            # - 2일차~: night_stay_hotels[d-2] (= 전날 박 숙소)
            if d == 1:
                day_start_for_tsp = (
                    airport_place
                    if ('항공' in user_data.get('transport', []) and airport_place)
                    else last_night_hotel
                )
            else:
                prev_night_idx = d - 2  # 전날 밤 숙소 인덱스 (0-based)
                day_start_for_tsp = (
                    night_stay_hotels[prev_night_idx]
                    if night_stay_hotels and prev_night_idx < len(night_stay_hotels)
                    else last_night_hotel
                ) or last_night_hotel

            # 오늘 밤 숙소: Round-trip end_point로 사용 (Phase 5 확정 숙소)
            tonight_idx = d - 1  # 오늘 밤 숙소 인덱스 (0-based)
            tonight_hotel = (
                night_stay_hotels[tonight_idx]
                if night_stay_hotels and tonight_idx < len(night_stay_hotels)
                else last_night_hotel
            )

            # [Phase 5] 관광지 방문 수 카운터 초기화
            sights_visited_today: int = 0

            unvisited_day_sights = [
                p for p in day_sight_pool
                if p.get('id') not in visited_place_ids
            ]
            if unvisited_day_sights:
                tsp_ordered, _, _ = self.tsp_service.solve(
                    unvisited_day_sights,
                    start_point=day_start_for_tsp,
                    end_point=tonight_hotel,   # [Phase 5] 확정 숙소 복귀 Round-trip
                    is_korea=is_korea,
                    travel_mode=travel_mode,
                )
            else:
                tsp_ordered = []
            # TSP 순서 큐: 일정 루프에서 pop(0)으로 하나씩 충당
            tsp_queue = list(tsp_ordered)

            day_places = []
            last_place = None
            current_time = datetime.combine(date.today(), time(9, 0, 0))
            
            # Day 시작 지점 설정
            if d == 1:
                if '항공' in user_data.get('transport', []) and airport_place:
                    current_day_start_point = airport_place
                else:
                    current_day_start_point = last_night_hotel or airport_place
                
                if current_day_start_point:
                    # [BUG-6 fix] 공유 dict 직접 변이 방지 → 복사본에 is_start_point 설정
                    current_day_start_point = {**current_day_start_point, 'is_start_point': True}
                    day_places.append(self._make_place(
                        current_time.strftime("%H:%M"),
                        "도착 지점",
                        current_day_start_point,
                        "숙소"
                    ))
                    last_place = {**current_day_start_point, 'type_key': '숙소'}
            
            elif d > 1 and last_night_hotel:
                # [BUG-6 fix] 공유 dict 직접 변이 방지 → 복사본에 is_start_point 설정
                current_day_start_point = {**last_night_hotel, 'is_start_point': True}
                day_places.append(self._make_place(
                    current_time.strftime("%H:%M"),
                    "숙소 출발",
                    current_day_start_point,
                    "숙소"
                ))
                last_place = {**current_day_start_point, 'type_key': '숙소'}
            
            # 장소 방문 루프
            for _, type_kor, type_key in daily_schedule:
                if type_key == "식사":
                    candidates_pool = pool_foods
                elif type_key == "카페":
                    candidates_pool = pool_cafes
                elif type_key == "관광":
                    # [Phase 2 적용] 전체 풀 대신 당일 지리적 클러스터 사용
                    # → 강남권 날엔 강남 장소만, 강북권 날엔 강북 장소만 후보로
                    candidates_pool = day_sight_pool
                else:
                    continue
                
                candidates = [p for p in candidates_pool if p['id'] not in visited_place_ids]
                if not candidates:
                    continue
                
                # ── [Phase 5-①] PACE Cut-off: 관광지 방문 수 제한 ──────────
                # pace별 최대 방문 수(max_sights_per_day)를 초과하면 해당 관광 슬롯 스킵
                if type_key == "관광" and sights_visited_today >= max_sights_per_day:
                    continue

                # ① [Phase 3 v2] 장소 유형별 최적화 선택
                #    관광지 : TSP 큐에서 순서대로 소비
                #    식사   : find_best_meal_insertion() — 우회 최소 위치 삽입
                #    카페   : epsilon-greedy (기존 유지)
                if type_key == "관광":
                    selected = None
                    while tsp_queue:
                        candidate = tsp_queue.pop(0)
                        if candidate.get('id') not in visited_place_ids:
                            selected = candidate
                            break
                elif type_key == "식사":
                    # TSP 큐 다음 관광지를 peek하여 우회 최소 식당 선택
                    next_sight = tsp_queue[0] if tsp_queue else None
                    selected = self.tsp_service.find_best_meal_insertion(
                        candidates, last_place, next_sight
                    )
                    if not selected:   # fallback
                        selected = self.optimization_service.select_next_place(
                            candidates, last_place, strategy_weights,
                            is_korea, travel_mode, type_key
                        )
                else:  # 카페
                    selected = self.optimization_service.select_next_place(
                        candidates, last_place, strategy_weights,
                        is_korea, travel_mode, type_key
                    )

                if not selected:
                    continue

                # ② 선택된 장소까지 이동 시간 계산
                #    [BUG-1/2/3 fix] current_time을 먼저 업데이트하지 않고
                #    departure_time / arrival_time을 분리 계산 후 Cut-off 통과 시 확정
                visit_duration_seconds = 0
                travel_duration_seconds = 0
                if last_place and last_place.get('lat', 0.0) != 0.0 and last_place.get('lng', 0.0) != 0.0:
                    prev_place_type_key = last_place.get('type_key', 'default')
                    # [Phase 5-②] 동행자 배율 적용한 체류시간
                    #             숙소 타입은 출발 준비 시간이 고정이므로 배율 미적용 (BUG-3 fix)
                    base_visit_sec = VISIT_TIMES.get(prev_place_type_key, VISIT_TIMES['default'])
                    if prev_place_type_key != '숙소':
                        visit_duration_seconds = int(base_visit_sec * stay_multiplier)
                    else:
                        visit_duration_seconds = int(base_visit_sec)

                    travel_duration_seconds = self.distance_service.get_travel_time(
                        last_place['lat'], last_place['lng'],
                        selected['lat'], selected['lng'],
                        is_korea, travel_mode
                    )

                    if travel_duration_seconds == 999999:
                        travel_duration_seconds = 30 * 60

                # ── [Phase 5-③] 시간 Cut-off: 밤 11시 이후 및 대중교통 막차 제한 ──
                # departure_time: last_place 체류 후 이동을 시작하는 시각
                # arrival_time  : selected에 도착하는 시각 (Cut-off 판단 기준)
                departure_time = current_time + timedelta(seconds=visit_duration_seconds)
                arrival_time   = departure_time + timedelta(seconds=travel_duration_seconds)

                # (a) 대중교통 모드: TRANSIT_LAST_HOUR(22시) 이후 이동 시작이면 스킵
                if travel_mode == 'transit' and departure_time.hour >= TRANSIT_LAST_HOUR:
                    continue

                # (b) 도착 예정 시각이 CUTOFF_HOUR(23시) 이상이거나 다음날이면 스킵
                if (arrival_time.date() > departure_time.date()  # 자정 넘어 다음날
                        or arrival_time.hour >= CUTOFF_HOUR):
                    continue

                # 모든 Cut-off 통과 → current_time을 도착 시각으로 확정 업데이트 (BUG-1/2 fix)
                current_time = arrival_time

                # ③ 식사 시간대 조정 (범위를 벗어나면 이 슬롯을 건너뜀)
                if type_key == "식사":
                    target_range = LUNCH_START_RANGE if current_time.hour < 15 else DINNER_START_RANGE
                    if current_time.hour < target_range[0]:
                        current_time = current_time.replace(hour=target_range[0], minute=0, second=0)
                    elif current_time.hour >= target_range[1]:
                        continue

                selected['is_start_point'] = False
                day_places.append(self._make_place(
                    current_time.strftime("%H:%M"),
                    type_kor,
                    selected,
                    type_key
                ))
                visited_place_ids.add(selected['id'])
                last_place = selected
                last_place['type_key'] = type_key
                # [Phase 5-①] 관광지 방문 카운터 증가
                if type_key == "관광":
                    sights_visited_today += 1
            
            # Day 종료 지점 설정
            next_hotel = night_stay_hotels[d - 1] if d < duration and night_stay_hotels else None
            
            if last_place:
                prev_place_type_key = last_place.get('type_key', 'default')
                visit_duration_seconds = VISIT_TIMES.get(prev_place_type_key, VISIT_TIMES['default'])
                current_time = current_time + timedelta(seconds=visit_duration_seconds)
            
            if d == duration:
                final_stop = None
                if '항공' in user_data.get('transport', []) and airport_place:
                    final_stop = airport_place
                elif last_night_hotel:
                    final_stop = last_night_hotel
                
                if final_stop:
                    # [BUG-6 fix] 공유 dict 직접 변이 방지 → 복사본 사용
                    final_stop = {**final_stop, 'is_start_point': True}
                    day_places.append(self._make_place(
                        current_time.strftime("%H:%M"),
                        "출발 지점",
                        final_stop,
                        "숙소"
                    ))
            
            elif next_hotel:
                # [BUG-6 fix] 공유 dict 직접 변이 방지 → 복사본 사용
                _next_hotel_copy = {**next_hotel, 'is_start_point': False}
                day_places.append(self._make_place(
                    current_time.strftime("%H:%M"),
                    "숙소 복귀",
                    _next_hotel_copy,
                    "숙소"
                ))
                last_night_hotel = next_hotel
            
            days.append({"day": d, "places": day_places})
        
        return days
    
    def _calc_theme_score(
        self,
        days: List[Dict[str, Any]],
        user_data: Dict[str, Any],
        strategy_key: str
    ) -> int:
        """
        일정 내 장소 점수를 집계해 테마 일정의 종합 점수를 계산

        계산 방식:
            1. 각 day의 place에 저장된 raw_score 평균 → 기본 점수
            2. 사용자 취향/테마 일치 여부에 따라 보정 점수 추가
            3. 결과를 60~99 사이로 클램핑

        Args:
            days: _generate_for_theme()가 반환한 day별 일정
            user_data: 사용자 입력 데이터
            strategy_key: 테마 전략 키 ("✨ 핵심 코스" 등)

        Returns:
            최종 테마 점수 (int, 60~99)
        """
        # 1. 장소 raw_score 수집 (숙소·공항 제외)
        raw_scores = [
            place['raw_score']
            for day in days
            for place in day.get('places', [])
            if place.get('raw_score') and place.get('type_key') not in ('숙소',)
        ]

        if not raw_scores:
            return 85  # 데이터 없을 때 기본값

        base_score = sum(raw_scores) / len(raw_scores)

        # 2. 취향-테마 일치 보정
        styles = set(user_data.get('style', []))
        pace = user_data.get('pace', '보통')
        companion = user_data.get('companions', [])
        with_kids = user_data.get('with_kids', False)

        bonus = 0.0

        # 식도락 테마 × 맛집/휴양 취향
        if strategy_key == "🍽️ 식도락 & 힐링":
            if styles & {"맛집", "휴양"}:
                bonus += 5.0
            if pace == "여유" or "커플" in companion or with_kids:
                bonus += 3.0

        # 자연 테마 × 자연/관광/문화 취향
        elif strategy_key == "🌿 자연 & 관광":
            if styles & {"자연", "관광", "문화"}:
                bonus += 5.0

        # 액티브 테마 × 액티비티/쇼핑 취향
        elif strategy_key == "🔥 액티브 & 핫플":
            if styles & {"액티비티", "쇼핑"}:
                bonus += 5.0
            if pace == "빡빡" or "친구" in companion:
                bonus += 3.0

        # 핵심 코스는 항상 기본 보정
        elif strategy_key == "✨ 핵심 코스":
            bonus += 2.0

        # 3. 고예산 = 평점 높은 장소 위주 → 소폭 추가 보정
        if user_data.get('budget_level') == '고':
            bonus += 2.0

        final = base_score + bonus
        return max(60, min(99, int(final)))

    def _build_themes(self, user_data: Dict[str, Any], city: str = "") -> List[Dict[str, Any]]:
        """
        사용자 입력을 분석해 항상 4개 테마를 구성.

        - 조건에 맞는 테마는 사용자 맥락을 반영한 설명으로 우선 배치
        - 조건 미충족 테마도 사용자 스타일·동행·페이스를 녹인 설명으로 보완 배치
        - 항상 4개 반환 (SPEC-3)
        """
        styles     = set(user_data.get('style', []))
        pace       = user_data.get('pace', '보통')
        companions = user_data.get('companions', [])
        with_kids  = user_data.get('with_kids', False)
        city_label = city if city else "여행"

        # ── 사용자 맥락 요약 문구 ──────────────────────────────────────────
        _style_str = '·'.join(styles) if styles else '균형'
        _companion_str = (
            '아이와 함께' if with_kids
            else ('커플' if '커플' in companions
                  else ('가족' if '가족' in companions
                        else ('친구들과' if '친구' in companions else '')))
        )
        _pace_str = {'여유': '느긋하게', '빡빡': '알차게', '알차게': '알차게'}.get(pace, '')

        def _ctx(*parts):
            return ' '.join(p for p in parts if p)

        # ── 테마별 조건 매칭 여부 & 사용자 맥락 반영 desc ─────────────────
        foodie_matched = (
            bool(styles & {'맛집', '휴양'})
            or pace == '여유'
            or '커플' in companions
            or '가족' in companions
            or with_kids
        )
        nature_matched = bool(styles & {'자연', '관광', '문화'})
        active_matched = (
            bool(styles & {'액티비티', '쇼핑'})
            or pace == '빡빡'
            or '친구' in companions
        )

        def _core_desc() -> str:
            parts = []
            if styles:
                parts.append(f'{_style_str} 취향')
            if _companion_str:
                parts.append(_companion_str)
            if _pace_str:
                parts.append(_pace_str)
            if parts:
                return f"{'·'.join(parts)}에 최적화된 {city_label} 핵심 동선"
            return f'사용자 취향 기반의 가장 효율적인 {city_label} 동선'

        def _foodie_desc(matched: bool) -> str:
            if matched:
                parts = []
                if '맛집' in styles:
                    parts.append(f'{city_label} 현지 맛집')
                if '휴양' in styles or pace == '여유':
                    parts.append('카페·힐링')
                if with_kids or '가족' in companions:
                    parts.append('온 가족 식사')
                if '커플' in companions:
                    parts.append('분위기 있는 레스토랑')
                base = '·'.join(parts) if parts else '맛집과 여유로운 휴식'
                return f'{base} 중심의 일정'
            return _ctx(
                f'{city_label}의 대표 맛집과 카페를',
                _companion_str, _pace_str + ' 즐기는 코스'
            ) or '현지 맛집과 카페 중심의 여유로운 일정'

        def _nature_desc(matched: bool) -> str:
            if matched:
                parts = []
                if '자연' in styles:
                    parts.append(f'{city_label}의 자연 경관')
                if '관광' in styles:
                    parts.append('주요 명소')
                if '문화' in styles:
                    parts.append('역사·문화 탐방')
                base = '·'.join(parts) if parts else '명소와 자연 경관'
                return f'{base}을 중심으로 한 일정'
            return _ctx(
                f'{city_label}의 주요 명소와 자연 경관을',
                _companion_str, _pace_str + ' 둘러보는 코스'
            ) or f'{city_label}의 대표 명소와 자연을 둘러보는 일정'

        def _active_desc(matched: bool) -> str:
            if matched:
                parts = []
                if '액티비티' in styles:
                    parts.append('체험·액티비티')
                if '쇼핑' in styles:
                    parts.append('쇼핑')
                if pace == '빡빡' or '친구' in companions:
                    parts.append('인기 핫플')
                base = '·'.join(parts) if parts else '액티비티와 핫플'
                return f'{base}을 알차게 탐방하는 일정'
            return _ctx(
                f'{city_label}의 인기 핫플과 활동적인 장소를',
                _companion_str, _pace_str + ' 탐방하는 코스'
            ) or f'{city_label}의 인기 명소와 핫플을 활동적으로 탐방하는 일정'

        # ── 후보 테마 4개: 조건 일치(priority≤1) → 미충족(priority≥10) 순 정렬 ──
        CANDIDATE_THEMES = [
            {
                'name': f'✨ {city_label} 핵심 코스',
                'desc': _core_desc(),
                'strategy_key': '✨ 핵심 코스',
                'priority': 0,
            },
            {
                'name': '🍽️ 식도락 & 힐링',
                'desc': _foodie_desc(foodie_matched),
                'strategy_key': '🍽️ 식도락 & 힐링',
                'priority': 1 if foodie_matched else 10,
            },
            {
                'name': '🌿 자연 & 관광',
                'desc': _nature_desc(nature_matched),
                'strategy_key': '🌿 자연 & 관광',
                'priority': 1 if nature_matched else 11,
            },
            {
                'name': '🔥 액티브 & 핫플',
                'desc': _active_desc(active_matched),
                'strategy_key': '🔥 액티브 & 핫플',
                'priority': 1 if active_matched else 12,
            },
        ]
        CANDIDATE_THEMES.sort(key=lambda t: t['priority'])

        # strategy_key, priority는 외부에 노출하지 않음
        return [
            {'name': t['name'], 'desc': t['desc'], 'strategy_key': t['strategy_key']}
            for t in CANDIDATE_THEMES
        ]
    
    def _create_daily_schedule(
        self, 
        num_sights: int, 
        num_foods: int, 
        num_cafes: int
    ) -> List[tuple]:
        """하루 일정 스케줄 생성"""
        food_slots_base = [("12:00", "식사", "식사"), ("18:00", "식사", "식사")]
        cafe_slot_base = [("15:30", "카페/휴식", "카페")]
        sight_time_candidates = [
            ("10:30", "관광", "관광"), ("14:30", "관광", "관광"),
            ("16:30", "관광", "관광"), ("17:00", "관광", "관광"),
        ]
        
        selected_food_slots = random.sample(food_slots_base, min(num_foods, len(food_slots_base)))
        selected_cafe_slots = random.sample(cafe_slot_base, min(num_cafes, len(cafe_slot_base)))
        selected_sight_slots = random.sample(sight_time_candidates, min(num_sights, len(sight_time_candidates)))
        
        daily_schedule = []
        daily_schedule.extend(selected_sight_slots)
        daily_schedule.extend(selected_food_slots)
        daily_schedule.extend(selected_cafe_slots)
        daily_schedule.sort(key=lambda x: x[0])
        
        return daily_schedule
    
    def _make_place(
        self,
        time: str,
        type_name: str,
        db_row: Dict[str, Any],
        type_key: str
    ) -> Dict[str, Any]:
        """장소 정보를 일정 항목으로 변환"""
        is_start_point = db_row.get('is_start_point', False)

        # 장소 이름 번역
        place_name = backend.translate_place_name(db_row['name'])

        # 주소 가져오기 및 번역
        raw_address = db_row.get('address', '')
        place_address = backend.translate_address(raw_address) if raw_address else ''

        # [BUG-9 fix] dict 직접 접근 대신 .get() 사용하여 KeyError 방지
        _category = db_row.get('category', '')
        _address  = db_row.get('address', '')
        desc_content = f"{_category} | {_address}"
        if is_start_point and 'airport' in _category.lower():
            desc_content = f"✈️ 여행 시작/마무리 지점: {_address}"
        elif is_start_point and type_name == "숙소 출발":
            desc_content = f"🏡 전날 숙소에서 출발합니다."

        # ── 영업 상태 경고 판단 ───────────────────────────────────
        # days_since_verified: None(미확인) or 경과 일수(int)
        # 경고 수준 → 'none' | 'caution' | 'danger'
        days_since_verified = db_row.get('days_since_verified')  # None or int
        if days_since_verified is None:
            # 확인 이력 없는 장소는 고위험으로 처리
            staleness_warning = 'danger'
        elif days_since_verified >= PLACE_STALE_HIGH_RISK_DAYS:
            staleness_warning = 'danger'    # 1년 이상 미확인 → 🔴
        elif days_since_verified >= PLACE_STALE_WARNING_DAYS:
            staleness_warning = 'caution'   # 6개월 이상 미확인 → 🟡
        else:
            staleness_warning = 'none'      # 최근 확인 → 정상

        # 숙소·공항은 경고 표시 안 함 (시스템 시작/종료 지점)
        if type_key == '숙소' or db_row.get('category', '') == 'airport':
            staleness_warning = 'none'

        # ── 상세보기 URL 결정 ──────────────────────────────────────────
        # Kakao: img_url = place.map.kakao.com/... (상세 페이지) → 그대로 사용
        # Google: img_url = maps.googleapis.com/maps/api/place/photo?... (사진 URL)
        #         → 브라우저에서 직접 열면 400 에러. Google Maps 좌표 URL로 대체.
        raw_img_url = db_row.get('img_url', '') or ''
        if 'maps.googleapis.com/maps/api/place/photo' in raw_img_url:
            _lat = db_row.get('lat', 0.0)
            _lng = db_row.get('lng', 0.0)
            place_detail_url = f"https://www.google.com/maps/search/?api=1&query={_lat},{_lng}"
        else:
            # Kakao place_url 또는 기타 소스의 URL을 그대로 사용
            place_detail_url = raw_img_url

        return {
            "time":               time,
            "type":               type_name,
            "name":               place_name,
            "desc":               desc_content,
            "address":            place_address,
            "lat":                db_row['lat'],
            "lng":                db_row['lng'],
            "url":                place_detail_url,
            "raw_score":          db_row.get('score', 80),
            # Google photo URL은 img 소스로도 부적합할 수 있으므로 picsum 폴백 유지
            "img":                raw_img_url or "https://picsum.photos/400/300",
            "type_key":           type_key,
            "staleness_warning":  staleness_warning,  # 프론트엔드 경고 배지용
            "sub_category":       db_row.get('sub_category', ''),  # 세부 카테고리
        }


# 외부 인터페이스 함수
def generate_plans(data: Dict[str, Any], duration: int) -> List[Dict[str, Any]]:
    """
    여행 일정 생성 (외부 인터페이스)
    
    Args:
        data: 사용자 입력 데이터
        duration: 여행 기간 (일)
        
    Returns:
        테마별 일정 리스트
    """
    generator = ItineraryGenerator()
    return generator.generate(data, duration)
