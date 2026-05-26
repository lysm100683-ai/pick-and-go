"""
Phase 1 실행 결과 데모
======================
실제 DB 연결 없이 제주도 장소 샘플 데이터로
Phase 1 (필터링 & 점수화) 각 단계별 결과를 출력합니다.

실행:
  cd "pick&go"
  $env:PYTHONIOENCODING="utf-8"
  .venv\Scripts\python.exe tests/demo_phase1_result.py
"""

import sys, os, importlib.util

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── 상수/서비스 직접 로드 (DB 의존성 없이) ──────────────────────
def _load(alias, path):
    spec = importlib.util.spec_from_file_location(alias, os.path.join(ROOT, path))
    mod  = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod

C  = _load("travel_logic.config.constants", "travel_logic/config/constants.py")
S  = _load("travel_logic.config.settings",  "travel_logic/config/settings.py")
SS = _load("travel_logic.services.scoring_service", "travel_logic/services/scoring_service.py")
ScoringService = SS.ScoringService

# ── 색상 ──────────────────────────────────────────────────────────
R="\033[91m"; G="\033[92m"; Y="\033[93m"; B="\033[94m"; C_="\033[96m"; M="\033[95m"; W="\033[97m"; DIM="\033[2m"; RST="\033[0m"; BOLD="\033[1m"

def hdr(title, sub=""):
    bar = "=" * 64
    print(f"\n{B}{bar}{RST}")
    print(f"{BOLD}{W}  {title}{RST}")
    if sub: print(f"{DIM}  {sub}{RST}")
    print(f"{B}{bar}{RST}")

def sub_hdr(title):
    print(f"\n{Y}  ── {title} ──{RST}")

def row(label, val, color=W):
    print(f"    {DIM}{label:<16}{RST}{color}{val}{RST}")

# ════════════════════════════════════════════════════════════════
#  제주도 샘플 데이터 (30개, 다양한 평점·카테고리·좌표 포함)
# ════════════════════════════════════════════════════════════════
JEJU_PLACES = [
    # 관광지
    {"id":"s01","name":"성산일출봉","category":"관광명소","lat":33.4580,"lng":126.9425,"rating":4.8,"img_url":"http://img1"},
    {"id":"s02","name":"한라산 국립공원","category":"관광명소","lat":33.3617,"lng":126.5292,"rating":4.9,"img_url":"http://img2"},
    {"id":"s03","name":"만장굴","category":"관광명소","lat":33.5280,"lng":126.7713,"rating":4.5,"img_url":"http://img3"},
    {"id":"s04","name":"천지연 폭포","category":"관광명소","lat":33.2460,"lng":126.5497,"rating":4.6,"img_url":"http://img4"},
    {"id":"s05","name":"협재 해수욕장","category":"park","lat":33.3941,"lng":126.2394,"rating":4.7,"img_url":"http://img5"},
    {"id":"s06","name":"제주 민속촌","category":"관광명소","lat":33.3195,"lng":126.8155,"rating":4.2,"img_url":""},
    {"id":"s07","name":"폐업된 관광지X","category":"관광명소","lat":33.4000,"lng":126.5000,"rating":1.2,"img_url":""},  # 탈락 예정
    {"id":"s08","name":"좌표없는명소Y","category":"관광명소","lat":0.0,"lng":0.0,"rating":4.5,"img_url":""},            # 탈락 예정
    {"id":"s09","name":"우도","category":"관광명소","lat":33.5025,"lng":126.9521,"rating":4.7,"img_url":"http://img9"},
    {"id":"s10","name":"비자림","category":"park","lat":33.5001,"lng":126.8112,"rating":4.4,"img_url":"http://img10"},
    # 식당
    {"id":"f01","name":"흑돼지거리 식당A","category":"restaurant","lat":33.4996,"lng":126.5312,"rating":4.3,"img_url":"http://f1"},
    {"id":"f02","name":"칠성식당","category":"음식점","lat":33.5000,"lng":126.5200,"rating":4.1,"img_url":"http://f2"},
    {"id":"f03","name":"해녀촌","category":"restaurant","lat":33.4600,"lng":126.9300,"rating":4.5,"img_url":"http://f3"},
    {"id":"f04","name":"폐업식당 Z","category":"restaurant","lat":33.4900,"lng":126.5100,"rating":0.8,"img_url":""},   # 탈락 예정
    {"id":"f05","name":"고기국수 본점","category":"음식점","lat":33.4890,"lng":126.5020,"rating":4.6,"img_url":"http://f5"},
    {"id":"f06","name":"자연식 뷔페","category":"restaurant","lat":33.5100,"lng":126.5500,"rating":3.2,"img_url":"http://f6"},
    {"id":"f07","name":"한치 물회","category":"음식점","lat":33.2500,"lng":126.5600,"rating":4.0,"img_url":"http://f7"},
    # 카페
    {"id":"c01","name":"바다뷰 카페","category":"카페","lat":33.5200,"lng":126.5400,"rating":4.5,"img_url":"http://c1"},
    {"id":"c02","name":"감귤 카페","category":"카페","lat":33.4700,"lng":126.3200,"rating":4.3,"img_url":"http://c2"},
    {"id":"c03","name":"스타벅스 제주점","category":"cafe","lat":33.4900,"lng":126.5300,"rating":4.0,"img_url":"http://c3"},
    {"id":"c04","name":"제주 커피 로스터리","category":"cafe","lat":33.5050,"lng":126.5100,"rating":4.6,"img_url":"http://c4"},
    {"id":"c05","name":"저평점 카페 W","category":"카페","lat":33.5000,"lng":126.5000,"rating":1.9,"img_url":""},     # 탈락 예정
    # 숙소
    {"id":"h01","name":"제주신라호텔","category":"호텔","lat":33.2476,"lng":126.5646,"rating":4.8,"img_url":"http://h1"},
    {"id":"h02","name":"롯데호텔 제주","category":"호텔","lat":33.2500,"lng":126.5550,"rating":4.6,"img_url":"http://h2"},
    {"id":"h03","name":"감귤 펜션","category":"펜션","lat":33.4000,"lng":126.3000,"rating":4.2,"img_url":"http://h3"},
    {"id":"h04","name":"저평점 모텔 Q","category":"모텔","lat":33.4900,"lng":126.5000,"rating":2.5,"img_url":""},    # star_rating 기준 탈락
    {"id":"h05","name":"아난티 리조트","category":"리조트","lat":33.2800,"lng":126.4200,"rating":4.7,"img_url":"http://h5"},
    # 평점 없는 장소 (좌표는 있음)
    {"id":"x01","name":"평점없는 장소A","category":"관광명소","lat":33.5000,"lng":126.5000,"rating":None,"img_url":""},  # 탈락
    # 이름 없는 장소
    {"id":"x02","name":"","category":"관광명소","lat":33.5000,"lng":126.5000,"rating":4.5,"img_url":""},              # 탈락
]

# ════════════════════════════════════════════════════════════════
#  사용자 조건 (시뮬레이션)
# ════════════════════════════════════════════════════════════════
USER_DATA = {
    "dest_city":    "제주",
    "budget_level": "중",        # 중간 예산 → 평점 3.0 미만 관광지 제거
    "star_rating":  4.0,          # 숙소 최소 별점 4.0
    "style":        ["자연", "맛집"],
    "with_kids":    False,
    "stroller":     False,
    "barrier_free": False,
    "photo_spot":   True,
    "pace":         "알차게",
    "transport":    ["항공"],
    "companions":   ["커플"],
    "_duration":    4,            # 3박 4일
}

NUM_DAYS = USER_DATA["_duration"]

# ════════════════════════════════════════════════════════════════
#  STEP 0: 원본 데이터 현황
# ════════════════════════════════════════════════════════════════
hdr("STEP 0 | 원본 데이터 현황", f"사용자: 예산={USER_DATA['budget_level']}, 별점≥{USER_DATA['star_rating']}, {NUM_DAYS}일 여행, 스타일={USER_DATA['style']}")
print(f"\n  총 {W}{BOLD}{len(JEJU_PLACES)}개{RST} 장소 로드됨\n")

cat_counts = {}
for p in JEJU_PLACES:
    cat_counts[p["category"]] = cat_counts.get(p["category"], 0) + 1

for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
    bar = "█" * cnt
    print(f"    {DIM}{cat:<14}{RST}  {C_}{bar}{RST} {cnt}개")

# ════════════════════════════════════════════════════════════════
#  STEP 1: 이름 없는 장소 + 중복 제거
# ════════════════════════════════════════════════════════════════
hdr("STEP 1 | 이름 없는 장소 제거 + 중복 제거")

unique_places = []
seen_names = set()
removed_no_name = []

for p in JEJU_PLACES:
    if not p.get("name"):
        removed_no_name.append(p)
        continue
    clean_name = "".join(filter(str.isalnum, p["name"])).lower()
    if clean_name not in seen_names:
        seen_names.add(clean_name)
        unique_places.append(p)

print(f"\n  {R}제거됨 ({len(removed_no_name)}개):{RST}")
for p in removed_no_name:
    print(f"    {DIM}[id={p['id']}]{RST} 이름 없는 장소")

print(f"\n  {G}잔존: {len(unique_places)}개{RST}  ({len(JEJU_PLACES)} → {len(unique_places)})")

# ════════════════════════════════════════════════════════════════
#  STEP 2: hard_filter() — 예산별 평점 컷 + 좌표 유효성
# ════════════════════════════════════════════════════════════════
hdr("STEP 2 | hard_filter() — 예산별 평점 컷 & 좌표 유효성",
    f"예산='{USER_DATA['budget_level']}' → 관광지 최소 평점 {C.BUDGET_MIN_RATING[USER_DATA['budget_level']]}점")

hard_filtered = ScoringService.hard_filter(unique_places, USER_DATA)

# 제거된 장소 찾기
surviving_ids = {p["id"] for p in hard_filtered}
removed_hard = [p for p in unique_places if p["id"] not in surviving_ids]

sub_hdr("제거된 장소 (hard_filter 탈락)")
if removed_hard:
    for p in removed_hard:
        rat = p.get("rating") or 0
        lat = p.get("lat", 0)
        reason = "좌표 0.0" if (lat == 0.0) else f"평점 {rat} 미달"
        print(f"    {R}[탈락]{RST} {p['name']:<20} {DIM}(카테고리:{p['category']}, 평점:{rat}){RST}  → {Y}{reason}{RST}")

sub_hdr("통과한 장소 (hard_filter 생존)")
for p in hard_filtered:
    cat = p["category"]
    rat = p.get("rating", 0)
    print(f"    {G}[통과]{RST} {p['name']:<24} {DIM}(카테고리:{cat}, 평점:{rat}){RST}")

print(f"\n  결과: {len(unique_places)}개 → {G}{BOLD}{len(hard_filtered)}개 생존{RST}  ({R}{len(removed_hard)}개 제거{RST})")

# ════════════════════════════════════════════════════════════════
#  STEP 3: 숙소 별도 풀 분리
# ════════════════════════════════════════════════════════════════
hdr("STEP 3 | 숙소 별도 풀 분리",
    f"HOTEL_CATEGORIES 상수 기반 + star_rating ≥ {USER_DATA['star_rating']}")

min_hotel_rating = float(USER_DATA.get("star_rating", 3))
hotels = [
    p for p in hard_filtered
    if (
        any(kw in str(p.get("category", "")) for kw in C.HOTEL_CATEGORIES)
        and float(p.get("rating", 0)) >= min_hotel_rating
    )
]
hotel_ids = {p["id"] for p in hotels}
non_hotels = [p for p in hard_filtered if p["id"] not in hotel_ids]

sub_hdr(f"hotels 풀 ({len(hotels)}개) — Phase 4 앵커링 후보")
for p in hotels:
    print(f"    {M}[숙소]{RST} {p['name']:<24} 평점:{p['rating']}  {DIM}({p['category']}){RST}")

sub_hdr(f"방문 후보 풀 ({len(non_hotels)}개) — 관광/식당/카페")
for p in non_hotels:
    print(f"    {B}[방문]{RST} {p['name']:<24} 평점:{p.get('rating','?')}  {DIM}({p['category']}){RST}")

# ════════════════════════════════════════════════════════════════
#  STEP 4: 점수 계산 & 정렬
# ════════════════════════════════════════════════════════════════
hdr("STEP 4 | 취향 점수 계산 & 내림차순 정렬",
    f"스타일={USER_DATA['style']}, photo_spot={USER_DATA['photo_spot']}")

scored = []
for p in non_hotels:
    score, tags = ScoringService.calculate_score(p, USER_DATA)
    p = dict(p)
    p["score"] = score
    p["matched_tags"] = tags
    scored.append(p)

scored.sort(key=lambda x: x["score"], reverse=True)

print(f"\n  {'순위':<4} {'점수':>5}  {'장소명':<24} {'카테고리':<14} {'평점':>5}")
print(f"  {'-'*62}")
for i, p in enumerate(scored, 1):
    score_color = G if p["score"] >= 70 else Y if p["score"] >= 50 else DIM
    bar = "▓" * (p["score"] // 10)
    print(f"  {BOLD}{i:<4}{RST} {score_color}{p['score']:>5}{RST}점  {W}{p['name']:<24}{RST} {DIM}{p['category']:<14}{RST} ★{p.get('rating','?')}   {score_color}{bar}{RST}")

# ════════════════════════════════════════════════════════════════
#  STEP 5: extract_top_n()
# ════════════════════════════════════════════════════════════════
hdr("STEP 5 | extract_top_n() — 상위 N개 추출",
    f"{NUM_DAYS}일 여행 × CANDIDATE_POOL_RATIO({C.CANDIDATE_POOL_RATIO}) = {NUM_DAYS * C.CANDIDATE_POOL_RATIO}개 추출")

top_n = ScoringService.extract_top_n(scored, NUM_DAYS)
excluded = scored[len(top_n):]

print(f"\n  {G}추출된 top_{NUM_DAYS * C.CANDIDATE_POOL_RATIO}개:{RST}")
for i, p in enumerate(top_n, 1):
    print(f"    {G}{i:>2}.{RST} [{p['score']:>3}점] {p['name']:<24}  {DIM}{p['category']}{RST}")

if excluded:
    print(f"\n  {DIM}탈락 (top_N 초과, {len(excluded)}개):{RST}")
    for p in excluded:
        print(f"    {DIM}     [{p['score']:>3}점] {p['name']}{RST}")

# ════════════════════════════════════════════════════════════════
#  STEP 6: categorize_visits()
# ════════════════════════════════════════════════════════════════
hdr("STEP 6 | categorize_visits() — 관광/식당/카페 분류")

sights, foods, cafes = ScoringService.categorize_visits(top_n, USER_DATA)

sub_hdr(f"관광지 (sights) — {len(sights)}개")
for p in sights:
    print(f"    {C_}[관광]{RST} [{p['score']:>3}점] {p['name']:<24}  {DIM}{p['category']}{RST}")

sub_hdr(f"식당 (foods) — {len(foods)}개")
for p in foods:
    print(f"    {Y}[식당]{RST} [{p['score']:>3}점] {p['name']:<24}  {DIM}{p['category']}{RST}")

sub_hdr(f"카페 (cafes) — {len(cafes)}개")
for p in cafes:
    print(f"    {M}[카페]{RST} [{p['score']:>3}점] {p['name']:<24}  {DIM}{p['category']}{RST}")

total_categorized = len(sights) + len(foods) + len(cafes)
print(f"\n  분류 합계: 관광{len(sights)} + 식당{len(foods)} + 카페{len(cafes)} = {G}{BOLD}{total_categorized}개{RST}  (top_N={len(top_n)}개 전부 분류)")

# ════════════════════════════════════════════════════════════════
#  최종 요약
# ════════════════════════════════════════════════════════════════
hdr("Phase 1 최종 요약")
print(f"""
  {DIM}원본 데이터      {RST}{W}{BOLD}{len(JEJU_PLACES):>3}개{RST}
  {DIM}이름 제거 후     {RST}{W}{len(unique_places):>3}개{RST}
  {DIM}hard_filter 후  {RST}{G}{len(hard_filtered):>3}개{RST}   ({R}-{len(unique_places)-len(hard_filtered)}개{RST} 제거)
  {DIM}숙소 별도 풀     {RST}{M}{len(hotels):>3}개{RST}   (Phase 4 앵커링 후보)
  {DIM}방문 후보 풀     {RST}{B}{len(non_hotels):>3}개{RST}
  {DIM}점수 계산 & 정렬 {RST}{B}{len(scored):>3}개{RST}
  {DIM}extract_top_n   {RST}{G}{len(top_n):>3}개{RST}   ({NUM_DAYS}일 × {C.CANDIDATE_POOL_RATIO} = {NUM_DAYS*C.CANDIDATE_POOL_RATIO})
  {DIM}  → 관광         {RST}{C_}{len(sights):>3}개{RST}
  {DIM}  → 식당         {RST}{Y}{len(foods):>3}개{RST}
  {DIM}  → 카페         {RST}{M}{len(cafes):>3}개{RST}

  {G}Phase 1 완료 → Phase 2 (K-Means 클러스터링) 입력 준비{RST}
""")
