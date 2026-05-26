# services/scoring_service.py
"""
장소 점수 계산 및 필터링 서비스

[점수 설계 이력]
  v1: rating × 10 (max 50) + 스타일 보너스
  v2: rating × 15 (max 75) + 리뷰수 구간 보너스 + 최신성 보정
  v3: 베이지안 평균(rating + review_count 복합) × 15  ← 현재
      + 별점 분포 보너스(5★~1★ 긍정/부정 비율 기반 -5~+5)
      + 최신성 보정 + 스타일 매칭
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
from ..config.settings import DEFAULT_MIN_RATING
from ..config.constants import (
    BUDGET_MIN_RATING,
    CANDIDATE_POOL_RATIO,
    HOTEL_CATEGORIES,             # hard_filter() is_hotel 판별에 사용
    REVIEW_COUNT_BONUS,           # 레거시 (하위 호환용)
    BAYESIAN_C,
    BAYESIAN_GLOBAL_AVG,
    BAYESIAN_SCORE_MULTIPLIER,
    RATING_DIST_POSITIVE_TIERS,
    RATING_DIST_NEGATIVE_TIERS,
    DATA_FRESHNESS_PENALTY,
    SUB_CATEGORY_MAP,
    CATEGORY_KEYWORD_MAP,
    ADULT_ONLY_KEYWORDS,
)


class ScoringService:
    """장소 점수 계산 및 필터링 담당"""

    # ─────────────────────────────────────────────────────────
    #  Phase 1: 필터링 메서드
    # ─────────────────────────────────────────────────────────

    # 조건 완화 시 예산 수준별 최소 평점 (한 단계 낮춤)
    RELAXED_MIN_RATING = {'저': 1.0, '중': 2.0, '고': 3.0}

    @staticmethod
    def hard_filter(places: List[Dict[str, Any]], user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        [Phase 1] 필수 조건 미충족 장소 즉시 제거

        조건 1 — 좌표 유효성: lat/lng 가 0.0 이거나 없는 장소 제거
        조건 2 — 예산 수준별 최소 평점 필터
                  숙소·식당은 1점 완화, Kakao(rating=0)는 API 미제공으로 면제
                  _relax_filter=True 시 평점 기준을 한 단계 완화
        조건 3 — 배리어프리: DB 태그 없어 현재 pass (TourAPI 연동 후 활성화)
        """
        budget = user_data.get('budget_level', '중')
        is_relaxed = user_data.get('_relax_filter', False)

        if is_relaxed:
            # 조건 완화 모드: 한 단계 낮은 평점 기준 적용
            min_rating = ScoringService.RELAXED_MIN_RATING.get(budget, 1.5)
        else:
            min_rating = BUDGET_MIN_RATING.get(budget, DEFAULT_MIN_RATING)

        result = []
        for p in places:
            # 조건 1: 좌표 유효성
            try:
                lat = float(p.get('lat', 0) or 0)
                lng = float(p.get('lng', 0) or 0)
            except (ValueError, TypeError):
                continue
            if lat == 0.0 or lng == 0.0:
                continue

            # 조건 2: 평점 필터
            try:
                rating = float(p.get('rating', 0) or 0)
            except (ValueError, TypeError):
                rating = 0.0

            category = str(p.get('category', '')).lower()
            # HOTEL_CATEGORIES 상수 재사용 → itinerary_generator와 동일 기준
            # (하드코딩 목록보다 완전함: 게스트하우스, 모텔, guesthouse 등 포함)
            is_hotel = any(kw in category for kw in HOTEL_CATEGORIES)
            is_food  = any(kw in category for kw in ('식당', '음식점', 'restaurant', 'food'))

            # Kakao 장소: 플랫폼 정책상 평점 미제공(0.0) → 필터 면제
            source = str(p.get('source', '')).lower()
            is_kakao_no_rating = (source == 'kakao' and rating == 0.0)

            effective_min = min_rating if not (is_hotel or is_food) else max(1.0, min_rating - 1.0)
            if not is_kakao_no_rating and rating < effective_min:
                continue

            # 조건 3: 배리어프리 (현재 미작동)
            if user_data.get('stroller', False) or user_data.get('barrier_free', False):
                pass  # TODO: TourAPI 연동 후 활성화

            result.append(p)

        return result

    @staticmethod
    def extract_top_n(places: List[Dict[str, Any]], num_days: int) -> List[Dict[str, Any]]:
        """
        [Phase 1] 상위 N개 방문 후보 장소 추출
        N = num_days × CANDIDATE_POOL_RATIO (= 5)
        """
        n = num_days * CANDIDATE_POOL_RATIO
        return places[:n]

    @staticmethod
    def categorize_visits(
        places: List[Dict[str, Any]],
        user_data: Dict[str, Any]
    ) -> Tuple[List, List, List]:
        """
        [Phase 1] 방문 장소를 관광·식당·카페로 분류

        분류 우선순위:
          1. sub_category → SUB_CATEGORY_MAP 직접 매핑
          2. category + name 키워드 → CATEGORY_KEYWORD_MAP fallback
        """
        sights, foods, cafes = [], [], []

        for p in places:
            sub_cat  = str(p.get('sub_category', '') or '').strip()
            category = str(p.get('category', '') or '').lower()
            name     = str(p.get('name', '') or '').lower()

            # 1순위: sub_category 직접 매핑
            if sub_cat and sub_cat in SUB_CATEGORY_MAP:
                target = SUB_CATEGORY_MAP[sub_cat]
                if target == "cafes":
                    cafes.append(p)
                elif target == "foods":
                    foods.append(p)
                else:
                    sights.append(p)
                continue

            # 2순위: 키워드 fallback
            combined = category + " " + name
            if any(kw in combined for kw in CATEGORY_KEYWORD_MAP["cafes"]):
                cafes.append(p)
            elif any(kw in combined for kw in CATEGORY_KEYWORD_MAP["foods"]):
                foods.append(p)
            else:
                sights.append(p)

        # 쇼핑 스타일 선택 시 쇼핑 장소도 sights 포함
        if '쇼핑' in user_data.get('style', []):
            shopping = [
                p for p in places
                if any(kw in str(p.get('category', '')).lower()
                       for kw in ('쇼핑', 'mall', 'market', 'shopping', '시장', '백화점', '편집샵'))
                and p not in sights
            ]
            sights.extend(shopping)

        return sights, foods, cafes

    # ─────────────────────────────────────────────────────────
    #  점수 계산 핵심 메서드 (v3 베이지안 + 별점 분포)
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def _bayesian_base_score(rating: float, review_count: int) -> float:
        """
        베이지안 평균 기반 기본 점수 계산 (최대 75점)

        단순 rating × 15 대신, 리뷰 수를 신뢰도로 반영한 공식:
          bayesian_rating = (C × global_avg + n × rating) / (C + n)
          score           = bayesian_rating × BAYESIAN_SCORE_MULTIPLIER

        리뷰가 적으면 → 글로벌 평균(3.5)으로 할인 (과신 방지)
        리뷰가 많으면 → 실제 평점에 수렴 (신뢰도 반영)

        예시:
          평점 5.0, 리뷰  2개 → score ≈ 54.8점  (리뷰 부족으로 할인)
          평점 5.0, 리뷰200개 → score ≈ 70.5점  (신뢰도 높아 반영)
          평점 4.0, 리뷰500개 → score ≈ 59.3점
        """
        # [M-2] Bayesian 개선: 리뷰 수 0인 장소도 rating 값을 소폭 반영
        # 기존: n=0이면 항상 global_avg(3.5)로 수렴 → 별점 5.0 신규 맛집 = 별점 1.0 불량 가게
        # 수정: 정규화 상수 C를 10으로 낮춰 실제 rating에 더 빠르게 수렴하도록 조정
        c = max(10, BAYESIAN_C - max(0, review_count) // 5)  # 리뷰 많을수록 C 축소
        g = BAYESIAN_GLOBAL_AVG
        n = max(0, review_count)
        bayesian = (c * g + n * rating) / (c + n)
        return bayesian * BAYESIAN_SCORE_MULTIPLIER

    @staticmethod
    def _distribution_bonus(place: Dict[str, Any]) -> int:
        """
        별점 분포(5★~1★ 누적 샘플)를 기반으로 보너스/패널티 계산

        [수집 방식]
        Google Place Details API는 상위 5개 리뷰만 반환하므로,
        fetch_google() 수집 시 해당 리뷰들의 별점을 DB에 누적 저장.
        수집을 거듭할수록 샘플이 쌓여 경향 파악 신뢰도가 개선됨.

        [계산 방식]
          total_sample    = rating_5star + ... + rating_1star
          positive_ratio  = (5★ + 4★) / total_sample
          negative_ratio  = (1★ + 2★) / total_sample

        분포 데이터 없으면(모두 0) → 0점 (영향 없음)

        [반환 범위] -5 ~ +5점
          부정 패널티를 긍정 보너스보다 먼저 체크 (안전 우선)
        """
        r5 = int(place.get('rating_5star', 0) or 0)
        r4 = int(place.get('rating_4star', 0) or 0)
        r3 = int(place.get('rating_3star', 0) or 0)
        r2 = int(place.get('rating_2star', 0) or 0)
        r1 = int(place.get('rating_1star', 0) or 0)

        total = r5 + r4 + r3 + r2 + r1
        if total == 0:
            return 0  # 분포 데이터 없으면 점수에 영향 없음

        positive_ratio = (r5 + r4) / total
        negative_ratio = (r1 + r2) / total

        # ① 부정 비율 먼저 체크 (패널티 우선)
        for threshold, penalty in RATING_DIST_NEGATIVE_TIERS:
            if negative_ratio >= threshold:
                return penalty

        # ② 긍정 비율 보너스 체크
        for threshold, bonus in RATING_DIST_POSITIVE_TIERS:
            if positive_ratio >= threshold:
                return bonus

        return 0

    @staticmethod
    def calculate_score(place: Dict[str, Any], user_data: Dict[str, Any]) -> tuple:
        """
        사용자 조건을 반영한 장소 점수 복합 계산 (v3)

        [점수 구성]
          1. 베이지안 기본 점수   최대 75점  rating + review_count 통합 공식
          2. 별점 분포 보너스    -5 ~ +5점  5★~1★ 긍정/부정 비율
          3. 데이터 최신성 보정  -5 ~ 0점   updated_at 경과일
          4. 스타일 매칭 보너스  +25점      취향 일치 시
          5. 포토스팟 보너스     +15점      photo_spot 선택 시
          6. 가족 친화 보너스    +20점      아이 동반 시
          7. 성인 전용 패널티    -50점      아이 동반 + 성인 전용 장소

        최종 점수: min(100, max(0, int(base + bonus)))
        """
        # 1. 베이지안 기본 점수
        rating       = float(place.get('rating', BAYESIAN_GLOBAL_AVG) or BAYESIAN_GLOBAL_AVG)
        review_count = int(place.get('review_count', 0) or 0)
        base  = ScoringService._bayesian_base_score(rating, review_count)
        bonus = 0

        # 2. 별점 분포 보너스 (-5 ~ +5)
        bonus += ScoringService._distribution_bonus(place)

        # 3. 데이터 최신성 보정 (-5 ~ 0)
        updated_at_str = place.get('updated_at')
        if updated_at_str:
            try:
                updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                days_since = (now - updated_at).days
                for threshold_days, freshness_penalty in DATA_FRESHNESS_PENALTY:
                    if days_since >= threshold_days:
                        bonus += freshness_penalty
                        break
            except (ValueError, TypeError):
                pass

        # 4. 스타일 매칭 보너스 (+25)
        style_keywords = {
            "휴양":     ["beach", "park", "spa", "resort", "pool", "휴양", "해변", "공원"],
            "관광":     ["museum", "tour", "historic", "attraction", "관광", "명소", "박물관", "유적"],
            "맛집":     ["restaurant", "food", "dining", "cuisine", "식당", "음식점", "맛집"],
            "쇼핑":     ["shopping", "mall", "market", "store", "쇼핑", "시장", "백화점"],
            "액티비티": ["activity", "sport", "adventure", "outdoor", "액티비티", "스포츠", "체험"],
            "자연":     ["nature", "mountain", "forest", "lake", "river", "자연", "산", "숲", "호수"],
            "문화":     ["culture", "art", "gallery", "theater", "문화", "예술", "갤러리", "극장"],
            "자연풍경": ["nature", "mountain", "beach", "scenic", "자연", "풍경", "경관"],
            "역사/문화": ["historic", "museum", "heritage", "유적", "박물관", "문화재", "역사"],
            "카페투어": ["cafe", "coffee", "카페", "커피", "브런치", "디저트"],
            "호캉스":   ["hotel", "resort", "pool", "luxury", "호텔", "리조트", "수영장"],
        }

        combined = (
            str(place.get('category', '')).lower() + " " +
            str(place.get('name', '')).lower() + " " +
            str(place.get('sub_category', '') or '').lower()
        )

        # [M-3] 스타일 보너스 cap: 최대 +30점 (스타일 3개 이상 매칭 시 무한 누적 방지)
        style_bonus = 0
        for style in user_data.get('style', []):
            if style in style_keywords:
                for kw in style_keywords[style]:
                    if kw.lower() in combined:
                        style_bonus += 25
                        break
        bonus += min(style_bonus, 30)

        # 5. 포토스팟 보너스 (+15)
        if user_data.get('photo_spot', False):
            for kw in ["view", "scenic", "landmark", "tower", "전망", "뷰", "포토", "타워"]:
                if kw in combined:
                    bonus += 15
                    break

        # 6 & 7. 아이 동반 반영
        if user_data.get('with_kids', False):
            for kw in ["park", "zoo", "aquarium", "family", "kid", "공원", "동물원", "수족관", "가족"]:
                if kw in combined:
                    bonus += 20
                    break
            for kw in ADULT_ONLY_KEYWORDS:
                if kw in combined:
                    bonus -= 50
                    break

        return min(100, max(0, int(base + bonus))), user_data.get('style', [])

    @staticmethod
    def filter_places(places: List[Dict[str, Any]], user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """사용자 선호도에 따른 소프트 필터"""
        filtered = []
        for place in places:
            min_rating = DEFAULT_MIN_RATING
            if user_data.get('budget_level') == '고':
                min_rating = 4.0
            elif user_data.get('budget_level') == '중':
                min_rating = 3.5

            if float(place.get('rating', 0)) < min_rating:
                continue

            if user_data.get('with_kids', False):
                combined = (str(place.get('category', '')).lower() + " " +
                            str(place.get('name', '')).lower())
                if any(kw in combined for kw in ADULT_ONLY_KEYWORDS):
                    continue

            filtered.append(place)
        return filtered
