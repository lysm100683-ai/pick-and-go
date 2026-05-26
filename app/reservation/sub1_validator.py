# -*- coding: utf-8 -*-
# app/reservation/sub1_validator.py
"""
Sub 1 — 예약 검증부
설계도 흐름:
  1. 예약 요청 정보 수집 (일정, 인원, 결제 금액 등)
  2. 여행 필수 정보 확인
  3. 일정 확인 (시작일 < 종료일)
  4. 중복 예약 확인 (DB 실 조회 — reservations 테이블)
  → 오류 있으면 ValidationError 발생 → Sub5 거부 처리
  → 오류 없으면 검증 완료 딕셔너리 반환
"""
import asyncio
import sys
import os
from datetime import date, datetime
from typing import Optional

# 프로젝트 루트를 경로에 추가 (db 패키지 접근용)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from db.connection import get_db_session
from db.models import Reservation
from .sub_metrics import log_attempt


def _check_duplicate_sync(user_id: str, itinerary_id: str) -> bool:
    """
    DB에서 동일 사용자·일정의 활성 예약을 조회하는 동기 함수.
    asyncio.to_thread()로 비동기 컨텍스트에서 호출됨.

    조회 조건: user_id 일치 + itinerary_id 일치 + status in ('confirmed', 'pending')
    연결 실패 시 False 반환(통과) — 보수적 정책: DB 오류로 정상 요청을 막지 않음.
    """
    try:
        with get_db_session() as session:
            existing = (
                session.query(Reservation)
                .filter(
                    Reservation.user_id      == user_id,
                    Reservation.itinerary_id == itinerary_id,
                    Reservation.status.in_(["confirmed", "pending"]),
                )
                .first()
            )
            return existing is not None
    except Exception:
        # DB 접근 불가 시 중복 판정 불가 → 파이프라인 통과 허용
        return False


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

    # ── 5. 중복 예약 확인 (DB 실 조회) ────────────────────────────
    itinerary_id_for_check = req.itinerary_id or f"ITIN_{req.user_id.strip()}_{d_start}"
    is_duplicate = await asyncio.to_thread(
        _check_duplicate_sync, req.user_id.strip(), itinerary_id_for_check
    )
    if is_duplicate:
        raise ReservationValidationError(
            "DUPLICATE_RESERVATION",
            "동일한 날짜에 이미 예약된 일정이 있습니다.",
            retryable=False
        )

    # ── 검증 완료: 정제 컨텍스트 반환 ───────────────────────────
    validated_context = {
        "user_id": req.user_id.strip(),
        "itinerary_id": req.itinerary_id or f"ITIN_{req.user_id.strip()}_{d_start}",
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

    # ── SRS M-13: 예약 시도 로그 기록 (best-effort) ────────────────
    # attempt 로그 = 성공률 분모. 실패해도 예약 흐름 유지.
    await log_attempt(
        user_id=req.user_id.strip(),
        itinerary_id=validated_context["itinerary_id"],
        dest_city=req.dest_city,
    )

    return validated_context
