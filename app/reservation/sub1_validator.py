# -*- coding: utf-8 -*-
# app/reservation/sub1_validator.py
"""
Sub 1 — 예약 검증부
설계도 흐름:
  1. 예약 요청 정보 수집 (일정, 인원, 결제 금액 등)
  2. 여행 필수 정보 확인
  3. 일정 확인 (시작일 < 종료일)
  4. 중복 예약 확인 (DB 조회)
  → 오류 있으면 ValidationError 발생 → Sub5 거부 처리
  → 오류 없으면 검증 완료 딕셔너리 반환
"""
from datetime import date, datetime
from typing import Optional


class ReservationValidationError(Exception):
    """Sub 1 검증 실패 예외"""
    def __init__(self, code: str, message: str, retryable: bool = False):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


async def validate_reservation(req) -> dict:
    """
    예약 요청 전체 검증.
    성공 시: 정제된 예약 컨텍스트 딕셔너리 반환
    실패 시: ReservationValidationError 발생

    Args:
        req: ReservationRequest (app.models)
    Returns:
        dict: validated_context — Sub2에 전달할 정제 데이터
    """
    # ── 1. 필수 필드 존재 확인 ──────────────────────────────────
    if not req.user_id or not req.user_id.strip():
        raise ReservationValidationError(
            "MISSING_USER_ID", "사용자 정보가 없습니다.", retryable=False
        )

    if not req.trip_data:
        raise ReservationValidationError(
            "MISSING_TRIP_DATA", "선택된 일정 데이터가 없습니다.", retryable=False
        )

    if not req.dest_city or not req.dep_city:
        raise ReservationValidationError(
            "MISSING_CITY", "출발지 또는 여행지 정보가 없습니다.", retryable=False
        )

    # ── 2. 일정 날짜 검증 ──────────────────────────────────────
    try:
        d_start = date.fromisoformat(req.start_date)
        d_end   = date.fromisoformat(req.end_date)
    except (ValueError, AttributeError):
        raise ReservationValidationError(
            "INVALID_DATE_FORMAT", "날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)", retryable=False
        )

    today = date.today()
    if d_start < today:
        raise ReservationValidationError(
            "PAST_DATE", f"출발일({d_start})이 오늘보다 이전입니다.", retryable=False
        )

    if d_end <= d_start:
        raise ReservationValidationError(
            "INVALID_DATE_RANGE", "종료일이 시작일보다 빠르거나 같습니다.", retryable=False
        )

    duration = (d_end - d_start).days + 1

    # ── 3. 인원 검증 ──────────────────────────────────────────
    if req.people < 1 or req.people > 8:
        raise ReservationValidationError(
            "INVALID_PEOPLE_COUNT",
            f"인원 수({req.people})가 허용 범위(1~8명)를 벗어났습니다.",
            retryable=False
        )

    # ── 4. 결제 정보 기본 확인 ─────────────────────────────────
    if req.payment.method not in ("card", "transfer"):
        raise ReservationValidationError(
            "INVALID_PAYMENT_METHOD",
            f"지원하지 않는 결제 수단입니다: {req.payment.method}",
            retryable=False
        )

    # ── 5. 중복 예약 확인 (DB 조회 — 현재는 Mock 통과) ──────────
    # TODO: 실 구현 시 DB에서 동일 user_id + start_date 조회
    # existing = db.query(Reservation).filter_by(user_id=req.user_id, ...).first()
    # if existing: raise ReservationValidationError("DUPLICATE_RESERVATION", ...)
    is_duplicate = False  # Mock: 항상 중복 없음
    if is_duplicate:
        raise ReservationValidationError(
            "DUPLICATE_RESERVATION",
            "동일한 날짜에 이미 예약된 일정이 있습니다.",
            retryable=False
        )

    # ── 검증 완료: 정제 컨텍스트 반환 ───────────────────────────
    validated_context = {
        "user_id": req.user_id.strip(),
        "itinerary_id": req.itinerary_id or f"ITIN_{req.user_id}_{d_start}",
        "trip_data": req.trip_data,
        "start_date": str(d_start),
        "end_date": str(d_end),
        "duration": duration,
        "dest_city": req.dest_city,
        "dep_city": req.dep_city,
        "people": req.people,
        "payment": {
            "method": req.payment.method,
            "card_last4": req.payment.card_last4,
            "budget_krw": req.payment.budget_krw,
        },
    }

    print(f"[Sub1] ✅ 검증 완료 — user:{req.user_id}, {req.dep_city}→{req.dest_city}, "
          f"{d_start}~{d_end}({duration}일), {req.people}명")

    return validated_context
