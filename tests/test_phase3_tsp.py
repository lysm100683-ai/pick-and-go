import sys, os, math, time, random, importlib.util, types
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ── 색상 ──────────────────────────────────────────────────────
G, R, B, X = "\033[32m", "\033[31m", "\033[1m", "\033[0m"
p = f = 0

def sec(msg):  print(f"\n{'='*62}\n  {msg}\n{'='*62}")
def info(msg): print(f"  INFO  {msg}")
def chk(cond, msg):
    global p, f
    if cond:  p += 1; print(f"  PASS  {msg}")
    else:     f += 1; print(f"  {R}FAIL{X}  {msg}")

# ── Mock DistanceService ───────────────────────────────────────
class MockDistanceService:
    """실제 API 없이 Haversine 기반으로 이동시간 계산 (60km/h 가정)"""
    def haversine_distance(self, lat1, lng1, lat2, lng2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlng/2)**2
        return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    def get_travel_times_bulk(self, lat, lng, candidates, is_korea, mode):
        results = []
        for c in candidates:
            km  = self.haversine_distance(lat, lng, c['lat'], c['lng'])
            results.append((int(km / 60.0 * 3600), c))
        return results

mock_ds = MockDistanceService()

# geoalchemy2 / relative import 우회
# travel_logic.services 패키지를 stub으로 등록 후 tsp_service.py 직접 로드
for _n in ["travel_logic", "travel_logic.services", "travel_logic.services.distance_service"]:
    if _n not in sys.modules:
        _sm = types.ModuleType(_n)
        if _n == "travel_logic.services.distance_service":
            class _FakeDS: pass
            _sm.DistanceService = _FakeDS
        sys.modules[_n] = _sm

_tsp_path = os.path.join(ROOT, "travel_logic", "services", "tsp_service.py")
_spec = importlib.util.spec_from_file_location(
    "travel_logic.services.tsp_service",
    _tsp_path,
    submodule_search_locations=[],
)
_mod = importlib.util.module_from_spec(_spec)
_mod.__package__ = "travel_logic.services"
sys.modules["travel_logic.services.tsp_service"] = _mod
_spec.loader.exec_module(_mod)

TSP = _mod.TSPService
tsp = TSP(mock_ds)
print("\ntsp_service.py 로드 성공")

# ── 테스트용 장소 생성 헬퍼 ────────────────────────────────────
def make_place(id_, lat, lng, name):
    return {"id": id_, "name": name, "lat": lat, "lng": lng, "score": 80}

START = {"id": "hotel", "name": "호텔", "lat": 37.50, "lng": 126.90, "score": 0}
P1 = make_place(1, 37.50, 126.99, "장소A")
P2 = make_place(2, 37.50, 127.08, "장소B")
P3 = make_place(3, 37.50, 127.17, "장소C")
P4 = make_place(4, 37.50, 126.81, "장소D")
FAR= make_place(5, 35.00, 129.00, "부산장소")

# ════════════════════════════════════════════════════════════════
sec("Test 1 | solve() — 빈 입력 처리")
# ════════════════════════════════════════════════════════════════
o, tt, total = tsp.solve([], START, True, "driving")
chk(o == [],    "빈 places → ordered = []")
chk(tt == [],   "빈 places → travel_times = []")
chk(total == 0, "빈 places → total_time = 0")
o2, tt2, tot2 = tsp.solve([P1, P2], None, True, "driving")
chk(len(o2) == 2, "start_point=None → Haversine Greedy 폴백, 2개 반환")
chk(tot2 == 0,    "start_point=None → total_time=0 (API 미호출)")
info(f"None 폴백 순서: {[x['name'] for x in o2]}")

# ════════════════════════════════════════════════════════════════
sec("Test 2 | solve() — 단일 장소")
# ════════════════════════════════════════════════════════════════
o3, tt3, tot3 = tsp.solve([P1], START, True, "driving")
chk(len(o3) == 1,            "단일 장소 → ordered 1개")
chk(o3[0]['id'] == 1,        "단일 장소 → P1 반환")
chk(len(tt3) == 1,           "이동시간 1개 반환")
chk(isinstance(tt3[0], int), "이동시간은 int형")
chk(tot3 > 0,                "총 이동시간 > 0")
info(f"호텔→장소A 이동시간: {tt3[0]}초 ({tt3[0]//60}분)")

# ════════════════════════════════════════════════════════════════
sec("Test 3 | solve() — 3개 장소 최근접 순서 검증")
# ════════════════════════════════════════════════════════════════
o4, tt4, tot4 = tsp.solve([P3, P2, P1], START, True, "driving")
chk(len(o4) == 3,     "3개 장소 → ordered 3개")
chk(len(tt4) == 3,    "이동시간 3개 반환")
chk(o4[0]['id'] == 1, f"첫 방문 = 가장 가까운 장소A (실제: {o4[0]['name']})")
chk(o4[1]['id'] == 2, f"두 번째 = 장소B (실제: {o4[1]['name']})")
chk(o4[2]['id'] == 3, f"세 번째 = 장소C (실제: {o4[2]['name']})")
chk(tot4 == sum(tt4), f"total_time = sum(travel_times) ({tot4}초)")
info(f"방문 순서: {[x['name'] for x in o4]} / 구간시간: {[t//60 for t in tt4]}분")

# ════════════════════════════════════════════════════════════════
sec("Test 4 | solve() — 양방향 분산 장소")
# ════════════════════════════════════════════════════════════════
o5, _, _ = tsp.solve([P1, P4], START, True, "driving")
chk(len(o5) == 2, "2개 장소 → ordered 2개")
chk({x['id'] for x in o5} == {1, 4}, "두 장소 모두 포함")
info(f"동서 대칭 순서: {[x['name'] for x in o5]}")

# ════════════════════════════════════════════════════════════════
sec("Test 5 | solve() — 멀리 있는 장소 포함 (부산 장소)")
# ════════════════════════════════════════════════════════════════
o6, _, tot6 = tsp.solve([FAR, P1, P2], START, True, "driving")
chk(len(o6) == 3,      "3개 장소 → ordered 3개")
chk(o6[-1]['id'] == 5, f"부산장소가 마지막 (실제: {o6[-1]['name']})")
chk(tot6 > 300*60,     f"총 이동시간 > 300분 (실제: {tot6//60}분)")
info(f"순서: {[x['name'] for x in o6]} / 총이동: {tot6//60}분")

# ════════════════════════════════════════════════════════════════
sec("Test 6 | _haversine_greedy() — 직접 테스트")
# ════════════════════════════════════════════════════════════════
o7 = TSP._haversine_greedy([P3, P2, P1])
chk(len(o7) == 3,      "_haversine_greedy 3개 반환")
chk(o7[0]['id'] == 3,  "첫 번째 = 입력 첫 장소(P3) 고정")
chk(o7[1]['id'] == 2,  "두 번째 = P3에서 가장 가까운 P2")
chk(o7[2]['id'] == 1,  "세 번째 = P1")
info(f"Haversine Greedy 순서: {[x['name'] for x in o7]}")
chk(TSP._haversine_greedy([]) == [], "_haversine_greedy([]) → []")

# ════════════════════════════════════════════════════════════════
sec("Test 7 | solve() — 처리 시간 검증 (20장소)")
# ════════════════════════════════════════════════════════════════
rng = random.Random(42)
places20 = [make_place(f"r{i}", 37.0+rng.random(), 126.0+rng.random()*1.5, f"장소{i}") for i in range(20)]
t0 = time.time()
o8, tt8, tot8 = tsp.solve(places20, START, True, "driving")
elapsed = (time.time() - t0) * 1000
chk(len(o8) == 20,    "20개 장소 모두 반환")
chk(len(tt8) == 20,   "이동시간 20개 반환")
chk(elapsed < 1000,   f"처리 시간 < 1000ms (실제: {elapsed:.1f}ms)")
chk(tot8 == sum(tt8), "total_time 정확성")
info(f"20개 장소 TSP 처리시간: {elapsed:.1f}ms / 총이동: {tot8//60}분")

# ════════════════════════════════════════════════════════════════
sec("Test 8 | services/__init__.py export 검증")
# ════════════════════════════════════════════════════════════════
init_path = os.path.join(ROOT, "travel_logic/services/__init__.py")
with open(init_path, encoding="utf-8") as fh:
    src = fh.read()
chk("from .tsp_service import TSPService" in src, "TSPService import 구문 존재")
chk("'TSPService'" in src,                        "__all__에 TSPService 등록")
chk("# Phase 3" in src,                           "Phase 3 주석 존재")

# ════════════════════════════════════════════════════════════════
sec("Test 9 | itinerary_generator.py Phase 3 v2 연동 코드 검증")
# ════════════════════════════════════════════════════════════════
ig_path = os.path.join(ROOT, "travel_logic/itinerary_generator.py")
with open(ig_path, encoding="utf-8") as fh:
    ig_src = fh.read()
chk("TSPService" in ig_src,                          "TSPService import됨")
chk("self.tsp_service = TSPService" in ig_src,       "__init__에 tsp_service 초기화")
chk("self.tsp_service.solve(" in ig_src,             "solve() 호출")
chk("tsp_queue" in ig_src,                           "tsp_queue 변수 존재")
chk('type_key == "관광"' in ig_src,                   "관광지 TSP 분기 존재")
chk("tsp_queue.pop(0)" in ig_src,                    "tsp_queue.pop(0) 소비 로직")
chk("optimization_service.select_next_place" in ig_src, "카페 기존 로직 유지")
chk("day_start_for_tsp" in ig_src,                   "출발점 변수 존재")
chk("unvisited_day_sights" in ig_src,                "미방문 필터링 코드")
chk("end_point=day_start_for_tsp" in ig_src,         "[v2] Round-trip end_point 코드")
chk("find_best_meal_insertion" in ig_src,             "[v2] 식사 우회 최소 삽입 호출")
chk('type_key == "식사"' in ig_src,                   "[v2] 식사 분기 존재")
chk("next_sight = tsp_queue[0]" in ig_src,           "[v2] 다음 관광지 peek 코드")

# ════════════════════════════════════════════════════════════════
sec("Test 10 | [v2] Dynamic TOP_N 수식 검증")
# ════════════════════════════════════════════════════════════════
chk(TSP._get_filter_n(3)  == 3,  "3개  → 3 (전체 조회)")
chk(TSP._get_filter_n(5)  == 5,  "5개  → 5 (전체 조회)")
chk(TSP._get_filter_n(6)  == 8,  "6개  → 8")
chk(TSP._get_filter_n(15) == 8,  "15개 → 8")
chk(TSP._get_filter_n(16) == 12, "16개 → 12")
chk(TSP._get_filter_n(30) == 12, "30개 → 12")
chk(TSP._get_filter_n(31) == 15, "31개 → 15 (최대)")
info(f"Dynamic TOP_N: 3개={TSP._get_filter_n(3)}, 15개={TSP._get_filter_n(15)}, 50개={TSP._get_filter_n(50)}")

# ════════════════════════════════════════════════════════════════
sec("Test 11 | [v2] 2-Opt 코드 존재 및 동작 검증")
# ════════════════════════════════════════════════════════════════
tsp_src_path = os.path.join(ROOT, "travel_logic/services/tsp_service.py")
with open(tsp_src_path, encoding="utf-8") as fh:
    tsp_src = fh.read()
chk("_two_opt_haversine" in tsp_src, "[v2] _two_opt_haversine 메서드 존재")
chk("improved = True" in tsp_src,    "[v2] 2-Opt 반복 개선 로직 존재")

CROSS_HOTEL = {"id": "ch", "name": "호텔", "lat": 37.50, "lng": 126.95, "score": 0}
CA = make_place("ca", 37.50, 127.00, "A")
CB = make_place("cb", 37.54, 127.10, "B")
CC = make_place("cc", 37.46, 127.10, "C")
CD = make_place("cd", 37.50, 127.20, "D")
o_cross, tt_cross, tot_cross = tsp.solve([CA, CB, CC, CD], CROSS_HOTEL, True, "driving")
ids_cross = [x['id'] for x in o_cross]
chk(len(o_cross) == 4,                        "2-Opt: 4개 장소 모두 반환")
chk(set(ids_cross) == {"ca","cb","cc","cd"},   "2-Opt: 4개 장소 전체 포함")
chk(len(tt_cross) == 4,                       "2-Opt: travel_times 4개")
chk(tot_cross >= 0,                           "2-Opt: total_time >= 0")
info(f"2-Opt 결과 순서: {ids_cross} / 총이동: {tot_cross//60}분")

# ════════════════════════════════════════════════════════════════
sec("Test 12 | [v2] end_point Round-trip 파라미터 검증")
# ════════════════════════════════════════════════════════════════
HOTEL_W = {"id": "hw", "name": "서쪽숙소", "lat": 37.50, "lng": 126.80, "score": 0}
_E1 = make_place("e1", 37.50, 127.05, "E1")
_E2 = make_place("e2", 37.50, 127.10, "E2")
_W1 = make_place("w1", 37.50, 126.85, "W1")

o_no, tt_no, _ = tsp.solve([_E1, _E2, _W1], HOTEL_W, True, "driving")
o_ep, tt_ep, _ = tsp.solve([_E1, _E2, _W1], HOTEL_W, True, "driving",
                            end_point=HOTEL_W)
chk(len(o_no) == 3, "end_point 미지정: 3개 반환")
chk(len(o_ep) == 3, "end_point 지정: 3개 반환 (파라미터 정상 수용)")
chk(len(tt_ep) == 3, "end_point 지정: travel_times 3개")
chk({x['id'] for x in o_ep} == {"e1","e2","w1"}, "end_point 지정: 3개 장소 전체 포함")
chk("end_point" in tsp_src,              "[v2] tsp_service에 end_point 파라미터 존재")
chk("_get_filter_n" in tsp_src,          "[v2] Dynamic TOP_N 함수 존재")
chk("find_best_meal_insertion" in tsp_src,"[v2] find_best_meal_insertion 존재")
info(f"end_point 미지정 순서: {[x['id'] for x in o_no]}")
info(f"end_point 지정 순서:  {[x['id'] for x in o_ep]}")

# ════════════════════════════════════════════════════════════════
sec("Test 13 | [v2] find_best_meal_insertion() 검증")
# ════════════════════════════════════════════════════════════════
_PREV = make_place("mp", 37.50, 127.00, "이전 관광")
_NEXT = make_place("mn", 37.50, 127.20, "다음 관광")
_M1   = make_place("m1", 37.50, 127.10, "식당A(중간)")
_M2   = make_place("m2", 37.60, 127.50, "식당B(멀리)")

best = tsp.find_best_meal_insertion([_M1, _M2], _PREV, _NEXT)
chk(best is not None,     "find_best_meal_insertion: 결과 반환")
chk(best['id'] == "m1",   f"우회 최소 식당 = M1(중간) (실제: {best['name']})")
chk(tsp.find_best_meal_insertion([], _PREV, _NEXT) is None, "빈 입력 → None")
fb = tsp.find_best_meal_insertion([_M1, _M2], None, None)
chk(fb is not None,       "기준점 없으면 첫 번째 반환 (fallback)")
chk(fb['id'] == "m1",     "fallback = 첫 번째 후보")
info(f"우회 최소 식당: {best['name']}")

# ════════════════════════════════════════════════════════════════
total_tests = p + f
print(f"\n{'='*62}")
if f == 0:
    print(f"  {G}{B}ALL {p} TESTS PASSED ✓{X}")
else:
    print(f"  {G}{p} PASS{X}  /  {R}{f} FAIL{X}  (총 {total_tests}개)")
print(f"{'='*62}\n")
sys.exit(0 if f == 0 else 1)
