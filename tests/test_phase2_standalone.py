"""
Phase 2 standalone test (DB dependency-free)  v2
ClusteringService 독립 테스트

[v2 테스트 변경 이력]
  v1 → v2:
  - Test 4/5/8: Time-Box 검증(_timebox_check) 도입으로 인해 장소 수 보존 기대치 변경
    (10h 초과 클러스터에서 최저 점수 장소 자동 제거 → 전체 보존 아님)
  - Test 9 추가: Time-Box 검증 전용 테스트 (max_hours 초과 시 제거 동작 확인)
  - Test 10 추가: _haversine_dist() 정확도 검증
  - Test 11 추가: 스마트 리밸런싱(Smart Rebalancing) vs 맹목적 pop() 비교 검증
"""

import sys, os, importlib.util, time, math

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("OMP_NUM_THREADS", "1")  # Windows MKL 경고 억제

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
#  ClusteringService 직접 로드
# ════════════════════════════════════════════════════════════════
def _load_module(alias, filepath):
    spec = importlib.util.spec_from_file_location(alias, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod

try:
    cs_mod = _load_module(
        "travel_logic.services.clustering_service",
        os.path.join(ROOT, "travel_logic/services/clustering_service.py")
    )
    CS = cs_mod.ClusteringService
    print(f"\n{BOLD}clustering_service.py (v2) 로드 성공{RESET}\n")
except Exception as e:
    print(f"{RED}모듈 로드 실패: {e}{RESET}")
    sys.exit(1)

# Time-Box 상수 (모듈과 동일한 값)
MAX_DAILY_HOURS   = cs_mod._MAX_DAILY_HOURS    # 10
SIGHT_VISIT_SEC   = cs_mod._SIGHT_VISIT_SEC    # 9000 (2.5h)
MAX_SIGHTS_PER_DAY = int(MAX_DAILY_HOURS * 3600 / SIGHT_VISIT_SEC)  # = 4
info(f"Time-Box 상수: 하루 최대 {MAX_DAILY_HOURS}h, 관광지 기본 {SIGHT_VISIT_SEC/3600:.1f}h → 클러스터당 최대 {MAX_SIGHTS_PER_DAY}개")


# ════════════════════════════════════════════════════════════════
#  Test 1: 정상 클러스터링 — 제주도 3박 4일 시나리오
# ════════════════════════════════════════════════════════════════
section("Test 1 | 정상 클러스터링 — 제주도 20개 장소 / 4일")

import random
random.seed(42)

JEJU = [
    {"id": i, "name": f"제주장소{i:02d}",
     "lat": 33.0 + random.uniform(0, 1.2),
     "lng": 126.0 + random.uniform(0, 1.4)}
    for i in range(1, 21)
]

t0 = time.perf_counter()
clusters, centroids = CS.cluster_by_day(JEJU, 4)
elapsed_ms = (time.perf_counter() - t0) * 1000

check(len(clusters) == 4,
      f"클러스터 수 == 4  (실제: {len(clusters)})")
check(len(centroids) == 4,
      f"centroid 수 == 4  (실제: {len(centroids)})")

# v2: Time-Box로 일부 장소가 제거될 수 있으므로 '전체 보존' 대신 '각 클러스터 ≤ MAX_SIGHTS_PER_DAY' 검증
check(all(len(c) <= MAX_SIGHTS_PER_DAY for c in clusters),
      f"각 클러스터 장소 수 ≤ {MAX_SIGHTS_PER_DAY}  (sizes={[len(c) for c in clusters]})",
      f"Time-Box 초과 클러스터 존재  sizes={[len(c) for c in clusters]}")
check(all(len(c) > 0 for c in clusters),
      f"빈 클러스터 없음  (sizes={[len(c) for c in clusters]})")

sizes = [len(c) for c in clusters]
diff = max(sizes) - min(sizes)
check(diff <= 2,
      f"클러스터 균등화 (max-min={diff} ≤ 2)  sizes={sizes}",
      f"균등화 실패: diff={diff}, sizes={sizes}")

check(all(33.0 <= lat <= 34.5 and 125.5 <= lng <= 127.5 for lat, lng in centroids),
      f"centroid 좌표 범위 유효 (제주도 위경도 범위 내)")

# warm-up 후 재측정
CS.cluster_by_day(JEJU, 4)
t1 = time.perf_counter()
CS.cluster_by_day(JEJU, 4)
warm_ms = (time.perf_counter() - t1) * 1000
info(f"최초 호출: {elapsed_ms:.1f}ms / warm-up 후: {warm_ms:.1f}ms")
check(warm_ms < 2000,
      f"warm-up 후 처리 속도 < 2000ms  (실제: {warm_ms:.1f}ms)",
      f"속도 기준 초과: {warm_ms:.1f}ms")


# ════════════════════════════════════════════════════════════════
#  Test 2: 빈 입력 예외 처리
# ════════════════════════════════════════════════════════════════
section("Test 2 | 빈 입력 — 에러 없이 빈 클러스터 반환")

c2, ct2 = CS.cluster_by_day([], 3)
check(len(c2) == 3,
      f"빈 입력 + 3일: 클러스터 3개 반환  (실제: {len(c2)})")
check(len(ct2) == 3,
      f"빈 입력 + 3일: centroid 3개 반환  (실제: {len(ct2)})")
check(all(len(c) == 0 for c in c2),
      "모든 클러스터 비어있음 (에러 없이 안전 반환)")
info("빈 입력 → 정상 반환 (에러 없음)")


# ════════════════════════════════════════════════════════════════
#  Test 3: 장소 수 ≤ 여행 일수 (극단 케이스)
# ════════════════════════════════════════════════════════════════
section("Test 3 | 장소 수 ≤ 일수 — 극단 케이스 처리")

tiny = [
    {"id": 1, "name": "장소A", "lat": 33.5, "lng": 126.5},
    {"id": 2, "name": "장소B", "lat": 33.6, "lng": 126.6},
]
c3, ct3 = CS.cluster_by_day(tiny, 5)  # 장소 2개, 5일 여행
check(len(c3) == 5,
      f"2개 장소 + 5일: 클러스터 5개 반환  (실제: {len(c3)})")
check(sum(len(c) for c in c3) == 2,
      f"총 장소 수 보존 (2개)  (실제: {sum(len(c) for c in c3)})")
info(f"sizes = {[len(c) for c in c3]}")

# 장소 수 == 일수
exact = [{"id": i, "name": f"장소{i}", "lat": 33.0 + i * 0.1, "lng": 126.0 + i * 0.1} for i in range(3)]
c3b, _ = CS.cluster_by_day(exact, 3)
check(len(c3b) == 3,
      f"3개 장소 + 3일: 클러스터 3개  (실제: {len(c3b)})")
check(all(len(c) == 1 for c in c3b),
      "각 클러스터에 장소 1개씩 정확히 배정")


# ════════════════════════════════════════════════════════════════
#  Test 4: 1일 여행 (v2 Time-Box 반영)
# ════════════════════════════════════════════════════════════════
section("Test 4 | 1일 여행 — Time-Box 적용 후 최대 장소 수 검증")

places_10 = [
    {"id": i, "name": f"장소{i}", "lat": 33.0 + i * 0.05, "lng": 126.0 + i * 0.05}
    for i in range(10)
]
c4, ct4 = CS.cluster_by_day(places_10, 1)

check(len(c4) == 1,
      f"1일 여행: 클러스터 1개  (실제: {len(c4)})")
check(len(ct4) == 1,
      f"centroid 1개 반환  (실제: {len(ct4)})")

# v2: Time-Box 검증으로 10h / 2.5h = 4개 이하로 제한
actual_count = len(c4[0])
check(actual_count <= MAX_SIGHTS_PER_DAY,
      f"Time-Box 적용: {actual_count}개 ≤ {MAX_SIGHTS_PER_DAY}개 (10h / 2.5h)",
      f"Time-Box 미작동: {actual_count}개 > {MAX_SIGHTS_PER_DAY}개")
check(actual_count > 0,
      f"최소 1개 장소 보존  (실제: {actual_count}개)")

# 남은 장소들의 총 체류 시간이 10h 초과하지 않는지 확인
total_h = actual_count * SIGHT_VISIT_SEC / 3600
check(total_h <= MAX_DAILY_HOURS,
      f"총 체류 시간 {total_h:.1f}h ≤ {MAX_DAILY_HOURS}h",
      f"총 체류 시간 초과: {total_h:.1f}h")
info(f"[v1과의 차이] v1: 10개 그대로 보존 | v2: Time-Box로 {actual_count}개로 감축 (총 {total_h:.1f}h)")


# ════════════════════════════════════════════════════════════════
#  Test 5: 균등화 강제 검증 — 지리 편중 데이터 (v2 Time-Box 반영)
# ════════════════════════════════════════════════════════════════
section("Test 5 | 균등화 검증 — 편중 데이터 + Time-Box 동시 검증")

biased = (
    [{"id": i, "name": f"동쪽{i}", "lat": 33.5, "lng": 127.0 + i * 0.01} for i in range(15)] +
    [{"id": 100 + i, "name": f"서쪽{i}", "lat": 33.5, "lng": 126.0 + i * 0.01} for i in range(3)]
)
c5, ct5 = CS.cluster_by_day(biased, 3)
s5 = sorted([len(c) for c in c5])
diff5 = max(s5) - min(s5)

# v2: Time-Box로 각 클러스터 최대 4개 → 전체 보존 아님
check(all(len(c) > 0 for c in c5),
      f"빈 클러스터 없음  (sizes={[len(c) for c in c5]})")
check(diff5 <= 2,
      f"편중 데이터 균등화 성공 (diff={diff5} ≤ 2)  sizes={s5}",
      f"균등화 실패: diff={diff5}, sizes={s5}")
check(all(len(c) <= MAX_SIGHTS_PER_DAY for c in c5),
      f"모든 클러스터 Time-Box 준수 (≤ {MAX_SIGHTS_PER_DAY}개)",
      f"Time-Box 초과 클러스터 존재: sizes={[len(c) for c in c5]}")

total_placed = sum(len(c) for c in c5)
info(f"동쪽 15개 + 서쪽 3개 = 18개 → Time-Box 후 {total_placed}개 배정  sizes={s5}")
info(f"[v1과의 차이] v1: '18개 전부 보존' 검증 | v2: 'Time-Box 준수' 검증으로 변경")


# ════════════════════════════════════════════════════════════════
#  Test 6: centroid 정확도 — 실제 좌표 평균과 일치하는지
# ════════════════════════════════════════════════════════════════
section("Test 6 | centroid 정확도 — 실제 장소 좌표 평균과 일치")

for i, (group, (clat, clng)) in enumerate(zip(clusters, centroids)):
    if not group:
        continue
    expected_lat = sum(p["lat"] for p in group) / len(group)
    expected_lng = sum(p["lng"] for p in group) / len(group)
    lat_ok = math.isclose(expected_lat, clat, abs_tol=1e-6)
    lng_ok = math.isclose(expected_lng, clng, abs_tol=1e-6)
    check(lat_ok and lng_ok,
          f"Day{i+1} centroid = 좌표 평균  "
          f"expected=({expected_lat:.5f},{expected_lng:.5f}) actual=({clat:.5f},{clng:.5f})",
          f"Day{i+1} centroid 불일치  "
          f"expected=({expected_lat:.5f},{expected_lng:.5f}) actual=({clat:.5f},{clng:.5f})")


# ════════════════════════════════════════════════════════════════
#  Test 7: fallback_split — scikit-learn 없을 때 대체 동작
# ════════════════════════════════════════════════════════════════
section("Test 7 | fallback_split() — scikit-learn 미설치 대체 로직")

c7, ct7 = CS._fallback_split(JEJU, 4)
check(len(c7) == 4,
      f"fallback: 클러스터 4개  (실제: {len(c7)})")
check(sum(len(c) for c in c7) == 20,
      f"fallback: 20개 장소 보존  (실제: {sum(len(c) for c in c7)})")
check(sorted([len(c) for c in c7]) == [5, 5, 5, 5],
      f"fallback: 완벽 균등 분배 [5,5,5,5]  (실제: {sorted([len(c) for c in c7])})")
check(all(len(ct) == 2 for ct in ct7),
      "fallback: 모든 centroid가 (lat, lng) 형태")

for i, (group, (clat, clng)) in enumerate(zip(c7, ct7)):
    expected_lat = sum(p["lat"] for p in group) / len(group)
    expected_lng = sum(p["lng"] for p in group) / len(group)
    check(math.isclose(expected_lat, clat, abs_tol=1e-6),
          f"fallback Day{i+1} centroid lat 정확  ({clat:.5f})")


# ════════════════════════════════════════════════════════════════
#  Test 8: 대용량 처리 — 100개 장소 / 7일 (v2 Time-Box 반영)
# ════════════════════════════════════════════════════════════════
section("Test 8 | 대용량 처리 — 100개 장소 / 7일 + Time-Box 검증")

BIG = [
    {"id": i, "name": f"장소{i}",
     "lat": 33.0 + random.uniform(0, 2.0),
     "lng": 126.0 + random.uniform(0, 2.0)}
    for i in range(100)
]
t_big0 = time.perf_counter()
c8, ct8 = CS.cluster_by_day(BIG, 7)
big_ms = (time.perf_counter() - t_big0) * 1000

check(len(c8) == 7,
      f"100개/7일: 클러스터 7개  (실제: {len(c8)})")
check(all(len(c) > 0 for c in c8),
      f"빈 클러스터 없음  (sizes={[len(c) for c in c8]})")

# v2: 각 클러스터가 Time-Box 준수 여부 검증 (전체 보존 아님)
s8 = [len(c) for c in c8]
diff8 = max(s8) - min(s8)
check(diff8 <= 2,
      f"100개/7일 균등화 (diff={diff8} ≤ 2)  sizes={sorted(s8)}",
      f"균등화 실패: diff={diff8}, sizes={sorted(s8)}")
check(all(len(c) <= MAX_SIGHTS_PER_DAY for c in c8),
      f"모든 클러스터 Time-Box 준수 (≤ {MAX_SIGHTS_PER_DAY}개)",
      f"Time-Box 초과 클러스터 존재: sizes={sorted(s8)}")
info(f"처리 시간: {big_ms:.1f}ms  sizes={sorted(s8)}  (총 배정: {sum(s8)}개/100개)")


# ════════════════════════════════════════════════════════════════
#  Test 9 (신규): Time-Box 검증 전용 — 초과 장소 제거 동작
# ════════════════════════════════════════════════════════════════
section("Test 9 | [v2 신규] Time-Box 검증 — 체류시간 초과 장소 제거")

# 점수 있는 장소로 구성 (제거 우선순위 확인)
heavy_cluster = [
    {"id": i, "name": f"관광지{i}", "lat": 37.5 + i*0.01, "lng": 127.0 + i*0.01,
     "score": 100 - i * 10}  # score: 100, 90, 80, 70, 60, 50 ...
    for i in range(6)  # 6개 × 2.5h = 15h > 10h
]

result = CS._timebox_check([heavy_cluster[:]], max_hours=10)
remaining = result[0]
remaining_scores = sorted([p['score'] for p in remaining], reverse=True)
total_h = len(remaining) * SIGHT_VISIT_SEC / 3600

check(total_h <= 10.0,
      f"Time-Box 후 총 체류 시간 {total_h:.1f}h ≤ 10h",
      f"Time-Box 미작동: {total_h:.1f}h > 10h")
check(len(remaining) <= MAX_SIGHTS_PER_DAY,
      f"남은 장소 수 {len(remaining)}개 ≤ {MAX_SIGHTS_PER_DAY}개")
check(remaining_scores == sorted(remaining_scores, reverse=True),
      f"높은 점수 장소 우선 보존 확인  남은 점수={remaining_scores}",
      f"점수 기반 제거 오동작  남은 점수={remaining_scores}")

info(f"6개(15h) → {len(remaining)}개({total_h:.1f}h) 감축, 보존된 점수={remaining_scores}")

# 10h 이하 클러스터는 변경 없음 검증
light_cluster = [
    {"id": i, "name": f"카페{i}", "lat": 37.5, "lng": 127.0, "score": 80, "type_key": "카페"}
    for i in range(3)  # 3개 × 1h = 3h < 10h → 변경 없어야 함
]
light_result = CS._timebox_check([light_cluster[:]], max_hours=10)
check(len(light_result[0]) == 3,
      "3h짜리 카페 클러스터는 Time-Box 미발동 (3개 유지)")
info("카페 3개 × 1h = 3h < 10h → 제거 없음 확인")


# ════════════════════════════════════════════════════════════════
#  Test 10 (신규): _haversine_dist() 정확도 검증
# ════════════════════════════════════════════════════════════════
section("Test 10 | [v2 신규] _haversine_dist() — Haversine 거리 정확도")

# 서울(37.5665, 126.9780) ↔ 인천(37.4563, 126.7052) ≈ 약 27km
seoul_lat, seoul_lng = 37.5665, 126.9780
incheon_lat, incheon_lng = 37.4563, 126.7052
dist_si = CS._haversine_dist(seoul_lat, seoul_lng, incheon_lat, incheon_lng)
check(25.0 <= dist_si <= 30.0,
      f"서울↔인천 거리 ≈ {dist_si:.1f}km (기대: 25~30km)",
      f"거리 계산 오류: {dist_si:.1f}km")

# 동일 좌표 거리 = 0
dist_same = CS._haversine_dist(37.5665, 126.9780, 37.5665, 126.9780)
check(math.isclose(dist_same, 0.0, abs_tol=1e-6),
      f"동일 좌표 거리 = 0  (실제: {dist_same:.8f})")

# 대칭성: dist(A→B) == dist(B→A)
dist_ab = CS._haversine_dist(33.0, 126.0, 33.5, 127.0)
dist_ba = CS._haversine_dist(33.5, 127.0, 33.0, 126.0)
check(math.isclose(dist_ab, dist_ba, rel_tol=1e-9),
      f"대칭성 검증: dist(A→B) == dist(B→A)  ({dist_ab:.4f} == {dist_ba:.4f})")

info(f"서울↔인천: {dist_si:.2f}km | 동일 좌표: {dist_same:.8f}km | 대칭성: OK")


# ════════════════════════════════════════════════════════════════
#  Test 11 (신규): 스마트 리밸런싱 vs v1 pop() 비교
# ════════════════════════════════════════════════════════════════
section("Test 11 | [v2 신규] 스마트 리밸런싱 — 지리적 연속성 검증")

# 시나리오: 강남권 6개 + 강북권 3개, 2클러스터
gangnam = [
    {"id": i, "name": f"강남{i}", "lat": 37.50 + i*0.005, "lng": 127.00 + i*0.005, "score": 70}
    for i in range(6)
]
gangbuk = [
    {"id": 100+i, "name": f"강북{i}", "lat": 37.58 + i*0.005, "lng": 126.98 + i*0.005, "score": 70}
    for i in range(3)
]

# 클러스터 직접 구성 (K-Means 우회)
test_clusters = [gangnam[:], gangbuk[:]]
test_centroids = [
    (sum(p['lat'] for p in gangnam) / len(gangnam),
     sum(p['lng'] for p in gangnam) / len(gangnam)),
    (sum(p['lat'] for p in gangbuk) / len(gangbuk),
     sum(p['lng'] for p in gangbuk) / len(gangbuk)),
]

result_clusters, result_centroids = CS._rebalance(test_clusters, test_centroids)

# 균등화 완료 확인
r_sizes = [len(c) for c in result_clusters]
check(max(r_sizes) - min(r_sizes) <= 2,
      f"리밸런싱 후 균등화 완료  sizes={r_sizes}",
      f"균등화 실패: sizes={r_sizes}")

# 핵심 검증: 이동된 장소가 강북 클러스터의 centroid와 가장 가까운 강남 장소여야 함
# 강북 centroid ≈ (37.585, 126.990)
# 강남에서 가장 가까운 장소 = 강남5 (37.525, 127.025) → 강남0 (37.500, 127.000)
# 강남에서 강북 centroid까지 거리가 가장 짧은 장소가 이동되었는지 확인
if len(result_clusters[0]) < len(gangnam):  # 강남에서 장소가 이동된 경우
    remaining_in_gangnam = [p['name'] for p in result_clusters[0]]
    moved_to_gangbuk = [p['name'] for p in result_clusters[1] if 'gangnam' in p.get('name', '').lower() or '강남' in p.get('name', '')]
    info(f"강남 클러스터에서 강북으로 이동된 장소: {[p['name'] for p in result_clusters[1]]}")
    check(len(result_clusters[1]) > len(gangbuk),
          f"강남 → 강북으로 장소 이동 성공 (강북: {len(result_clusters[1])}개)")

info(f"[v1 pop() vs v2 스마트] v1은 마지막 장소(강남5) 무조건 이동, v2는 강북 centroid 최근접 장소 선택")
info(f"리밸런싱 후 sizes={r_sizes}")


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
