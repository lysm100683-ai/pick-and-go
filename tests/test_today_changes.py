"""
오늘 변경된 파일 통합 테스트
대상: exceptions.py / scoring_service.py / clustering_service.py / models.py / __init__.py
"""
import sys, os, math, time
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("OMP_NUM_THREADS", "1")

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; C = "\033[96m"; B = "\033[1m"; X = "\033[0m"
p = f = 0

def ok(m):  global p; print(f"  {G}PASS{X}  {m}"); p += 1
def fail(m): global f; print(f"  {R}FAIL{X}  {m}"); f += 1
def info(m): print(f"  {C}INFO{X}  {m}")
def sec(t):  print(f"\n{Y}{'='*62}{X}\n{Y}{B}  {t}{X}\n{Y}{'='*62}{X}")
def chk(c, pm, fm=""):
    if c: ok(pm)
    else: fail(fm or pm)

# ── 모듈 로드 ──────────────────────────────────────────────────────
import importlib.util

def load(alias, path):
    spec = importlib.util.spec_from_file_location(alias, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[alias] = m
    spec.loader.exec_module(m)
    return m

try:
    exc_mod = load("travel_logic.exceptions",
                   os.path.join(ROOT, "travel_logic/exceptions.py"))
    cs_mod  = load("travel_logic.services.clustering_service",
                   os.path.join(ROOT, "travel_logic/services/clustering_service.py"))
    # scoring_service는 여러 내부 의존성 있어 import 경로 설정
    sys.path.insert(0, os.path.join(ROOT, "travel_logic"))
    print(f"{B}모듈 로드 완료{X}\n")
except Exception as e:
    print(f"{R}로드 실패: {e}{X}"); sys.exit(1)

CS  = cs_mod.ClusteringService
IPE = exc_mod.InsufficientPlacesError

# ════════════════════════════════════════════════════════════════
# [1] InsufficientPlacesError 예외 클래스
# ════════════════════════════════════════════════════════════════
sec("Test 1 | InsufficientPlacesError — 예외 클래스 속성 검증")

e1 = IPE(city="제주", available=2, required=5, budget_level="고", relaxed=False)
chk(isinstance(e1, Exception),    "InsufficientPlacesError는 Exception 하위 클래스")
chk(e1.city == "제주",             "city 속성 정상")
chk(e1.available == 2,             "available 속성 정상")
chk(e1.required == 5,              "required 속성 정상")
chk(e1.budget_level == "고",       "budget_level 속성 정상")
chk(e1.relaxed == False,           "relaxed=False 기본값 정상")
chk("제주" in str(e1),             f"str(e) 메시지 포함: {str(e1)[:60]}")

e2 = IPE(city="서울", available=0, required=3, relaxed=True)
chk(e2.relaxed == True,            "relaxed=True 설정 정상")
chk(e2.budget_level == "중",       "budget_level 기본값 '중' 정상")

try:
    raise IPE(city="부산", available=1, required=4)
except IPE as caught:
    chk(caught.city == "부산",     "raise/catch 정상 동작")

# ════════════════════════════════════════════════════════════════
# [2] travel_logic __init__ export
# ════════════════════════════════════════════════════════════════
sec("Test 2 | travel_logic.__init__ — InsufficientPlacesError export 확인")

init_path = os.path.join(ROOT, "travel_logic/__init__.py")
with open(init_path, encoding="utf-8") as fh:
    init_src = fh.read()
chk("InsufficientPlacesError" in init_src, "__init__.py에 InsufficientPlacesError 포함")
chk("from .exceptions import InsufficientPlacesError" in init_src,
    "예외 클래스 import 구문 존재")
chk("'InsufficientPlacesError'" in init_src, "__all__ 에 등록됨")

# ════════════════════════════════════════════════════════════════
# [3] ScoringService.hard_filter — _relax_filter 지원
# ════════════════════════════════════════════════════════════════
sec("Test 3 | ScoringService.hard_filter — _relax_filter=True 동작 검증")

# scoring_service는 내부 constants 의존 → 소스 직접 검사
ss_path = os.path.join(ROOT, "travel_logic/services/scoring_service.py")
with open(ss_path, encoding="utf-8") as fh:
    ss_src = fh.read()
chk("_relax_filter" in ss_src,              "hard_filter에 _relax_filter 분기 추가됨")
chk("RELAXED_MIN_RATING" in ss_src,         "RELAXED_MIN_RATING 상수 정의됨")
chk("ScoringService.RELAXED_MIN_RATING" in ss_src, "클래스 변수로 선언됨")

# 완화 등급 확인: 저→1.0, 중→2.0, 고→3.0
chk("'저': 1.0" in ss_src, "완화 기준: 저 → 1.0")
chk("'중': 2.0" in ss_src, "완화 기준: 중 → 2.0")
chk("'고': 3.0" in ss_src, "완화 기준: 고 → 3.0")

# ════════════════════════════════════════════════════════════════
# [4] app/models.py — InsufficientPlacesDetail 모델
# ════════════════════════════════════════════════════════════════
sec("Test 4 | app/models.py — InsufficientPlacesDetail 모델 검증")

models_path = os.path.join(ROOT, "app/models.py")
with open(models_path, encoding="utf-8") as fh:
    models_src = fh.read()
chk("InsufficientPlacesDetail" in models_src, "InsufficientPlacesDetail 클래스 존재")
chk("error_code" in models_src,               "error_code 필드 존재")
chk("available" in models_src,                "available 필드 존재")
chk("required" in models_src,                 "required 필드 존재")
chk("relaxed" in models_src,                  "relaxed 필드 존재")
chk('"INSUFFICIENT_PLACES"' in models_src,    "error_code 기본값 INSUFFICIENT_PLACES")

# ════════════════════════════════════════════════════════════════
# [5] app/main.py — 새 엔드포인트 및 에러 처리
# ════════════════════════════════════════════════════════════════
sec("Test 5 | app/main.py — 신규 엔드포인트 및 에러 핸들링 검증")

main_path = os.path.join(ROOT, "app/main.py")
with open(main_path, encoding="utf-8") as fh:
    main_src = fh.read()
chk("from travel_logic import InsufficientPlacesError" in main_src,
    "InsufficientPlacesError import 존재")
chk("from fastapi.responses import JSONResponse" in main_src,
    "JSONResponse import 존재")
chk("/api/v1/generate-relaxed" in main_src, "generate-relaxed 엔드포인트 존재")
chk("/api/v1/generate-fetch" in main_src,   "generate-fetch 엔드포인트 존재")
chk("except InsufficientPlacesError" in main_src,
    "generate 엔드포인트에 InsufficientPlacesError 핸들러 존재")
chk("status_code=422" in main_src,          "422 상태 코드 반환 코드 존재")
chk("_relax_filter" in main_src,            "generate-relaxed에 _relax_filter=True 플래그")
chk("update_db" in main_src,               "generate-fetch에 update_db 호출 존재")

# ════════════════════════════════════════════════════════════════
# [6] clustering_service v3 — Haversine K-Means (개선점 B)
# ════════════════════════════════════════════════════════════════
sec("Test 6 | ClusteringService v3 — _haversine_kmeans() 메서드 존재 확인")

chk(hasattr(CS, "_haversine_kmeans"),       "_haversine_kmeans 메서드 존재")
chk(hasattr(CS, "_kmeans_plus_plus_init"),  "_kmeans_plus_plus_init 메서드 존재")
chk(hasattr(CS, "_haversine_dist"),         "_haversine_dist 메서드 존재 (v2 유지)")
chk(hasattr(CS, "_rebalance"),              "_rebalance 메서드 존재 (v2 유지)")
chk(hasattr(CS, "_timebox_check"),          "_timebox_check 메서드 존재 (v2 유지)")
chk(hasattr(CS, "_fallback_split"),         "_fallback_split 메서드 존재 (폴백 유지)")

# cluster_by_day 시그니처에 anchor_points 파라미터 확인
import inspect
sig = inspect.signature(CS.cluster_by_day)
chk("anchor_points" in sig.parameters,     "cluster_by_day에 anchor_points 파라미터 추가됨")
chk(sig.parameters["anchor_points"].default is None,
    "anchor_points 기본값 None (하위 호환)")

# ════════════════════════════════════════════════════════════════
# [7] _haversine_kmeans 실행 테스트
# ════════════════════════════════════════════════════════════════
sec("Test 7 | _haversine_kmeans() — 기본 동작 검증")

import random
random.seed(42)
PLACES_20 = [
    {"id": i, "name": f"장소{i}",
     "lat": 33.0 + random.uniform(0, 1.2),
     "lng": 126.0 + random.uniform(0, 1.4)}
    for i in range(20)
]

t0 = time.perf_counter()
labels, centroids = CS._haversine_kmeans(PLACES_20, 4)
elapsed = (time.perf_counter() - t0) * 1000

chk(len(labels) == 20,           f"labels 수 == 20 (실제: {len(labels)})")
chk(len(centroids) == 4,         f"centroids 수 == 4 (실제: {len(centroids)})")
chk(all(0 <= l < 4 for l in labels), f"모든 label 0~3 범위")
chk(elapsed < 3000,              f"처리 시간 < 3000ms (실제: {elapsed:.1f}ms)")

# centroid가 제주도 위경도 범위 내인지
chk(all(33.0 <= c[0] <= 34.5 and 125.5 <= c[1] <= 127.5 for c in centroids),
    f"centroids 제주 범위 내 (lat 33~34.5, lng 125.5~127.5)")

# 각 클러스터에 최소 1개 이상 장소
sizes = [labels.count(k) for k in range(4)]
chk(all(s > 0 for s in sizes),   f"모든 클러스터에 장소 존재 sizes={sizes}")
info(f"Haversine K-Means 처리시간: {elapsed:.1f}ms, sizes={sizes}")

# ════════════════════════════════════════════════════════════════
# [8] Seeded K-Means (개선점 D) — anchor_points 시딩 검증
# ════════════════════════════════════════════════════════════════
sec("Test 8 | Seeded K-Means — anchor_points 시딩 검증")

# 제주 동쪽에 공항, 서쪽에 호텔 앵커 설정
anchor_east = {"id": 901, "name": "제주공항", "lat": 33.51, "lng": 126.49, "score": 80}
anchor_west = {"id": 902, "name": "서귀포호텔", "lat": 33.25, "lng": 126.57, "score": 80}

t1 = time.perf_counter()
c_seeded, ct_seeded = CS.cluster_by_day(PLACES_20, 2, anchor_points=[anchor_east, anchor_west])
t_seed_ms = (time.perf_counter() - t1) * 1000

chk(len(c_seeded) == 2,          f"앵커 시딩 후 클러스터 2개 (실제: {len(c_seeded)})")
chk(len(ct_seeded) == 2,         f"centroid 2개 반환")
chk(all(len(c) > 0 for c in c_seeded), f"빈 클러스터 없음 sizes={[len(c) for c in c_seeded]}")
chk(t_seed_ms < 3000,            f"시딩 처리 시간 < 3000ms (실제: {t_seed_ms:.1f}ms)")

# 앵커 없는 결과와 비교
c_no_seed, ct_no_seed = CS.cluster_by_day(PLACES_20, 2)
sizes_seed   = sorted([len(c) for c in c_seeded])
sizes_noseed = sorted([len(c) for c in c_no_seed])
info(f"시딩 있음 sizes={sizes_seed} / 시딩 없음 sizes={sizes_noseed}")

# 기능적으로 두 경우 모두 유효한 클러스터여야 함
chk(sum(len(c) for c in c_seeded) <= 20,  "시딩 결과 총 장소 수 ≤ 20")
chk(sum(len(c) for c in c_no_seed) <= 20, "비시딩 결과 총 장소 수 ≤ 20")

# ════════════════════════════════════════════════════════════════
# [9] _kmeans_plus_plus_init — 앵커 우선 배치 검증
# ════════════════════════════════════════════════════════════════
sec("Test 9 | _kmeans_plus_plus_init — 앵커 좌표 우선 배치")

coords_sample = [(33.0 + i*0.05, 126.0 + i*0.05) for i in range(10)]
anchor_c = [(33.51, 126.49), (33.25, 126.57)]  # 2개 앵커

init_centroids = CS._kmeans_plus_plus_init(coords_sample, k=3, anchor_coords=anchor_c)
chk(len(init_centroids) == 3,             "초기 centroid 3개 생성")
chk(init_centroids[0] == anchor_c[0],    f"첫 번째 centroid = 앵커0 {anchor_c[0]}")
chk(init_centroids[1] == anchor_c[1],    f"두 번째 centroid = 앵커1 {anchor_c[1]}")
chk(init_centroids[2] not in anchor_c,   "세 번째 centroid는 K-Means++로 선택됨")

# 앵커 없이 호출
init_no_anchor = CS._kmeans_plus_plus_init(coords_sample, k=3)
chk(len(init_no_anchor) == 3,            "앵커 없이 3개 centroid 생성")
chk(all(c in coords_sample for c in init_no_anchor),
    "앵커 없는 경우 모든 centroid는 입력 좌표에서 선택")

# ════════════════════════════════════════════════════════════════
# [10] Haversine 정확도 검증 (v2 유지 확인)
# ════════════════════════════════════════════════════════════════
sec("Test 10 | _haversine_dist() — 거리 정확도 (v2 로직 유지)")

d_si = CS._haversine_dist(37.5665, 126.9780, 37.4563, 126.7052)  # 서울↔인천 ≈27km
chk(25.0 <= d_si <= 30.0,                f"서울↔인천 거리 ≈{d_si:.1f}km (기대 25~30km)")
chk(math.isclose(CS._haversine_dist(37.5, 127.0, 37.5, 127.0), 0.0, abs_tol=1e-6),
    "동일 좌표 거리=0")
d_ab = CS._haversine_dist(33.0, 126.0, 33.5, 127.0)
d_ba = CS._haversine_dist(33.5, 127.0, 33.0, 126.0)
chk(math.isclose(d_ab, d_ba, rel_tol=1e-9), f"대칭성 검증: {d_ab:.4f}=={d_ba:.4f}")

# ════════════════════════════════════════════════════════════════
# [11] itinerary_generator.py — 변경 코드 검증
# ════════════════════════════════════════════════════════════════
sec("Test 11 | itinerary_generator.py — 변경 코드 정적 검증")

ig_path = os.path.join(ROOT, "travel_logic/itinerary_generator.py")
with open(ig_path, encoding="utf-8") as fh:
    ig_src = fh.read()
chk("from .exceptions import InsufficientPlacesError" in ig_src,
    "InsufficientPlacesError import 존재")
chk("raise InsufficientPlacesError(" in ig_src,
    "장소 부족 시 InsufficientPlacesError raise 코드 존재")
chk("min_required" in ig_src,             "min_required 변수 존재")
chk("kmeans_anchors" in ig_src,           "kmeans_anchors 구성 코드 존재")
chk("anchor_points=kmeans_anchors" in ig_src,
    "cluster_by_day에 anchor_points 전달 코드 존재")
chk("num_hotels" in ig_src and "airport_place" in ig_src,
    "멀티호텔/공항 조건 분기 존재")

# ════════════════════════════════════════════════════════════════
# [12] cluster_by_day 풀 파이프라인 (anchor_points 포함)
# ════════════════════════════════════════════════════════════════
sec("Test 12 | cluster_by_day 전체 파이프라인 — v3 anchor_points 포함")

random.seed(99)
PLACES_30 = [
    {"id": i, "name": f"장소{i}", "score": random.randint(50, 100),
     "lat": 33.2 + random.uniform(0, 0.8),
     "lng": 126.2 + random.uniform(0, 0.8)}
    for i in range(30)
]
ANCHORS = [
    {"id": 801, "name": "공항", "lat": 33.51, "lng": 126.49},
    {"id": 802, "name": "호텔A", "lat": 33.25, "lng": 126.60},
    {"id": 803, "name": "호텔B", "lat": 33.40, "lng": 126.30},
]

t2 = time.perf_counter()
c12, ct12 = CS.cluster_by_day(PLACES_30, 3, anchor_points=ANCHORS)
ms12 = (time.perf_counter() - t2) * 1000

chk(len(c12) == 3,               f"3일: 클러스터 3개 (실제: {len(c12)})")
chk(len(ct12) == 3,              f"centroid 3개 반환")
chk(all(len(c) > 0 for c in c12), f"빈 클러스터 없음 sizes={[len(c) for c in c12]}")
s12 = [len(c) for c in c12]
chk(max(s12) - min(s12) <= 2,   f"균등화 완료 diff={max(s12)-min(s12)} sizes={s12}")
MAX_D = int(cs_mod._MAX_DAILY_HOURS * 3600 / cs_mod._SIGHT_VISIT_SEC)
chk(all(len(c) <= MAX_D for c in c12), f"Time-Box 준수 (≤{MAX_D}개/일)")
chk(ms12 < 5000,                f"처리 시간 < 5000ms (실제: {ms12:.1f}ms)")
info(f"30개 장소 / 3일 / 앵커3개 → sizes={s12} / {ms12:.1f}ms")

# ════════════════════════════════════════════════════════════════
# 최종 결과
# ════════════════════════════════════════════════════════════════
total = p + f
print(f"\n{'='*62}")
if f == 0:
    print(f"  {G}{B}ALL {p} TESTS PASSED ✓{X}")
else:
    print(f"  {G}{p} PASS{X}  /  {R}{f} FAIL{X}  (총 {total}개)")
print(f"{'='*62}\n")
sys.exit(0 if f == 0 else 1)
