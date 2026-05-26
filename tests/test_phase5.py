# tests/test_phase5.py
"""
Phase 5: 최종 경로 + 타임박싱 독립 테스트

검증 항목:
  (1) PACE Cut-off: 일정 강도별 하루 최대 관광지 방문 수 제한
  (2) 동행자별 체류시간 배율 (부모님 x1.2, 아이 x1.3)
  (3) 시간 Cut-off: 밤 11시(23시) 이후 도착 예정 장소 스킵
  (4) 대중교통 막차: transit 모드 22시 이후 이동 시작 제한
  (5) stay_multiplier 계산 로직 (with_kids + companions 중 최댓값)
  (6) 상수 정의 일관성
"""

import sys
import os
import math
from datetime import datetime, timedelta, time, date

# 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# constants.py 를 importlib 로 직접 로드 (geoalchemy2 의존성 우회)
import importlib.util

_constants_path = os.path.join(parent_dir, "travel_logic", "config", "constants.py")
_spec = importlib.util.spec_from_file_location("constants", _constants_path)
_constants = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_constants)

PACE_MAX_PLACES           = _constants.PACE_MAX_PLACES
COMPANION_STAY_MULTIPLIER = _constants.COMPANION_STAY_MULTIPLIER
CUTOFF_HOUR               = _constants.CUTOFF_HOUR
TRANSIT_LAST_HOUR         = _constants.TRANSIT_LAST_HOUR
VISIT_TIMES               = _constants.VISIT_TIMES


# ─────────────────────────────────────────────────────────────────────
#  헬퍼 함수
# ─────────────────────────────────────────────────────────────────────

def _get_max_sights(pace: str) -> int:
    """PACE_MAX_PLACES 에서 최대 관광지 수 추출"""
    limit = PACE_MAX_PLACES.get(pace, (2, 3))
    return limit if isinstance(limit, int) else limit[1]


def _get_stay_multiplier(companions: list, with_kids: bool = False) -> float:
    """동행자 배율 계산 (itinerary_generator 와 동일 로직)"""
    multiplier = COMPANION_STAY_MULTIPLIER.get('default', 1.0)
    for key, val in COMPANION_STAY_MULTIPLIER.items():
        if key != 'default' and key in companions:
            multiplier = max(multiplier, val)
    if with_kids:
        multiplier = max(multiplier, COMPANION_STAY_MULTIPLIER.get('\uc544\uc774 \ub3d9\ubc18', 1.3))
    return multiplier


def _would_skip_cutoff(current_hour: int, travel_seconds: int, mode: str) -> bool:
    """
    Phase 5 시간 Cut-off 시뮬레이션.
    current_hour 시각에서 travel_seconds 이동 후 스킵 여부 반환.
    - 다음 날(자정 초과)에 도착하면 무조건 스킵
    - 당일 23시 이후 도착이면 스킵
    - transit 모드: 22시 이후 이동 시작이면 스킵
    """
    current_time = datetime.combine(date.today(), time(current_hour, 0, 0))

    # (a) 대중교통 막차 체크
    if mode == 'transit' and current_time.hour >= TRANSIT_LAST_HOUR:
        return True

    # (b) 도착 예정 시각 체크 (날짜 바뀜 = 다음날 = 반드시 스킵)
    arrival = current_time + timedelta(seconds=travel_seconds)
    if arrival.date() > current_time.date():   # 자정 넘어 다음 날
        return True
    if arrival.hour >= CUTOFF_HOUR:
        return True

    return False


# ─────────────────────────────────────────────────────────────────────
#  테스트 케이스
# ─────────────────────────────────────────────────────────────────────

def test_constants_sanity():
    """(6) 상수 정의 일관성 검증"""
    print("\n[TEST-6] Phase 5 상수 정의 검증")

    assert CUTOFF_HOUR == 23,          f"CUTOFF_HOUR=23 예상, 실제={CUTOFF_HOUR}"
    assert TRANSIT_LAST_HOUR == 22,    f"TRANSIT_LAST_HOUR=22 예상, 실제={TRANSIT_LAST_HOUR}"
    assert TRANSIT_LAST_HOUR < CUTOFF_HOUR, "막차 시간이 Cut-off 보다 앞서야 함"
    assert COMPANION_STAY_MULTIPLIER.get('\ub3d9\ubc18\uc778 \uc608\uc2dc\uc6a9', 1.0) == 1.0  # 없는 키는 default

    parent_mult  = COMPANION_STAY_MULTIPLIER.get('\ubd80\ubaa8\ub2d8 \ub3d9\ubc18', 0)
    child_mult   = COMPANION_STAY_MULTIPLIER.get('\uc544\uc774 \ub3d9\ubc18', 0)
    default_mult = COMPANION_STAY_MULTIPLIER.get('default', 0)
    assert abs(parent_mult  - 1.2) < 1e-9, f"부모님 동반 배율 1.2 예상, 실제={parent_mult}"
    assert abs(child_mult   - 1.3) < 1e-9, f"아이 동반 배율 1.3 예상, 실제={child_mult}"
    assert abs(default_mult - 1.0) < 1e-9, f"default 배율 1.0 예상, 실제={default_mult}"

    print(f"  CUTOFF_HOUR       = {CUTOFF_HOUR}  [OK]")
    print(f"  TRANSIT_LAST_HOUR = {TRANSIT_LAST_HOUR}  [OK]")
    print(f"  부모님 동반 배율   = {parent_mult}x  [OK]")
    print(f"  아이 동반 배율     = {child_mult}x  [OK]")
    print(f"  default 배율      = {default_mult}x  [OK]")


def test_pace_cutoff_values():
    """(1-A) PACE_MAX_PLACES 상수가 plan.md 기준과 일치하는지 확인"""
    print("\n[TEST-1A] PACE Cut-off 상수 검증")

    assert _get_max_sights("여유")     == 2, "여유: 최대 2곳이어야 함"
    assert _get_max_sights("여유롭게") == 2, "여유롭게: 최대 2곳이어야 함"
    assert _get_max_sights("보통")     == 3, "보통: 최대 3곳이어야 함"
    assert _get_max_sights("알차게")   == 4, "알차게: 최대 4곳이어야 함"
    assert _get_max_sights("빡빡")     == 4, "빡빡: 최대 4곳이어야 함"

    for pace, limit in PACE_MAX_PLACES.items():
        max_v = limit if isinstance(limit, int) else limit[1]
        min_v = limit if isinstance(limit, int) else limit[0]
        print(f"  pace='{pace}': {min_v}~{max_v}곳/일  [OK]")


def test_pace_cutoff_simulation():
    """(1-B) PACE Cut-off 시뮬레이션: 카운터 기반 스킵 로직 검증"""
    print("\n[TEST-1B] PACE Cut-off 시뮬레이션")

    # 여유 모드: 최대 2곳
    max_sights = _get_max_sights("여유")
    counter, skipped = 0, []
    for i in range(5):
        if counter >= max_sights:
            skipped.append(i)
        else:
            counter += 1
    assert counter == 2,    f"여유: 방문 2곳 예상, 실제={counter}"
    assert len(skipped) == 3, f"여유: 스킵 3번 예상, 실제={len(skipped)}"
    print("  여유 모드: 2곳 방문 후 3곳 스킵  [OK]")

    # 알차게 모드: 최대 4곳
    max_sights = _get_max_sights("알차게")
    counter, skipped = 0, []
    for i in range(5):
        if counter >= max_sights:
            skipped.append(i)
        else:
            counter += 1
    assert counter == 4,    f"알차게: 방문 4곳 예상, 실제={counter}"
    assert len(skipped) == 1, f"알차게: 스킵 1번 예상, 실제={len(skipped)}"
    print("  알차게 모드: 4곳 방문 후 1곳 스킵  [OK]")


def test_companion_stay_multiplier():
    """(2) 동행자별 체류시간 배율 검증"""
    print("\n[TEST-2] 동행자별 체류시간 배율 검증")

    cases = [
        ([],                         False, 1.0, "기본 (없음)"),
        (['\ubd80\ubaa8\ub2d8 \ub3d9\ubc18'], False, 1.2, "부모님 동반"),
        (['\uc544\uc774 \ub3d9\ubc18'],   False, 1.3, "아이 동반"),
        ([],                         True,  1.3, "with_kids=True"),
        (['\ubd80\ubaa8\ub2d8 \ub3d9\ubc18', '\uc544\uc774 \ub3d9\ubc18'], False, 1.3, "부모님+아이(최댓값)"),
        (['\uce5c\uad6c'],                False, 1.0, "친구 동반(목록없음)"),
    ]

    for companions, with_kids, expected, label in cases:
        actual = _get_stay_multiplier(companions, with_kids)
        assert abs(actual - expected) < 1e-9, \
            f"'{label}': 예상={expected}, 실제={actual}"
        print(f"  '{label}': {actual}x  [OK]")


def test_visit_time_with_multiplier():
    """(2-B) 체류시간 배율이 실제 수치에 올바르게 곱해지는지 검증"""
    print("\n[TEST-2B] 체류시간 배율 수치 검증")

    base_sight = VISIT_TIMES['\uad00\uad11']  # 9000초 (2.5h)
    base_food  = VISIT_TIMES['\uc2dd\uc0ac']  # 5400초 (1.5h)

    for companions, with_kids in [
        ([], False),
        (['\ubd80\ubaa8\ub2d8 \ub3d9\ubc18'], False),
        (['\uc544\uc774 \ub3d9\ubc18'],   False),
        ([], True),
    ]:
        m = _get_stay_multiplier(companions, with_kids)
        v = int(base_sight * m)
        f = int(base_food  * m)
        print(f"  {m}x  |  관광={v//3600:.1f}h  |  식사={f//3600:.1f}h")

    assert int(base_sight * 1.2) == 10800, "부모님 동반: 관광지 체류 10800초 예상"
    assert int(base_sight * 1.3) == 11700, "아이 동반: 관광지 체류 11700초 예상"
    print("  수치 검증  [OK]")


def test_cutoff_hour_driving():
    """(3) 자차 모드 23시 Cut-off 검증"""
    print("\n[TEST-3] Driving 모드 23시 Cut-off 검증")

    cases = [
        (22, 1800, 'driving', False, "22:00 + 30분 = 22:30 -> 통과"),
        (22, 5400, 'driving', True,  "22:00 + 90분 = 23:30 -> 스킵"),
        (21, 3600, 'driving', False, "21:00 + 60분 = 22:00 -> 통과"),
        (22, 7200, 'driving', True,  "22:00 + 120분 = 00:00(다음날) -> 스킵"),
        (20, 9000, 'driving', False, "20:00 + 150분 = 22:30 -> 통과"),
    ]

    for start_hour, travel_sec, mode, expect_skip, label in cases:
        actual_skip = _would_skip_cutoff(start_hour, travel_sec, mode)
        assert actual_skip == expect_skip, \
            f"'{label}': 예상 skip={expect_skip}, 실제={actual_skip}"
        status = "SKIP" if actual_skip else "PASS"
        print(f"  {label}  [{status}]")


def test_transit_last_hour():
    """(4) 대중교통 모드 22시 막차 제한 검증"""
    print("\n[TEST-4] Transit 모드 22시 막차 제한 검증")

    cases = [
        (21, 'transit', False, "21:00 이동 -> 통과"),
        (22, 'transit', True,  "22:00 이동 -> 스킵(막차)"),
        (23, 'transit', True,  "23:00 이동 -> 스킵(막차)"),
        (22, 'driving', False, "22:00 driving -> 통과(막차제한없음)"),
    ]

    for start_hour, mode, expect_skip, label in cases:
        actual_skip = _would_skip_cutoff(start_hour, 0, mode)
        assert actual_skip == expect_skip, \
            f"'{label}': 예상 skip={expect_skip}, 실제={actual_skip}"
        status = "SKIP" if actual_skip else "PASS"
        print(f"  {label}  [{status}]")


def test_pace_all_levels_coverage():
    """(1-C) PACE_MAX_PLACES 전체 레벨 커버리지"""
    print("\n[TEST-1C] PACE_MAX_PLACES 전체 레벨 커버리지")

    required_paces = ["여유", "여유롭게", "보통", "알차게", "빡빡"]
    for pace in required_paces:
        assert pace in PACE_MAX_PLACES, f"'{pace}' 레벨이 PACE_MAX_PLACES에 없음"
        limit = PACE_MAX_PLACES[pace]
        max_v = limit if isinstance(limit, int) else limit[1]
        min_v = limit if isinstance(limit, int) else limit[0]
        assert max_v >= min_v >= 1, f"'{pace}' 값 이상: min={min_v}, max={max_v}"
        print(f"  pace='{pace}': {min_v}~{max_v}곳/일  [OK]")


def test_timebox_edge_cases():
    """(3-B) 경계값 테스트: 정확히 23:00 도착, 22:00 이동 등"""
    print("\n[TEST-3B] 경계값 테스트")

    # 정확히 23:00 도착 -> 스킵 (hour >= 23)
    skip = _would_skip_cutoff(22, 3600, 'driving')
    assert skip is True, "23:00 도착: 스킵 예상"
    print("  22:00 + 60분 = 23:00 -> SKIP  [OK]")

    # 22:59 도착 -> 통과 (hour == 22 < 23)
    skip = _would_skip_cutoff(22, 3540, 'driving')
    assert skip is False, "22:59 도착: 통과 예상"
    print("  22:00 + 59분 = 22:59 -> PASS  [OK]")

    # transit 21:00 이동 -> 통과
    skip = _would_skip_cutoff(21, 3540, 'transit')
    assert skip is False, "transit 21:00 이동: 통과 예상"
    print("  transit 21:00 이동 -> PASS  [OK]")

    # transit 22:00 이동 -> 스킵
    skip = _would_skip_cutoff(22, 0, 'transit')
    assert skip is True, "transit 22:00 이동: 스킵 예상"
    print("  transit 22:00 이동 -> SKIP  [OK]")


# ─────────────────────────────────────────────────────────────────────
#  실행 엔트리포인트
# ─────────────────────────────────────────────────────────────────────

def run_all_tests():
    tests = [
        test_constants_sanity,
        test_pace_cutoff_values,
        test_pace_cutoff_simulation,
        test_companion_stay_multiplier,
        test_visit_time_with_multiplier,
        test_cutoff_hour_driving,
        test_transit_last_hour,
        test_pace_all_levels_coverage,
        test_timebox_edge_cases,
    ]

    passed, failed, errors = 0, 0, []

    print("=" * 60)
    print("  Phase 5 Timebox Standalone Test")
    print("=" * 60)

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            failed += 1
            errors.append((test_fn.__name__, str(e)))
            print(f"  [FAIL] {test_fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            errors.append((test_fn.__name__, f"ERROR: {e}"))
            print(f"  [ERROR] {test_fn.__name__}: {e}")

    print("\n" + "=" * 60)
    print(f"  Result: {passed}/{len(tests)} passed  |  Failed: {failed}")
    print("=" * 60)

    if errors:
        print("\nFailed list:")
        for name, msg in errors:
            print(f"  - {name}: {msg}")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
