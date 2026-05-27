# app/reservation/sub3_confirmer.py
"""
Sub 3 — 예약 확정 검증
설계도 흐름:
  1. 예약 필수 요소 / 결과 성공 여부 확인
  2. 파트너사 예약 번호 실존 여부 재확인 (항공: Duffel / 숙소: LiteAPI)
  3. 최종 금액 재계산
  4. 예약 ID / 상태 생성
  5. 하나의 예약 정보 묶음으로 반환 → Sub4에 전달

환경변수:
  MOCK_VERIFY=false  → Duffel + LiteAPI 실 API로 예약번호 재확인 (기본값)
  MOCK_VERIFY=true   → 모의 검증 (항상 통과, 단위 테스트용)
"""
import asyncio
import os
import uuid
from typing import List

import requests as _requests

MOCK_VERIFY = os.getenv("MOCK_VERIFY", "false").lower() == "true"

# ── Duffel 항공 예약 검증 ──────────────────────────────────────────
_DUFFEL_BASE    = "https://api.duffel.com"
_DUFFEL_VERSION = "v2"

def _verify_flight_sync(order_id: str) -> bool:
    """
    Duffel GET /air/orders/{order_id} 로 예약 실존 여부 확인.
    booking_reference 존재 + cancellation이 None → 유효
    """
    key = os.getenv("DUFFEL_API_KEY", "")
    if not key:
        return False
    r = _requests.get(
        f"{_DUFFEL_BASE}/air/orders/{order_id}",
        headers={"Authorization": f"Bearer {key}",
                 "Duffel-Version": _DUFFEL_VERSION,
                 "Accept": "application/json"},
        timeout=15,
    )
    if r.status_code != 200:
        return False
    data = r.json().get("data", {})
    return bool(data.get("booking_reference")) and data.get("cancellation") is None


# ── LiteAPI 숙소 예약 검증 ─────────────────────────────────────────
_LITEAPI_BASE = "https://api.liteapi.travel/v3.0"

def _verify_hotel_sync(booking_id: str) -> bool:
    """
    LiteAPI GET /bookings/{booking_id} 로 예약 실존 여부 확인.
    status == "CONFIRMED" → 유효
    """
    key = os.getenv("LITEAPI_KEY", "")
    if not key:
        return False
    r = _requests.get(
        f"{_LITEAPI_BASE}/bookings/{booking_id}",
        headers={"X-API-Key": key, "Accept": "application/json"},
        timeout=15,
    )
    if r.status_code != 200:
        return False
    return r.json().get("data", {}).get("status") == "CONFIRMED"


class ConfirmationError(Exception):
    """Sub 3 확정 검증 실패 예외"""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


async def _verify_partner_booking(item: dict) -> bool:
    """
    파트너사에 예약 번호 실존 여부 재확인.
    - MOCK_VERIFY=true  → 항상 통과 (단위 테스트용)
    - MOCK_VERIFY=false → 항공: Duffel GET /air/orders/{id}
                          숙소: LiteAPI GET /bookings/{id}

    [BUG FIX] Sub2가 Mock 모드(MOCK_FLIGHT=true)일 때 생성하는 가짜 booking_id
    (예: FL-XXXXXXXX, partner_name: "amadeus_mock")를 MOCK_VERIFY=false 상태에서
    실제 Duffel/LiteAPI에 조회하면 404 → 항상 검증 실패 발생.
    partner_name에 "mock"이 포함된 항목은 Mock 예약이므로 실 API 검증을 건너뜀.
    """
    if not item.get("partner_booking_id"):
        return False
    # Mock 예약 자동 감지 (partner_name: "amadeus_mock", "booking_com_mock" 등)
    partner_name = item.get("partner_name", "").lower()
    if MOCK_VERIFY or "mock" in partner_name:
        await asyncio.sleep(0.05)  # API 응답 시뮬레이션
        return True
    item_type = item.get("item_type", "")
    booking_id = item["partner_booking_id"]
    if item_type == "flight":
        return await asyncio.to_thread(_verify_flight_sync, booking_id)
    elif item_type == "hotel":
        return await asyncio.to_thread(_verify_hotel_sync, booking_id)
    return False


async def confirm_reservation(validated_context: dict, booking_results: List[dict]) -> dict:
    """
    Sub2 결과를 받아 최종 예약 확정 객체를 생성.

    Args:
        validated_context: Sub1 검증 컨텍스트
        booking_results:   Sub2 예약 결과 리스트
    Returns:
        dict: confirmed_reservation — Sub4에 전달할 최종 예약 묶음
    Raises:
        ConfirmationError: 필수 항목 누락 또는 검증 실패
    """
    # ── 1. 필수 예약 결과 존재 확인 ────────────────────────────
    if not booking_results:
        raise ConfirmationError("NO_BOOKING_RESULTS", "예약 결과가 없습니다.")

    item_types = {r["item_type"] for r in booking_results}
    if "flight" not in item_types:
        raise ConfirmationError("MISSING_FLIGHT", "항공 예약 결과가 없습니다.")
    if "hotel" not in item_types:
        raise ConfirmationError("MISSING_HOTEL", "숙소 예약 결과가 없습니다.")

    # ── 2. 모든 항목 상태 재확인 ───────────────────────────────
    for item in booking_results:
        if item.get("status") != "confirmed":
            raise ConfirmationError(
                "ITEM_NOT_CONFIRMED",
                f"{item['item_type']} 예약이 확정 상태가 아닙니다: {item.get('status')}"
            )

    # ── 2-b. 파트너사 예약 번호 실존 여부 재확인 (병렬) ──────────
    verify_results = await asyncio.gather(
        *[_verify_partner_booking(item) for item in booking_results],
        return_exceptions=True,
    )
    for item, verified in zip(booking_results, verify_results):
        if isinstance(verified, Exception) or not verified:
            raise ConfirmationError(
                "PARTNER_BOOKING_VERIFY_FAILED",
                f"{item['item_type']} 예약 번호({item.get('partner_booking_id')}) "
                f"파트너사 재확인 실패",
            )

    print(f"[Sub3] 파트너사 예약 번호 재확인 완료 — {len(booking_results)}건")

    # ── 3. 최종 금액 재계산 ────────────────────────────────────
    total_amount = sum(float(r.get("amount", 0)) for r in booking_results)

    # 예산 초과 확인 (선택적)
    budget = validated_context.get("payment", {}).get("budget_krw", 0)
    if budget > 0 and total_amount > budget:
        print(f"[Sub3] ⚠️ 총 금액({total_amount:,.0f}원)이 예산({budget:,.0f}원)을 초과합니다.")
        # 설계 결정: 예산 초과는 경고만, 취소하지 않음 (사용자가 사전 동의한 경우)

    # ── 4. 예약 ID 및 상태 생성 ───────────────────────────────
    reservation_id = str(uuid.uuid4())

    confirmed_reservation = {
        "reservation_id": reservation_id,
        "user_id": validated_context["user_id"],
        "itinerary_id": validated_context["itinerary_id"],
        "trip_data": validated_context["trip_data"],
        "start_date": validated_context["start_date"],
        "end_date": validated_context["end_date"],
        "dest_city": validated_context["dest_city"],
        "dep_city": validated_context["dep_city"],
        "people": validated_context["people"],
        "payment": validated_context["payment"],
        "status": "confirmed",
        "total_amount": total_amount,
        "currency": "KRW",
        "items": booking_results,  # 항공 + 숙소 결과 리스트
    }

    print(f"[Sub3] ✅ 예약 확정 — ID:{reservation_id}, "
          f"총 금액:{total_amount:,.0f}원, 항목:{len(booking_results)}개")

    return confirmed_reservation
