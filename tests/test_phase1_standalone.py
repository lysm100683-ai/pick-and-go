"""
Phase 1 standalone test (DB dependency-free)
"""

import sys, os, importlib.util

# Windows cp949 콘솔에서 한글/특수문자 출력 보장
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── 색상 헬퍼 ──────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

pass_count = 0
fail_count = 0

def ok(msg):
    global pass_count
    print(f"  {GREEN}PASS{RESET}  {msg}")
    pass_count += 1

def fail(msg):
    global fail_count
    print(f"  {RED}FAIL{RESET}  {msg}")
    fail_count += 1

def info(msg):
    print(f"  {CYAN}INFO{RESET}  {msg}")

def section(title):
    print(f"\n{YELLOW}{'='*60}{RESET}")
    print(f"{YELLOW}{BOLD}  {title}{RESET}")
    print(f"{YELLOW}{'='*60}{RESET}")

def check(condition, pass_msg, fail_msg=""):
    if condition:
        ok(pass_msg)
    else:
        fail(fail_msg or pass_msg)


# ════════════════════════════════════════════════════════════════
#  모듈 직접 로드 (travel_logic.__init__ 우회)
# ════════════════════════════════════════════════════════════════
def _load_module(alias, filepath):
    """상대 import 없이 파일 직접 로드"""
    spec = importlib.util.spec_from_file_location(alias, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod

try:
    c = _load_module("travel_logic.config.constants",
                     os.path.join(ROOT, "travel_logic/config/constants.py"))
    s = _load_module("travel_logic.config.settings",
                     os.path.join(ROOT, "travel_logic/config/settings.py"))
    ss_mod = _load_module("travel_logic.services.scoring_service",
                          os.path.join(ROOT, "travel_logic/services/scoring_service.py"))
    ScoringService = ss_mod.ScoringService
    print(f"\n{BOLD}constants.py / scoring_service.py 로드 성공{RESET}\n")
except Exception as e:
    print(f"{RED}모듈 로드 실패: {e}{RESET}")
    sys.exit(1)


# ════════════════════════════════════════════════════════════════
#  Test 1: constants.py 신규 상수
# ════════════════════════════════════════════════════════════════
section("Test 1 | constants.py — 5-Phase 신규 상수 검증")

check(c.CANDIDATE_POOL_RATIO == 5,
      f"CANDIDATE_POOL_RATIO == 5  (실제: {c.CANDIDATE_POOL_RATIO})")

check(c.HOTEL_ANCHOR_TIME_THRESHOLD == 5400,
      f"HOTEL_ANCHOR_TIME_THRESHOLD == 5400s(90분)  (실제: {c.HOTEL_ANCHOR_TIME_THRESHOLD})")

check(c.PACE_MAX_PLACES.get("여유") == 2,
      f"PACE_MAX_PLACES['여유'] == 2  (실제: {c.PACE_MAX_PLACES.get('여유')})")

check(c.PACE_MAX_PLACES.get("보통") == (2, 3),
      f"PACE_MAX_PLACES['보통'] == (2,3)  (실제: {c.PACE_MAX_PLACES.get('보통')})")

check(c.PACE_MAX_PLACES.get("알차게") == (3, 4),
      f"PACE_MAX_PLACES['알차게'] == (3,4)  (실제: {c.PACE_MAX_PLACES.get('알차게')})")

check(c.BUDGET_MIN_RATING.get("저") == 2.0,
      f"BUDGET_MIN_RATING['저'] == 2.0  (실제: {c.BUDGET_MIN_RATING.get('저')})")
check(c.BUDGET_MIN_RATING.get("중") == 3.0,
      f"BUDGET_MIN_RATING['중'] == 3.0  (실제: {c.BUDGET_MIN_RATING.get('중')})")
check(c.BUDGET_MIN_RATING.get("고") == 4.0,
      f"BUDGET_MIN_RATING['고'] == 4.0  (실제: {c.BUDGET_MIN_RATING.get('고')})")

check("제주" in c.AIRPORT_COORDS,
      f"AIRPORT_COORDS 에 '제주' 등록됨  (lat={c.AIRPORT_COORDS['제주']['lat']})")
check("서울" in c.AIRPORT_COORDS,
      f"AIRPORT_COORDS 에 '서울' 등록됨  (name={c.AIRPORT_COORDS['서울']['name']})")
check("부산" in c.AIRPORT_COORDS,
      f"AIRPORT_COORDS 에 '부산' 등록됨  (name={c.AIRPORT_COORDS['부산']['name']})")

check("호텔" in c.HOTEL_CATEGORIES,   "HOTEL_CATEGORIES 에 '호텔' 포함")
check("펜션" in c.HOTEL_CATEGORIES,   "HOTEL_CATEGORIES 에 '펜션' 포함")
check("lodging" in c.HOTEL_CATEGORIES,"HOTEL_CATEGORIES 에 'lodging' 포함")


# ════════════════════════════════════════════════════════════════
#  Test 2: hard_filter() — 예산별 평점 컷 + 좌표 유효성
# ════════════════════════════════════════════════════════════════
section("Test 2 | hard_filter() — 예산별 평점 컷 & 좌표 유효성")

MOCK = [
    {"id":"A","name":"고평점관광지",  "category":"관광",      "lat":33.5,"lng":126.5,"rating":4.5},
    {"id":"B","name":"중평점관광지",  "category":"관광",      "lat":33.5,"lng":126.5,"rating":3.2},
    {"id":"C","name":"저평점관광지",  "category":"관광",      "lat":33.5,"lng":126.5,"rating":1.5},
    {"id":"D","name":"좌표없는장소",  "category":"관광",      "lat":0.0, "lng":0.0,  "rating":4.8},
    {"id":"E","name":"평점없는장소",  "category":"관광",      "lat":33.5,"lng":126.5,"rating":0},
    {"id":"F","name":"고평점식당",    "category":"restaurant","lat":33.5,"lng":126.5,"rating":2.5},
    {"id":"G","name":"저평점호텔",    "category":"hotel",     "lat":33.5,"lng":126.5,"rating":1.8},
]

# 예산 = 저 (min=2.0)
r_low  = ScoringService.hard_filter(MOCK, {"budget_level":"저"})
il = {p["id"] for p in r_low}
check("C" not in il, "예산=저: 평점 1.5 관광지 제거  (ID=C)")
check("D" not in il, "예산=저: 좌표 0.0 장소 제거    (ID=D)")
check("E" not in il, "예산=저: 평점=0  장소 제거     (ID=E)")
check("A"     in il, "예산=저: 평점 4.5 관광지 통과  (ID=A)")
check("B"     in il, "예산=저: 평점 3.2 관광지 통과  (ID=B)")
info(f"예산=저  통과 {len(r_low)}/{len(MOCK)}개  → {sorted(il)}")

# 예산 = 고 (min=4.0)
r_high = ScoringService.hard_filter(MOCK, {"budget_level":"고"})
ih = {p["id"] for p in r_high}
check("B" not in ih, "예산=고: 평점 3.2 관광지 제거  (ID=B)")
check("C" not in ih, "예산=고: 평점 1.5 관광지 제거  (ID=C)")
check("A"     in ih, "예산=고: 평점 4.5 관광지 통과  (ID=A)")
# 예산=고: min=4.0, 식당/호텔 완화 적용 시 effective_min = max(1.0, 4.0-1.0) = 3.0
# F(식당 2.5) < 3.0 → 탈락,  G(호텔 1.8) < 3.0 → 탈락 이 정상 동작
check("F" not in ih, "예산=고: 식당  2.5 탈락 (완화기준 3.0에도 미달)  (ID=F)")
check("G" not in ih, "예산=고: 호텔  1.8 탈락 (완화기준 3.0에도 미달)  (ID=G)")
info(f"예산=고  통과 {len(r_high)}/{len(MOCK)}개  → {sorted(ih)}")


# ════════════════════════════════════════════════════════════════
#  Test 3: extract_top_n() — CANDIDATE_POOL_RATIO 상수 사용
# ════════════════════════════════════════════════════════════════
section("Test 3 | extract_top_n() — 여행일수 × CANDIDATE_POOL_RATIO")

TWENTY = [
    {"id":str(i),"name":f"장소{i}","category":"관광",
     "lat":33.5,"lng":126.5,"rating":4.0,"score":100-i}
    for i in range(20)
]

t4 = ScoringService.extract_top_n(TWENTY, num_days=4)
check(len(t4) == 20, f"4일 여행 → top_n=20  (실제: {len(t4)}개)")

t2 = ScoringService.extract_top_n(TWENTY, num_days=2)
check(len(t2) == 10, f"2일 여행 → top_n=10  (실제: {len(t2)}개)")

t1 = ScoringService.extract_top_n(TWENTY, num_days=1)
check(len(t1) == 5,  f"1일 여행 → top_n=5   (실제: {len(t1)}개)")

small = TWENTY[:5]
ts = ScoringService.extract_top_n(small, num_days=4)
check(len(ts) == 5,  f"장소 5개 + 4일 → 전부(5개) 반환  (실제: {len(ts)}개, 에러 없음)")

info(f"CANDIDATE_POOL_RATIO 현재값: {c.CANDIDATE_POOL_RATIO}  "
     f"(하루 평균 {c.CANDIDATE_POOL_RATIO}곳 가정)")


# ════════════════════════════════════════════════════════════════
#  Test 4: categorize_visits() — 관광/식당/카페 분류
# ════════════════════════════════════════════════════════════════
section("Test 4 | categorize_visits() — 카테고리 분류 정확도")

VISIT = [
    {"id":"s1","name":"성산일출봉","category":"관광명소",   "lat":33.5,"lng":126.9,"rating":4.8},
    {"id":"s2","name":"협재해변",  "category":"park",       "lat":33.5,"lng":126.2,"rating":4.5},
    {"id":"f1","name":"흑돼지집",  "category":"restaurant", "lat":33.5,"lng":126.5,"rating":4.3},
    {"id":"f2","name":"해물뚝배기","category":"음식점",     "lat":33.5,"lng":126.5,"rating":4.1},
    {"id":"c1","name":"감성카페",  "category":"카페",       "lat":33.5,"lng":126.5,"rating":4.4},
    {"id":"c2","name":"스타벅스",  "category":"cafe",       "lat":33.5,"lng":126.5,"rating":4.0},
]

sights, foods, cafes = ScoringService.categorize_visits(VISIT, {})
s_ids = {p["id"] for p in sights}
f_ids = {p["id"] for p in foods}
c_ids = {p["id"] for p in cafes}

check("s1" in s_ids, "관광명소 '성산일출봉' → sights")
check("s2" in s_ids, "park     '협재해변'   → sights")
check("f1" in f_ids, "restaurant '흑돼지집' → foods")
check("f2" in f_ids, "음식점 '해물뚝배기'   → foods")
check("c1" in c_ids, "카페 '감성카페'       → cafes")
check("c2" in c_ids, "cafe '스타벅스'       → cafes")
check(
    len(sights)+len(foods)+len(cafes) == len(VISIT),
    f"총 {len(VISIT)}개 = 관광{len(sights)} + 식당{len(foods)} + 카페{len(cafes)}  (누락 없음)"
)
info(f"분류 결과 → 관광:{len(sights)}개 | 식당:{len(foods)}개 | 카페:{len(cafes)}개")


# ════════════════════════════════════════════════════════════════
#  Test 5: 공항 좌표 동적 조회 시뮬레이션
# ════════════════════════════════════════════════════════════════
section("Test 5 | AIRPORT_COORDS — 공항 하드코딩 제거 검증")

CITIES_TO_CHECK = ["제주", "서울", "부산", "대구", "광주", "청주", "여수", "양양"]
for city_name in CITIES_TO_CHECK:
    coords = c.AIRPORT_COORDS.get(city_name)
    check(
        coords is not None and coords.get("lat") and coords.get("lng"),
        f"'{city_name}' → {coords['name'] if coords else 'NOT FOUND'}  "
        f"(lat={coords['lat'] if coords else '-'}, lng={coords['lng'] if coords else '-'})"
    )

# 미등록 도시 → None
unknown = c.AIRPORT_COORDS.get("오사카")
check(unknown is None,
      "'오사카' → None 반환 (미등록 도시 안전 처리 OK)")


# ════════════════════════════════════════════════════════════════
#  Test 6: HOTEL_CATEGORIES 기반 숙소 분리 시뮬레이션
# ════════════════════════════════════════════════════════════════
section("Test 6 | HOTEL_CATEGORIES — 숙소 별도 풀 분리 시뮬레이션")

MIXED_PLACES = [
    {"id":"h1","name":"제주신라호텔",   "category":"호텔",       "rating":4.8,"lat":33.2,"lng":126.5},
    {"id":"h2","name":"감귤펜션",       "category":"펜션",       "rating":4.2,"lat":33.3,"lng":126.3},
    {"id":"h3","name":"아난티리조트",   "category":"리조트",     "rating":4.6,"lat":33.4,"lng":126.6},
    {"id":"v1","name":"성산일출봉",     "category":"관광명소",   "rating":4.7,"lat":33.5,"lng":126.9},
    {"id":"v2","name":"흑돼지식당",     "category":"restaurant", "rating":4.1,"lat":33.5,"lng":126.5},
    {"id":"v3","name":"감성카페바다",   "category":"카페",       "rating":4.3,"lat":33.5,"lng":126.4},
]

star_rating = 4.0

hotels = [
    p for p in MIXED_PLACES
    if (
        any(kw in str(p.get("category", "")) for kw in c.HOTEL_CATEGORIES)
        and float(p.get("rating", 0)) >= star_rating
    )
]
hotel_ids = {p["id"] for p in hotels}
non_hotels = [p for p in MIXED_PLACES if p["id"] not in hotel_ids]

check("h1" in hotel_ids, f"'제주신라호텔'(호텔,4.8) → hotels 풀  (star_rating={star_rating})")
# 감귤펜션 rating=4.2 >= star_rating=4.0 → hotels 풀에 포함 (탈락이 아님)
check("h2" in hotel_ids, f"'감귤펜션'(펜션,4.2) → hotels 풀 포함  (4.2 >= {star_rating})")
check("h3" in hotel_ids, f"'아난티리조트'(리조트,4.6) → hotels 풀")
check("v1" in {p["id"] for p in non_hotels}, "'성산일출봉' → non_hotels (방문 후보)")
check("v2" in {p["id"] for p in non_hotels}, "'흑돼지식당' → non_hotels (방문 후보)")
check("v3" in {p["id"] for p in non_hotels}, "'감성카페바다' → non_hotels (방문 후보)")

info(f"hotels 풀: {len(hotels)}개  |  방문 후보: {len(non_hotels)}개")
info(f"extract_top_n 적용 전 방문 후보: {[p['name'] for p in non_hotels]}")


# ════════════════════════════════════════════════════════════════
#  최종 결과
# ════════════════════════════════════════════════════════════════
total = pass_count + fail_count
print(f"\n{'='*60}")
if fail_count == 0:
    print(f"  {GREEN}{BOLD}ALL {pass_count} TESTS PASSED{RESET}")
else:
    print(f"  {GREEN}{pass_count} PASS{RESET}  /  {RED}{fail_count} FAIL{RESET}  (총 {total}개)")
print(f"{'='*60}\n")

sys.exit(0 if fail_count == 0 else 1)
