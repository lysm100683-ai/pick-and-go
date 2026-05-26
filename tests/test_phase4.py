# tests/test_phase4.py
"""
Phase 4: HotelAnchorService 단위 테스트

검증 항목:
  1. hotel_anchor_service.py 직접 import 및 동작
  2. num_hotels=1 → 앵커링 없이 base_hotel 전체 반환
  3. 상황 A: 90분 초과 날 → 클러스터 중심 근처 숙소로 교체
  4. 상황 B: 전날 이동시간 비슷 → 중간 날 마지막 장소 근처 숙소로 교체
  5. 당일치기(num_days=1) → 빈 리스트 반환
  6. hotel_candidates 없을 때 → base_hotel 유지
  7. services/__init__.py export 확인
  8. itinerary_generator 코드 레벨 검증 (import 없이 AST/텍스트 검사)
"""

import sys
import os
import importlib.util

# 프로젝트 루트
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICES_DIR = os.path.join(ROOT, 'travel_logic', 'services')

# ── hotel_anchor_service만 직접 로드 (backend_postgres chain 우회) ──────
def _load_module_direct(name, filepath):
    """파일 경로로 모듈을 직접 로드 (패키지 __init__ 연쇄 import 우회)."""
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod  = importlib.util.module_from_spec(spec)
    # 상대 import를 위해 부모 패키지 경로 설정
    sys.modules.setdefault('travel_logic', type(sys)('travel_logic'))
    sys.modules.setdefault('travel_logic.config', type(sys)('travel_logic.config'))
    sys.modules.setdefault('travel_logic.services', type(sys)('travel_logic.services'))

    # constants 모듈 로드 (hotel_anchor_service가 의존)
    const_path = os.path.join(ROOT, 'travel_logic', 'config', 'constants.py')
    const_spec = importlib.util.spec_from_file_location('travel_logic.config.constants', const_path)
    const_mod  = importlib.util.module_from_spec(const_spec)
    sys.modules['travel_logic.config.constants'] = const_mod
    const_spec.loader.exec_module(const_mod)

    spec.loader.exec_module(mod)
    return mod

# 직접 로드
_ha_mod = _load_module_direct(
    'travel_logic.services.hotel_anchor_service',
    os.path.join(SERVICES_DIR, 'hotel_anchor_service.py'),
)
HotelAnchorService = _ha_mod.HotelAnchorService

# constants에서 임계치 가져오기
HOTEL_ANCHOR_TIME_THRESHOLD = sys.modules['travel_logic.config.constants'].HOTEL_ANCHOR_TIME_THRESHOLD

PASS = 0
FAIL = 0

def ok(msg):
    global PASS
    PASS += 1
    print(f"  [PASS] {msg}")

def fail(msg, detail=""):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg}" + (f" | {detail}" if detail else ""))


# ── 픽스처 ─────────────────────────────────────────────────────────────
base = {
    'id': 'hotel_base', 'name': '기본호텔',
    'lat': 33.50, 'lng': 126.50, 'rating': 4.0,
}
hotel_b = {
    'id': 'hotel_b', 'name': '앵커호텔',
    'lat': 33.65, 'lng': 126.65, 'rating': 4.0,
}
candidates = [base, hotel_b]
user_data_base = {'star_rating': 3}


# ── 테스트 1: 클래스 로드 확인 ───────────────────────────────────────────
print("\n[Test 1] HotelAnchorService 로드 및 기본 확인")
try:
    assert callable(HotelAnchorService.determine_hotels)
    assert callable(HotelAnchorService._find_nearest_hotel)
    assert callable(HotelAnchorService._haversine)
    ok("HotelAnchorService 로드 및 핵심 메서드 존재 확인")
    th = HOTEL_ANCHOR_TIME_THRESHOLD
    assert th == 90 * 60, f"임계치 오류: {th}"
    ok(f"HOTEL_ANCHOR_TIME_THRESHOLD = {th}초 (90분) 정상")
except Exception as e:
    fail("기본 확인 실패", str(e))


# ── 테스트 2: num_hotels=1 고정 ─────────────────────────────────────────
print("\n[Test 2] num_hotels=1 → 앵커링 없이 base_hotel 반환")
result = HotelAnchorService.determine_hotels(
    num_hotels=1, base_hotel=base, num_days=3,
    daily_travel_times=[[1000, 9000], [8000, 7000]],
    centroids=[(33.65, 126.65), (33.7, 126.7)],
    last_places_per_day=[None, None],
    hotel_candidates=candidates,
    user_data=user_data_base,
)
if len(result) == 2 and all(h is base for h in result):
    ok("num_hotels=1: 결과 길이=2, 모두 base_hotel (앵커링 무시)")
else:
    fail("num_hotels=1 결과 오류", f"result={[h.get('id') for h in result]}")


# ── 테스트 3: 당일치기 ──────────────────────────────────────────────────
print("\n[Test 3] num_days=1 (당일치기) → 빈 리스트 반환")
result = HotelAnchorService.determine_hotels(
    num_hotels=2, base_hotel=base, num_days=1,
    daily_travel_times=[],
    centroids=[],
    last_places_per_day=[],
    hotel_candidates=candidates,
    user_data=user_data_base,
)
if result == []:
    ok("당일치기: 빈 리스트 반환 (숙박 없음)")
else:
    fail("당일치기 결과 오류", f"result={result}")


# ── 테스트 4: 상황 A — 90분 초과 날 ────────────────────────────────────
print("\n[Test 4] 상황 A: 90분 초과 날 → 클러스터 중심 근처 숙소 교체")
over = HOTEL_ANCHOR_TIME_THRESHOLD + 1   # 5401초
result = HotelAnchorService.determine_hotels(
    num_hotels=2, base_hotel=base, num_days=3,
    daily_travel_times=[[over, 1000], [500, 600]],   # day0 초과
    centroids=[(33.65, 126.65), (33.50, 126.50)],    # day0 centroid = hotel_b 근처
    last_places_per_day=[None, None],
    hotel_candidates=candidates,
    user_data=user_data_base,
)
if len(result) == 2:
    ok(f"결과 길이 정상 (2박): [{result[0]['name']}, {result[1]['name']}]")
    if result[0]['id'] == 'hotel_b':
        ok("상황 A: day0 초과 → 1박 숙소가 클러스터 중심 근처(hotel_b)로 교체")
    else:
        fail("상황 A: 1박 숙소 교체 실패", f"got {result[0]['id']}")
    if result[1] is base:
        ok("상황 A: day1 초과 없음 → 2박 숙소는 base_hotel 유지")
    else:
        fail("상황 A: 2박 숙소 잘못 교체", f"got {result[1]['id']}")
else:
    fail("결과 길이 오류", f"len={len(result)}")


# ── 테스트 5: 상황 B — 모든 날 이동시간 비슷 ─────────────────────────────
print("\n[Test 5] 상황 B: 전날 이동시간 비슷 → 중간 날 마지막 장소 근처 숙소 교체")
# 3박 4일: mid_idx = (4-1)//2 = 1
mid_last = {'lat': 33.66, 'lng': 126.66, 'id': 'sight_x'}
result = HotelAnchorService.determine_hotels(
    num_hotels=2, base_hotel=base, num_days=4,
    daily_travel_times=[[1000, 900], [800, 1100], [950, 1050]],   # 전부 5400 미만
    centroids=[(33.50, 126.50), (33.55, 126.55), (33.60, 126.60)],
    last_places_per_day=[None, mid_last, None],
    hotel_candidates=candidates,
    user_data=user_data_base,
)
if len(result) == 3:
    ok(f"결과 길이 정상 (3박): {[h['name'] for h in result]}")
    # mid_idx=1 이후(night 1, 2)는 hotel_b (mid_last에 더 가까움)
    if result[1]['id'] == 'hotel_b' and result[2]['id'] == 'hotel_b':
        ok("상황 B: 중간(idx=1) 이후 박 모두 hotel_b로 교체")
    else:
        fail("상황 B: 교체 결과 오류", f"result[1]={result[1]['id']}, result[2]={result[2]['id']}")
    if result[0] is base:
        ok("상황 B: 중간 이전 박(0)은 base_hotel 유지")
    else:
        fail("상황 B: 이전 박이 잘못 변경됨", f"result[0]={result[0]['id']}")
else:
    fail("결과 길이 오류", f"len={len(result)}")


# ── 테스트 6: hotel_candidates 없을 때 ──────────────────────────────────
print("\n[Test 6] hotel_candidates 없을 때 → base_hotel 유지")
result = HotelAnchorService.determine_hotels(
    num_hotels=2, base_hotel=base, num_days=3,
    daily_travel_times=[[over, 1000], [500, 600]],
    centroids=[(33.65, 126.65), (33.50, 126.50)],
    last_places_per_day=[None, None],
    hotel_candidates=[],
    user_data=user_data_base,
)
if all(h is base for h in result):
    ok("candidates 빈 풀: 모든 박 base_hotel 유지 (폴백 정상)")
else:
    fail("candidates 빈 풀: 예상치 못한 교체 발생", f"result={[h.get('id') for h in result]}")


# ── 테스트 7: services/__init__.py export 텍스트 검증 ────────────────────
print("\n[Test 7] services/__init__.py 코드 레벨 검증")
init_path = os.path.join(SERVICES_DIR, '__init__.py')
with open(init_path, encoding='utf-8') as f:
    init_src = f.read()
if 'HotelAnchorService' in init_src:
    ok("services/__init__.py에 HotelAnchorService export 확인")
else:
    fail("services/__init__.py에 HotelAnchorService 없음")


# ── 테스트 8: itinerary_generator.py 코드 레벨 검증 ─────────────────────
print("\n[Test 8] itinerary_generator.py Phase 4 통합 코드 레벨 검증")
ig_path = os.path.join(ROOT, 'travel_logic', 'itinerary_generator.py')
with open(ig_path, encoding='utf-8') as f:
    ig_src = f.read()

checks = [
    ('HotelAnchorService import', 'HotelAnchorService' in ig_src),
    ('Phase 3 사전 실행 (daily_travel_times_p3)', 'daily_travel_times_p3' in ig_src),
    ('Phase 3 사전 실행 (last_places_per_day)', 'last_places_per_day' in ig_src),
    ('Phase 4 determine_hotels 호출', 'HotelAnchorService.determine_hotels(' in ig_src),
    ('night_stay_hotels 파라미터 전달', 'night_stay_hotels=night_stay_hotels' in ig_src),
    ('_generate_for_theme 시그니처에 night_stay_hotels', 'night_stay_hotels: Optional[List[Optional[Dict]]] = None' in ig_src),
    ('랜덤 샘플 제거 확인', 'random.sample(all_hotels' not in ig_src),
]
for label, cond in checks:
    if cond:
        ok(label)
    else:
        fail(label)


# ── 결과 요약 ────────────────────────────────────────────────────────────
print(f"\n{'='*55}")
print(f"  결과: PASS {PASS} / FAIL {FAIL} / TOTAL {PASS + FAIL}")
print(f"{'='*55}")
if FAIL == 0:
    print("  [ALL PASS] Phase 4 구현 검증 완료")
else:
    print("  [FAIL 존재] 위 항목 확인 필요")
    sys.exit(1)
