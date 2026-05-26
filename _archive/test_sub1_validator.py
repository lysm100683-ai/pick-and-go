"""
Sub1 예약 검증부 독립 테스트
DB나 외부 API 없이 순수 로직만 테스트합니다.

실행:
    python test_sub1_validator.py
"""
import asyncio
import sys
import os
from datetime import date, timedelta

# 경로 설정
sys.path.insert(0, os.path.dirname(__file__))

from app.models import ReservationRequest, PaymentInfo
from app.reservation.sub1_validator import validate_reservation, ReservationValidationError

# ── 내일 날짜 기준 (과거 날짜 오류 방지) ───────────────────────
TOMORROW   = str(date.today() + timedelta(days=1))
NEXT_WEEK  = str(date.today() + timedelta(days=7))
YESTERDAY  = str(date.today() - timedelta(days=1))

# ── 결과 집계 ──────────────────────────────────────────────────
results = {"pass": 0, "fail": 0}

def check(name: str, passed: bool, detail: str = ""):
    icon = "✅" if passed else "❌"
    print(f"  {icon} [{name}] {detail}")
    if passed:
        results["pass"] += 1
    else:
        results["fail"] += 1


# ── 헬퍼: 기본 유효 요청 생성 ────────────────────────────────
def valid_req(**overrides) -> ReservationRequest:
    defaults = dict(
        user_id      = "user_001",
        trip_data    = {"theme": "힐링", "days": []},
        start_date   = TOMORROW,
        end_date     = NEXT_WEEK,
        dest_city    = "도쿄",
        dep_city     = "서울",
        people       = 2,
        payment      = PaymentInfo(method="card", budget_krw=1_500_000),
    )
    defaults.update(overrides)
    return ReservationRequest(**defaults)


# ── 테스트 케이스들 ────────────────────────────────────────────

async def test_valid_request():
    """TC-01: 정상 요청 → 검증 통과"""
    print("\n[TC-01] 정상 요청 → 검증 통과")
    try:
        ctx = await validate_reservation(valid_req())
        ok = (
            ctx["user_id"] == "user_001"
            and ctx["dest_city"] == "도쿄"
            and ctx["duration"] == 7
            and ctx["people"] == 2
        )
        check("user_id 확인",   ctx["user_id"] == "user_001")
        check("dest_city 확인", ctx["dest_city"] == "도쿄")
        check("duration 계산",  ctx["duration"] == 7, f"duration={ctx['duration']}")
        check("people 확인",    ctx["people"] == 2)
    except ReservationValidationError as e:
        check("예상치 못한 검증 실패", False, f"{e.code}: {e.message}")


async def test_missing_user_id():
    """TC-02: user_id 없음 → MISSING_USER_ID"""
    print("\n[TC-02] user_id 누락 → MISSING_USER_ID 오류")
    try:
        await validate_reservation(valid_req(user_id="   "))
        check("오류 미발생 (실패)", False, "ValidationError가 발생해야 함")
    except ReservationValidationError as e:
        check("MISSING_USER_ID 코드", e.code == "MISSING_USER_ID", f"code={e.code}")
        check("retryable=False",      e.retryable == False)


async def test_missing_trip_data():
    """TC-03: trip_data 없음 → MISSING_TRIP_DATA"""
    print("\n[TC-03] trip_data 누락 → MISSING_TRIP_DATA 오류")
    try:
        await validate_reservation(valid_req(trip_data={}))
        check("오류 미발생 (실패)", False, "ValidationError가 발생해야 함")
    except ReservationValidationError as e:
        check("MISSING_TRIP_DATA 코드", e.code == "MISSING_TRIP_DATA", f"code={e.code}")


async def test_past_date():
    """TC-04: 출발일이 과거 → PAST_DATE"""
    print("\n[TC-04] 출발일이 어제 → PAST_DATE 오류")
    try:
        await validate_reservation(valid_req(start_date=YESTERDAY, end_date=NEXT_WEEK))
        check("오류 미발생 (실패)", False, "ValidationError가 발생해야 함")
    except ReservationValidationError as e:
        check("PAST_DATE 코드", e.code == "PAST_DATE", f"code={e.code}")


async def test_invalid_date_range():
    """TC-05: 종료일 < 시작일 → INVALID_DATE_RANGE"""
    print("\n[TC-05] 종료일이 시작일보다 이전 → INVALID_DATE_RANGE 오류")
    try:
        await validate_reservation(valid_req(start_date=NEXT_WEEK, end_date=TOMORROW))
        check("오류 미발생 (실패)", False, "ValidationError가 발생해야 함")
    except ReservationValidationError as e:
        check("INVALID_DATE_RANGE 코드", e.code == "INVALID_DATE_RANGE", f"code={e.code}")


async def test_invalid_people():
    """TC-06: 인원 0명 → INVALID_PEOPLE_COUNT"""
    print("\n[TC-06] 인원 0명 → Pydantic 검증 오류")
    try:
        req = valid_req(people=0)
        check("people=0 거부됨", False, "Pydantic ge=1이 막아야 함")
    except Exception as e:
        check("Pydantic 검증으로 거부", True, type(e).__name__)


async def test_invalid_payment_method():
    """TC-07: 잘못된 결제 수단 → INVALID_PAYMENT_METHOD"""
    print("\n[TC-07] 결제 수단 'bitcoin' → INVALID_PAYMENT_METHOD 오류")
    try:
        await validate_reservation(valid_req(
            payment=PaymentInfo(method="bitcoin", budget_krw=0)
        ))
        check("오류 미발생 (실패)", False, "ValidationError가 발생해야 함")
    except ReservationValidationError as e:
        check("INVALID_PAYMENT_METHOD 코드", e.code == "INVALID_PAYMENT_METHOD", f"code={e.code}")


async def test_invalid_date_format():
    """TC-08: 날짜 형식 오류 → INVALID_DATE_FORMAT"""
    print("\n[TC-08] 날짜 형식 오류 '2026/06/01' → INVALID_DATE_FORMAT")
    try:
        await validate_reservation(valid_req(start_date="2026/06/01"))
        check("오류 미발생 (실패)", False, "ValidationError가 발생해야 함")
    except ReservationValidationError as e:
        check("INVALID_DATE_FORMAT 코드", e.code == "INVALID_DATE_FORMAT", f"code={e.code}")
    except Exception as e:
        # Pydantic이 먼저 잡을 수도 있음
        check("형식 오류 거부됨", True, type(e).__name__)


# ── 메인 실행 ─────────────────────────────────────────────────

async def main():
    print("=" * 55)
    print("  Sub1 예약 검증부 (sub1_validator.py) 테스트")
    print("=" * 55)

    await test_valid_request()
    await test_missing_user_id()
    await test_missing_trip_data()
    await test_past_date()
    await test_invalid_date_range()
    await test_invalid_people()
    await test_invalid_payment_method()
    await test_invalid_date_format()

    print("\n" + "=" * 55)
    print(f"  결과: {results['pass']}개 통과 / {results['fail']}개 실패")
    print("=" * 55)

    if results["fail"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
