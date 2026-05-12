# app/reservation/sub3_confirmer.py
"""
Sub 3 — 예약 확정 검증
설계도 흐름:
  1. 예약 필수 요소 / 결과 성공 여부 확인
  2. 최종 금액 재계산
  3. 예약 ID / 상태 생성
  4. 하나의 예약 정보 묶음으로 반환 → Sub4에 전달
"""
import uuid
from typing import List


class ConfirmationError(Exception):
    """Sub 3 확정 검증 실패 예외"""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


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
