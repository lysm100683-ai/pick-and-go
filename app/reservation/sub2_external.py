# app/reservation/sub2_external.py
"""
Sub 2 — 외부 예약 연동 관리부
설계도 흐름:
  1. 예약이 필요한 일정 요소 분리 (항공 + 숙소)
  2. 예약 파트너 API 형식으로 데이터 변환
  3. asyncio.gather()로 병렬 예약 시도 (항공 + 숙소 동시)
  4. 성공/실패 분리
  5. 하나라도 실패 → 이미 성공한 것도 취소(롤백) → 전체 실패 반환
  6. 모두 성공 → 예약 결과 리스트 반환

환경변수:
  MOCK_FLIGHT=true  → Mock 항공 예약 사용 (기본값)
  MOCK_HOTEL=true   → Mock 숙소 예약 사용 (기본값)
"""
import asyncio
import os
import uuid
import random
from typing import List, Dict, Any


MOCK_FLIGHT = os.getenv("MOCK_FLIGHT", "true").lower() == "true"
MOCK_HOTEL  = os.getenv("MOCK_HOTEL",  "true").lower() == "true"

# Mock 성공률 (테스트용 — 환경변수로 조정 가능)
MOCK_FLIGHT_SUCCESS_RATE = float(os.getenv("MOCK_FLIGHT_SUCCESS_RATE", "0.95"))
MOCK_HOTEL_SUCCESS_RATE  = float(os.getenv("MOCK_HOTEL_SUCCESS_RATE",  "0.95"))


class BookingFailedError(Exception):
    """Sub 2 예약 실패 예외 (롤백 완료 포함)"""
    def __init__(self, failed_items: List[str], message: str, retryable: bool = True):
        self.failed_items = failed_items
        self.message = message
        self.retryable = retryable
        super().__init__(message)


# ── Mock API 함수들 ────────────────────────────────────────────────

async def _mock_book_flight(context: dict) -> dict:
    """
    Mock 항공 예약 (Amadeus API 대체)
    실제 연동 시 이 함수만 교체하면 됨
    """
    await asyncio.sleep(random.uniform(0.3, 1.2))  # API 응답 시뮬레이션

    success = random.random() < MOCK_FLIGHT_SUCCESS_RATE
    if success:
        return {
            "item_type": "flight",
            "partner_name": "amadeus_mock",
            "partner_booking_id": f"FL-{uuid.uuid4().hex[:8].upper()}",
            "status": "confirmed",
            "amount": random.randint(150_000, 600_000) * context.get("people", 1),
            "currency": "KRW",
            "details": {
                "flight_no": f"KE{random.randint(100, 999)}",
                "dep": context.get("dep_city", "ICN"),
                "arr": context.get("dest_city", "NRT"),
                "departure_date": context.get("start_date"),
                "return_date": context.get("end_date"),
                "seats": context.get("people", 1),
                "class": "Economy",
            },
            "error_msg": None,
        }
    else:
        return {
            "item_type": "flight",
            "partner_name": "amadeus_mock",
            "partner_booking_id": None,
            "status": "failed",
            "amount": 0,
            "currency": "KRW",
            "details": {},
            "error_msg": "항공편 좌석 부족 또는 일시적 오류 (Mock)",
        }


async def _mock_book_hotel(context: dict) -> dict:
    """
    Mock 숙소 예약 (Booking.com API 대체)
    실제 연동 시 이 함수만 교체하면 됨
    """
    await asyncio.sleep(random.uniform(0.2, 1.0))  # API 응답 시뮬레이션

    success = random.random() < MOCK_HOTEL_SUCCESS_RATE
    if success:
        return {
            "item_type": "hotel",
            "partner_name": "booking_com_mock",
            "partner_booking_id": f"HT-{uuid.uuid4().hex[:8].upper()}",
            "status": "confirmed",
            "amount": random.randint(80_000, 300_000) * context.get("duration", 1),
            "currency": "KRW",
            "details": {
                "hotel_name": f"{context.get('dest_city', '여행지')} 대표 호텔 (Mock)",
                "check_in": context.get("start_date"),
                "check_out": context.get("end_date"),
                "nights": context.get("duration", 1),
                "rooms": max(1, context.get("people", 1) // 2),
            },
            "error_msg": None,
        }
    else:
        return {
            "item_type": "hotel",
            "partner_name": "booking_com_mock",
            "partner_booking_id": None,
            "status": "failed",
            "amount": 0,
            "currency": "KRW",
            "details": {},
            "error_msg": "숙소 객실 소진 또는 일시적 오류 (Mock)",
        }


async def _cancel_item(item: dict) -> None:
    """
    예약 취소 API 호출 (롤백용)
    실제 연동 시 파트너사 취소 API 호출로 교체
    """
    if item.get("partner_booking_id"):
        await asyncio.sleep(0.1)  # 취소 API 시뮬레이션
        print(f"[Sub2] 🔄 롤백: {item['item_type']} {item['partner_booking_id']} 취소 처리")


# ── 메인 함수 ──────────────────────────────────────────────────────

async def book_parallel(validated_context: dict) -> List[dict]:
    """
    항공 + 숙소를 asyncio.gather()로 병렬 예약 시도.
    하나라도 실패 시 성공한 항목을 롤백하고 BookingFailedError 발생.

    Args:
        validated_context: Sub1에서 반환된 검증 완료 컨텍스트
    Returns:
        List[dict]: 모든 예약 성공 시 결과 리스트 (flight + hotel)
    Raises:
        BookingFailedError: 하나 이상 실패 (롤백 완료)
    """
    print(f"[Sub2] 🚀 병렬 예약 시작 — {validated_context['dep_city']} → "
          f"{validated_context['dest_city']}, {validated_context['people']}명")

    # 1. 병렬 예약 시도
    flight_coro = _mock_book_flight(validated_context) if MOCK_FLIGHT else _real_book_flight(validated_context)
    hotel_coro  = _mock_book_hotel(validated_context)  if MOCK_HOTEL  else _real_book_hotel(validated_context)

    results: list = await asyncio.gather(flight_coro, hotel_coro, return_exceptions=True)

    # 2. 예외 처리 (네트워크 오류 등)
    booking_results = []
    for r in results:
        if isinstance(r, Exception):
            booking_results.append({
                "item_type": "unknown",
                "partner_name": "unknown",
                "status": "failed",
                "amount": 0,
                "currency": "KRW",
                "details": {},
                "error_msg": f"예외 발생: {str(r)}",
            })
        else:
            booking_results.append(r)

    # 3. 성공/실패 분리
    succeeded = [r for r in booking_results if r["status"] == "confirmed"]
    failed    = [r for r in booking_results if r["status"] != "confirmed"]

    print(f"[Sub2] 결과 — 성공: {[r['item_type'] for r in succeeded]}, "
          f"실패: {[r['item_type'] for r in failed]}")

    # 4. 하나라도 실패 → 전체 롤백 (Saga 보상 트랜잭션)
    if failed:
        if succeeded:
            print(f"[Sub2] ⚠️ 일부 실패 감지 → 성공 항목 롤백 시작")
            rollback_tasks = [_cancel_item(item) for item in succeeded]
            await asyncio.gather(*rollback_tasks, return_exceptions=True)
            print(f"[Sub2] 롤백 완료")

        failed_types = [r["item_type"] for r in failed]
        raise BookingFailedError(
            failed_items=failed_types,
            message=f"예약 실패: {', '.join([r.get('error_msg','') for r in failed])}",
            retryable=True,
        )

    print(f"[Sub2] ✅ 전체 예약 성공")
    return booking_results


# ── 실제 API 연동 스텁 (Phase 2용) ────────────────────────────────

async def _real_book_flight(context: dict) -> dict:
    """
    실제 Amadeus API 연동 (Phase 2)
    환경변수 MOCK_FLIGHT=false 설정 시 활성화
    """
    raise NotImplementedError("Amadeus API 연동은 Phase 2에서 구현 예정입니다.")


async def _real_book_hotel(context: dict) -> dict:
    """
    실제 Booking.com API 연동 (Phase 2)
    환경변수 MOCK_HOTEL=false 설정 시 활성화
    """
    raise NotImplementedError("Booking.com API 연동은 Phase 2에서 구현 예정입니다.")
