"""
Phase 1 테스트 스크립트
---------------------
테스트 항목:
  1. constants.py 신규 상수 로드 검증
  2. hard_filter() — 예산별 평점 컷, 좌표 유효성
  3. extract_top_n() — CANDIDATE_POOL_RATIO 상수 사용 확인
  4. categorize_visits() — 관광/식당/카페 분류 정확도
  5. [선택] 실제 DB 연결 후 제주 장소 데이터로 통합 테스트

실행:
  cd "pick&go"
  python tests/test_phase1.py
"""

import sys
import os

# 프로젝트 루트를 sys.path에 추가
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── 색상 출력 헬퍼 ──────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✅ PASS{RESET}  {msg}")
def fail(msg): print(f"  {RED}❌ FAIL{RESET}  {msg}")
def info(msg): print(f"  {CYAN}ℹ  {msg}{RESET}")
def section(title): print(f"\n{YELLOW}{'─'*55}{RESET}\n{YELLOW}  {title}{RESET}\n{YELLOW}{'─'*55}{RESET}")

pass_count = 0
fail_count = 0

def check(condition, pass_msg, fail_msg=""):
    global pass_count, fail_count
    if condition:
        ok(pass_msg)
        pass_count += 1
    else:
        fail(fail_msg or pass_msg)
        fail_count += 1

# ════════════════════════════════════════════════════════════
#  Test 1: 상수 로드
# ════════════════════════════════════════════════════════════
section("Test 1: constants.py 신규 상수 로드")

try:
    from travel_logic.config.constants import (
        HOTEL_CATEGORIES, BUDGET_MIN_RATING, CANDIDATE_POOL_RATIO,
        HOTEL_ANCHOR_TIME_THRESHOLD, PACE_MAX_PLACES,
        COMPANION_STAY_MULTIPLIER, AIRPORT_COORDS
    )
    ok("모든 신규 상수 import 성공")
    pass_count += 1
except ImportError as e:
    fail(f"import 실패: {e}")
    fail_count += 1
    sys.exit(1)

check(CANDIDATE_POOL_RATIO == 5,
      f"CANDIDATE_POOL_RATIO == 5  (실제값: {CANDIDATE_POOL_RATIO})")

check(HOTEL_ANCHOR_TIME_THRESHOLD == 5400,
      f"HOTEL_ANCHOR_TIME_THRESHOLD == 5400초(90분)  (실제값: {HOTEL_ANCHOR_TIME_THRESHOLD})")

check(PACE_MAX_PLACES.get("여유") == 2,
      f"PACE_MAX_PLACES['여유'] == 2  (실제값: {PACE_MAX_PLACES.get('여유')})")

check(PACE_MAX_PLACES.get("보통") == (2, 3),
      f"PACE_MAX_PLACES['보통'] == (2,3)  (실제값: {PACE_MAX_PLACES.get('보통')})")

check(PACE_MAX_PLACES.get("알차게") == (3, 4),
      f"PACE_MAX_PLACES['알차게'] == (3,4)  (실제값: {PACE_MAX_PLACES.get('알차게')})")

check(BUDGET_MIN_RATING.get("저") == 2.0,
      f"BUDGET_MIN_RATING['저'] == 2.0  (실제값: {BUDGET_MIN_RATING.get('저')})")

check("제주" in AIRPORT_COORDS,
      "'제주' 공항 좌표 등록 확인")

check("호텔" in HOTEL_CATEGORIES,
      "'호텔' 이 HOTEL_CATEGORIES에 포함")

# ════════════════════════════════════════════════════════════
#  Test 2: hard_filter() — 평점 필터
# ════════════════════════════════════════════════════════════
section("Test 2: hard_filter() — 예산별 평점 컷")

from travel_logic.services.scoring_service import ScoringService

MOCK_PLACES = [
    {"id": "A", "name": "고평점 관광지",  "category": "관광", "lat": 33.5, "lng": 126.5, "rating": 4.5},
    {"id": "B", "name": "중평점 관광지",  "category": "관광", "lat": 33.5, "lng": 126.5, "rating": 3.2},
    {"id": "C", "name": "저평점 관광지",  "category": "관광", "lat": 33.5, "lng": 126.5, "rating": 1.5},
    {"id": "D", "name": "좌표 없는 장소", "category": "관광", "lat": 0.0,  "lng": 0.0,   "rating": 4.8},
    {"id": "E", "name": "평점 없는 장소", "category": "관광", "lat": 33.5, "lng": 126.5, "rating": 0},
    {"id": "F", "name": "고평점 식당",    "category": "restaurant", "lat": 33.5, "lng": 126.5, "rating": 2.5},
    {"id": "G", "name": "저평점 호텔",    "category": "hotel",      "lat": 33.5, "lng": 126.5, "rating": 1.8},
]

# 예산 "저" → 관광지 평점 2.0 미만 제거
result_low = ScoringService.hard_filter(MOCK_PLACES, {"budget_level": "저"})
ids_low = {p["id"] for p in result_low}
check("C" not in ids_low,   "예산=저: 평점 1.5 관광지 제거됨 (ID=C)")
check("D" not in ids_low,   "예산=저: 좌표 0.0 장소 제거됨 (ID=D)")
check("E" not in ids_low,   "예산=저: 평점 0 장소 제거됨 (ID=E)")
check("A" in ids_low,       "예산=저: 평점 4.5 관광지 통과 (ID=A)")
check("B" in ids_low,       "예산=저: 평점 3.2 관광지 통과 (ID=B)")

# 예산 "고" → 관광지 평점 4.0 미만 제거
result_high = ScoringService.hard_filter(MOCK_PLACES, {"budget_level": "고"})
ids_high = {p["id"] for p in result_high}
check("B" not in ids_high,  "예산=고: 평점 3.2 관광지 제거됨 (ID=B)")
check("A" in ids_high,      "예산=고: 평점 4.5 관광지 통과 (ID=A)")

# 식당·숙소는 조건 완화 (min_rating - 1.0)
check("F" in ids_high,      "예산=고: 평점 2.5 식당 완화 통과 (ID=F, 기준 3.0)")
check("G" in ids_high,      "예산=고: 평점 1.8 호텔 완화 통과 (ID=G, 기준 3.0)")

info(f"예산=저 통과: {len(result_low)}개 / 예산=고 통과: {len(result_high)}개")

# ════════════════════════════════════════════════════════════
#  Test 3: extract_top_n() — 상수 기반 슬라이싱
# ════════════════════════════════════════════════════════════
section("Test 3: extract_top_n() — CANDIDATE_POOL_RATIO 사용")

twenty_places = [
    {"id": str(i), "name": f"장소{i}", "category": "관광",
     "lat": 33.5, "lng": 126.5, "rating": 4.0, "score": 100 - i}
    for i in range(20)
]

# 4일 여행 → N = 4 × 5 = 20
top_4day = ScoringService.extract_top_n(twenty_places, num_days=4)
check(len(top_4day) == 20,  f"4일 → top_n=20  (실제: {len(top_4day)}개)")

# 2일 여행 → N = 2 × 5 = 10
top_2day = ScoringService.extract_top_n(twenty_places, num_days=2)
check(len(top_2day) == 10,  f"2일 → top_n=10  (실제: {len(top_2day)}개)")

# 장소가 N보다 적을 때 index 에러 없이 전부 반환
five_places = twenty_places[:5]
top_4day_small = ScoringService.extract_top_n(five_places, num_days=4)
check(len(top_4day_small) == 5,
      f"장소 5개, 4일 → 가능한 전부(5개) 반환  (실제: {len(top_4day_small)}개)")

# ════════════════════════════════════════════════════════════
#  Test 4: categorize_visits() — 관광/식당/카페 분류
# ════════════════════════════════════════════════════════════
section("Test 4: categorize_visits() — 카테고리 분류")

VISIT_PLACES = [
    {"id": "s1", "name": "성산일출봉", "category": "관광명소", "lat": 33.5, "lng": 126.9, "rating": 4.8},
    {"id": "s2", "name": "협재해변",   "category": "park",    "lat": 33.5, "lng": 126.2, "rating": 4.5},
    {"id": "f1", "name": "흑돼지집",   "category": "restaurant", "lat": 33.5, "lng": 126.5, "rating": 4.3},
    {"id": "f2", "name": "해물뚝배기", "category": "음식점",   "lat": 33.5, "lng": 126.5, "rating": 4.1},
    {"id": "c1", "name": "감성카페",   "category": "카페",     "lat": 33.5, "lng": 126.5, "rating": 4.4},
    {"id": "c2", "name": "스타벅스",   "category": "cafe",     "lat": 33.5, "lng": 126.5, "rating": 4.0},
]

sights, foods, cafes = ScoringService.categorize_visits(VISIT_PLACES, {})
sight_ids = {p["id"] for p in sights}
food_ids  = {p["id"] for p in foods}
cafe_ids  = {p["id"] for p in cafes}

check("s1" in sight_ids, "관광지 '성산일출봉' → sights 분류")
check("s2" in sight_ids, "park '협재해변' → sights 분류")
check("f1" in food_ids,  "restaurant '흑돼지집' → foods 분류")
check("f2" in food_ids,  "음식점 '해물뚝배기' → foods 분류")
check("c1" in cafe_ids,  "카페 '감성카페' → cafes 분류")
check("c2" in cafe_ids,  "cafe '스타벅스' → cafes 분류")
check(len(sights) + len(foods) + len(cafes) == len(VISIT_PLACES),
      f"전체 {len(VISIT_PLACES)}개 = sights({len(sights)}) + foods({len(foods)}) + cafes({len(cafes)})")

info(f"분류 결과 → 관광: {len(sights)}개 / 식당: {len(foods)}개 / 카페: {len(cafes)}개")

# ════════════════════════════════════════════════════════════
#  Test 5: 실제 DB 통합 테스트 (선택 — DB 연결 실패 시 스킵)
# ════════════════════════════════════════════════════════════
section("Test 5: 실제 DB 통합 테스트 (제주 데이터)")

try:
    import backend_postgres as backend
    raw = backend.get_places("제주")
    if not raw:
        info("제주 장소 데이터 없음 — DB 비어있거나 연결 실패, 스킵")
    else:
        info(f"DB에서 제주 장소 {len(raw)}개 로드")

        user_data_sample = {
            "budget_level": "중",
            "stroller": False,
            "barrier_free": False,
            "style": ["자연", "관광"],
            "with_kids": False,
        }

        # hard_filter
        filtered = ScoringService.hard_filter(raw, user_data_sample)
        check(len(filtered) <= len(raw),
              f"hard_filter 후 {len(raw)}개 → {len(filtered)}개 (줄어들거나 같음)")
        check(len(filtered) > 0,
              f"hard_filter 후 1개 이상 생존  (실제: {len(filtered)}개)")

        # 점수 계산
        for p in filtered:
            score, _ = ScoringService.calculate_score(p, user_data_sample)
            p['score'] = score
        filtered.sort(key=lambda x: x['score'], reverse=True)

        # extract_top_n (4일 여행 기준)
        top = ScoringService.extract_top_n(filtered, num_days=4)
        check(len(top) == min(20, len(filtered)),
              f"4일 기준 top_n={min(20, len(filtered))}개 추출  (실제: {len(top)}개)")

        # categorize_visits
        sights, foods, cafes = ScoringService.categorize_visits(top, user_data_sample)
        info(f"분류 결과 → 관광: {len(sights)}개 / 식당: {len(foods)}개 / 카페: {len(cafes)}개")
        check(len(sights) + len(foods) + len(cafes) == len(top),
              "분류 합계 = top_n 개수 일치 (중복/누락 없음)")

        # 상위 5개 장소 미리보기
        info("점수 상위 5개 장소:")
        for i, p in enumerate(top[:5], 1):
            print(f"     {i}. [{p.get('score',0):3d}점] {p.get('name','?')}"
                  f"  ({p.get('category','?')})  평점:{p.get('rating','?')}")

except Exception as e:
    info(f"DB 통합 테스트 스킵: {e}")

# ════════════════════════════════════════════════════════════
#  최종 결과
# ════════════════════════════════════════════════════════════
total = pass_count + fail_count
print(f"\n{'═'*55}")
print(f"  결과: {GREEN}{pass_count} PASS{RESET} / {RED}{fail_count} FAIL{RESET}  (총 {total}개 검사)")
print(f"{'═'*55}\n")

if fail_count > 0:
    sys.exit(1)
