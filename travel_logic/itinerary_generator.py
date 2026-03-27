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
from .domain import check_is_domestic
from .services import ScoringService, DistanceService, OptimizationService, DBService
from .strategies import CoreStrategy, FoodieStrategy, NatureStrategy, ActiveStrategy


class ItineraryGenerator:
    """여행 일정 생성기"""
    
    def __init__(self):
        self.scoring_service = ScoringService()
        self.distance_service = DistanceService()
        self.optimization_service = OptimizationService(self.distance_service)
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
        
        # 데이터 로드 및 전처리
        places = self._load_and_preprocess_places(city, user_data)
        if not places:
            return []
        
        # 장소 타입별 분류
        sights, foods, cafes, hotels, airport_place = self._categorize_places(
            places, user_data
        )
        
        # 테마별 일정 생성
        final_plans = []
        is_korea = check_is_domestic(city)
        
        # 사용자 입력 기반으로 테마 동적 결정
        themes = self._build_themes(user_data, city)
        
        for theme in themes:
            strategy = self.strategies.get(theme['strategy_key'], self.strategies["✨ 핵심 코스"])
            
            days = self._generate_for_theme(
                theme, strategy, duration, sights, foods, cafes, 
                hotels, airport_place, user_data, is_korea
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
        """장소 데이터 로드 및 전처리"""
        places = backend.get_places(city)
        
        # 유효한 장소만 필터링
        valid_places = [
            p for p in places
            if p.get('lat') and p.get('lng')
            and float(p.get('lat', 0)) != 0.0
            and float(p.get('lng', 0)) != 0.0
            and float(p.get('rating', 0)) > 0
            and p.get('name')
        ]
        
        # 정렬 및 중복 제거
        valid_places.sort(
            key=lambda x: (x.get('img_url') != "", float(x.get('rating', 0))),
            reverse=True
        )
        
        unique_places = []
        seen_names = set()
        
        for p in valid_places:
            clean_name = ''.join(filter(str.isalnum, p['name'])).lower()
            if clean_name not in seen_names:
                seen_names.add(clean_name)
                unique_places.append(p)
        
        # 점수 계산
        scored_places = []
        for p in unique_places:
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
        """장소를 타입별로 분류"""
        # 공항 설정
        airport_place = None
        if '항공' in user_data.get('transport', []):
            airport_place = {
                "id": "airport_start",
                "source": "system",
                "name": f"{user_data['dest_city']} 공항",
                "city": user_data['dest_city'],
                "category": "airport",
                "lat": 33.5113,
                "lng": 126.493,
                "address": "공항 출발/도착",
                "rating": 5.0,
                "img_url": "",
                "desc": "여행 시작/마무리 지점"
            }
        
        # 숙소 필터링
        min_hotel_rating = user_data.get('star_rating', 3)
        hotels = [
            p for p in places
            if ("숙소" in str(p['category']) or "호텔" in str(p['category'])
                or "펜션" in str(p['category']) or "리조트" in str(p['category'])
                or "lodging" in str(p['category']).lower())
            and float(p.get('rating', 0)) >= min_hotel_rating
        ]
        
        non_lodging_places = [p for p in places if p not in hotels]
        
        # 관광지 필터링
        sights = [
            p for p in non_lodging_places
            if "관광" in str(p['category']) or "명소" in str(p['category'])
            or "공원" in str(p['category']) or "박물관" in str(p['category'])
            or "tourist_attraction" in str(p['category']).lower()
            or "park" in str(p['category']).lower()
        ]
        
        # 식당 필터링
        foods = [
            p for p in non_lodging_places
            if ("식당" in str(p['category']) or "음식점" in str(p['category'])
                or "restaurant" in str(p['category']).lower()
                or "food" in str(p['category']).lower())
            and "카페" not in str(p['category'])
            and "cafe" not in str(p['category']).lower()
        ]
        
        # 카페 필터링
        cafes = [
            p for p in non_lodging_places
            if "카페" in str(p['category']) or "cafe" in str(p['category']).lower()
        ]
        
        # 쇼핑 장소 추가
        if "쇼핑" in user_data.get('style', []):
            shopping_places = [
                p for p in non_lodging_places
                if "쇼핑" in str(p['category']) or "mall" in str(p['category']).lower()
                or "market" in str(p['category']).lower()
            ]
            sights.extend(shopping_places)
        
        # 예비 후보
        if not sights:
            sights = non_lodging_places[:20]
        if not foods:
            foods = non_lodging_places[:15]
        if not cafes:
            cafes = non_lodging_places[:5]
        if not hotels:
            hotels = [airport_place] if airport_place else []
        
        return sights, foods, cafes, hotels, airport_place
    
    def _generate_for_theme(
        self,
        theme: Dict[str, str],
        strategy: Any,
        duration: int,
        all_sights: List[Dict],
        all_foods: List[Dict],
        all_cafes: List[Dict],
        all_hotels: List[Dict],
        airport_place: Optional[Dict],
        user_data: Dict[str, Any],
        is_korea: bool
    ) -> List[Dict[str, Any]]:
        """테마별 일정 생성"""
        # 사용자 선호도에 따라 장소 필터링
        all_sights = self.scoring_service.filter_places(all_sights, user_data)
        all_foods = self.scoring_service.filter_places(all_foods, user_data)
        all_cafes = self.scoring_service.filter_places(all_cafes, user_data)
        
        # 영업 중인 장소만 필터링
        all_sights = [p for p in all_sights if backend.check_place_status(p['lat'], p['lng'], p['name'])]
        all_foods = [p for p in all_foods if backend.check_place_status(p['lat'], p['lng'], p['name'])]
        all_cafes = [p for p in all_cafes if backend.check_place_status(p['lat'], p['lng'], p['name'])]
        
        # 점수 기준으로 정렬
        all_sights.sort(key=lambda x: x.get('score', 0), reverse=True)
        all_foods.sort(key=lambda x: x.get('score', 0), reverse=True)
        all_cafes.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        # 장소 풀 생성 및 셔플
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
        
        # 교통수단 결정
        is_driving = '렌트카' in user_data.get('local_transport', []) or '자차' in user_data.get('local_transport', [])
        travel_mode = 'driving' if is_driving else 'transit'
        
        # 전략 가중치
        strategy_weights = strategy.get_weights()
        
        # 숙소 유동화
        num_req_hotels = min(user_data.get('num_hotels', 1), len(all_hotels))
        if num_req_hotels == 0:
            num_req_hotels = 1
        
        hotel_candidates = random.sample(all_hotels, num_req_hotels) if all_hotels else []
        night_stay_hotels = [
            hotel_candidates[i % num_req_hotels]
            for i in range(duration - 1)
        ] if hotel_candidates else []
        
        last_night_hotel = hotel_candidates[0] if hotel_candidates else None
        
        # 일차별 일정 생성
        days = []
        visited_place_ids = set()
        
        for d in range(1, duration + 1):
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
                    current_day_start_point['is_start_point'] = True
                    day_places.append(self._make_place(
                        current_time.strftime("%H:%M"),
                        "도착 지점",
                        current_day_start_point,
                        "숙소"
                    ))
                    last_place = current_day_start_point
                    last_place['type_key'] = '숙소'
            
            elif d > 1 and last_night_hotel:
                current_day_start_point = last_night_hotel
                current_day_start_point['is_start_point'] = True
                day_places.append(self._make_place(
                    current_time.strftime("%H:%M"),
                    "숙소 출발",
                    current_day_start_point,
                    "숙소"
                ))
                last_place = current_day_start_point
                last_place['type_key'] = '숙소'
            
            # 장소 방문 루프
            for _, type_kor, type_key in daily_schedule:
                if type_key == "식사":
                    candidates_pool = pool_foods
                elif type_key == "카페":
                    candidates_pool = pool_cafes
                elif type_key == "관광":
                    candidates_pool = pool_sights
                else:
                    continue
                
                candidates = [p for p in candidates_pool if p['id'] not in visited_place_ids]
                if not candidates:
                    continue
                
                # ① 장소 먼저 선택 (최적화 — 내부에서 Top-10 bulk 이동 시간 조회 및 캐시 저장)
                selected = self.optimization_service.select_next_place(
                    candidates, last_place, strategy_weights,
                    is_korea, travel_mode, type_key
                )

                if not selected:
                    continue

                # ② 선택된 장소까지 이동 시간으로 current_time 업데이트
                #    (캐시에 이미 저장되어 있어 추가 API 호출 없음)
                if last_place and last_place.get('lat', 0.0) != 0.0 and last_place.get('lng', 0.0) != 0.0:
                    prev_place_type_key = last_place.get('type_key', 'default')
                    visit_duration_seconds = VISIT_TIMES.get(prev_place_type_key, VISIT_TIMES['default'])

                    travel_duration_seconds = self.distance_service.get_travel_time(
                        last_place['lat'], last_place['lng'],
                        selected['lat'], selected['lng'],
                        is_korea, travel_mode
                    )

                    if travel_duration_seconds == 999999:
                        travel_duration_seconds = 30 * 60

                    current_time = current_time + timedelta(seconds=visit_duration_seconds + travel_duration_seconds)

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
                    final_stop['is_start_point'] = True
                    day_places.append(self._make_place(
                        current_time.strftime("%H:%M"),
                        "출발 지점",
                        final_stop,
                        "숙소"
                    ))
            
            elif next_hotel:
                next_hotel['is_start_point'] = False
                day_places.append(self._make_place(
                    current_time.strftime("%H:%M"),
                    "숙소 복귀",
                    next_hotel,
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
        사용자 입력을 분석하여 의미 있는 테마를 동적으로 결정
        
        Args:
            user_data: 사용자 입력 데이터
            city: 여행 도시 이름 (핵심 코스 테마명에 사용)
            
        Returns:
            [{name, desc, strategy_key}, ...] 형태, 2~4개 보장
        """
        styles = set(user_data.get('style', []))
        pace = user_data.get('pace', '보통')
        companions = user_data.get('companions', [])
        with_kids = user_data.get('with_kids', False)
        city_label = city if city else "여행"
        
        # 후보 테마 정의 (strategy_key는 self.strategies의 키와 일치)
        CANDIDATE_THEMES = [
            {
                "name": f"✨ {city_label} 핵심 코스",
                "desc": "사용자 취향 기반의 가장 효율적인 동선",
                "strategy_key": "✨ 핵심 코스",
                "always": True,   # 항상 포함
            },
            {
                "name": "🍽️ 식도락 & 힐링",
                "desc": "맛집 방문과 여유로운 휴식 중심의 일정",
                "strategy_key": "🍽️ 식도락 & 힐링",
                "always": False,
                # 맛집·휴양 스타일, 여유 페이스, 또는 커플/가족 동반일 때 포함
                "condition": lambda: (
                    bool(styles & {"맛집", "휴양"})
                    or pace == "여유"
                    or "커플" in companions
                    or "가족" in companions
                    or with_kids
                ),
            },
            {
                "name": "🌿 자연 & 관광",
                "desc": "주요 명소와 자연 경관을 둘러보는 일정",
                "strategy_key": "🌿 자연 & 관광",
                "always": False,
                # 자연·관광·문화 스타일 선택 시 포함
                "condition": lambda: bool(styles & {"자연", "관광", "문화"}),
            },
            {
                "name": "🔥 액티브 & 핫플",
                "desc": "활동적인 장소와 인기 명소 탐방",
                "strategy_key": "🔥 액티브 & 핫플",
                "always": False,
                # 액티비티·쇼핑 스타일, 또는 빡빡 페이스일 때 포함
                "condition": lambda: (
                    bool(styles & {"액티비티", "쇼핑"})
                    or pace == "빡빡"
                    or "친구" in companions
                ),
            },
        ]
        
        selected = []
        for t in CANDIDATE_THEMES:
            if t.get('always') or t.get('condition', lambda: False)():
                # strategy_key, always, condition 키는 외부에 노출하지 않음
                selected.append({
                    "name": t["name"],
                    "desc": t["desc"],
                    "strategy_key": t["strategy_key"],
                })
        
        # 최소 2개 보장: 조건 해당 테마가 1개(핵심 코스만)이면
        # 조건 미충족 테마 중 첫 번째를 추가
        if len(selected) < 2:
            fallback_keys = ["🍽️ 식도락 & 힐링", "🌿 자연 & 관광", "🔥 액티브 & 핫플"]
            selected_keys = {t["strategy_key"] for t in selected}
            for t in CANDIDATE_THEMES:
                if t["strategy_key"] not in selected_keys:
                    selected.append({
                        "name": t["name"],
                        "desc": t["desc"],
                        "strategy_key": t["strategy_key"],
                    })
                    if len(selected) >= 2:
                        break
        
        return selected
    
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
        
        desc_content = f"{db_row['category']} | {db_row['address']}"
        if is_start_point and 'airport' in db_row.get('category', '').lower():
            desc_content = f"✈️ 여행 시작/마무리 지점: {db_row['address']}"
        elif is_start_point and type_name == "숙소 출발":
            desc_content = f"🏡 전날 숙소에서 출발합니다."
        
        return {
            "time": time,
            "type": type_name,
            "name": place_name,
            "desc": desc_content,
            "address": place_address,
            "lat": db_row['lat'],
            "lng": db_row['lng'],
            "url": db_row['img_url'],
            "raw_score": db_row.get('score', 80),
            "img": db_row['img_url'] or "https://source.unsplash.com/400x300/?travel",
            "type_key": type_key
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
