# app/reservation/sub4_storage.py
"""
Sub 4 — 예약 정보 저장부
설계도 흐름:
  1. 트랜잭션 시작
  2. reservations 테이블에 기본 예약 정보 삽입
  3. reservation_items 테이블에 각 여행 항목 삽입
  4. reservation_logs 테이블에 성공 이력 저장
  5. 트랜잭션 커밋
  → 실패 시 트랜잭션 롤백 + 로그 기록
"""
import uuid
from typing import List

# DB 연결 임포트
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from db.connection import get_db_session
from db.models import Reservation, ReservationItem, ReservationLog


class StorageError(Exception):
    """Sub 4 DB 저장 실패 예외"""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


async def save_reservation(confirmed_reservation: dict) -> str:
    """
    확정된 예약 정보를 DB에 트랜잭션으로 저장.

    Args:
        confirmed_reservation: Sub3에서 반환된 확정 예약 묶음
    Returns:
        str: 저장 완료된 reservation_id
    Raises:
        StorageError: DB 저장 실패
    """
    res_id_str = confirmed_reservation["reservation_id"]
    res_uuid   = uuid.UUID(res_id_str)

    try:
        # ── 트랜잭션 시작 ─────────────────────────────────────
        with get_db_session() as session:

            # ── 1. reservations 테이블 삽입 ──────────────────
            reservation = Reservation(
                id           = res_uuid,
                user_id      = confirmed_reservation["user_id"],
                itinerary_id = confirmed_reservation.get("itinerary_id"),
                trip_data    = confirmed_reservation["trip_data"],
                status       = "confirmed",
                total_amount = confirmed_reservation["total_amount"],
                currency     = confirmed_reservation.get("currency", "KRW"),
                people       = confirmed_reservation["people"],
            )
            session.add(reservation)
            session.flush()  # FK 참조를 위해 먼저 flush

            # ── 2. reservation_items 테이블 삽입 ─────────────
            for item in confirmed_reservation.get("items", []):
                res_item = ReservationItem(
                    reservation_id    = res_uuid,
                    item_type         = item["item_type"],
                    partner_name      = item.get("partner_name"),
                    partner_booking_id= item.get("partner_booking_id"),
                    status            = item.get("status", "confirmed"),
                    amount            = item.get("amount", 0),
                    currency          = item.get("currency", "KRW"),
                    details           = item.get("details", {}),
                )
                session.add(res_item)

            # ── 3. reservation_logs 테이블 — 성공 이력 ───────
            success_log = ReservationLog(
                reservation_id = res_uuid,
                action_type    = "success",
                sub_system     = "sub4",
                result         = "ok",
                payload        = {
                    "total_amount": confirmed_reservation["total_amount"],
                    "items_count":  len(confirmed_reservation.get("items", [])),
                    "dest_city":    confirmed_reservation.get("dest_city"),
                },
            )
            session.add(success_log)

            # ── 트랜잭션 커밋 ─────────────────────────────────
            session.commit()

        print(f"[Sub4] ✅ DB 저장 완료 — reservation_id:{res_id_str}")
        return res_id_str

    except Exception as e:
        # DB 오류: 트랜잭션은 with 블록 종료 시 자동 롤백됨
        # 실패 로그는 트랜잭션 외부에서 별도 저장 시도
        await _save_failure_log(res_uuid, str(e))
        raise StorageError(
            "DB_SAVE_FAILED",
            f"예약 정보 저장 중 오류 발생: {str(e)}"
        )


async def _save_failure_log(reservation_id: uuid.UUID, error_msg: str) -> None:
    """
    저장 실패 로그 기록 (트랜잭션 외부 — best-effort)
    실패해도 예외를 전파하지 않음
    """
    try:
        with get_db_session() as session:
            fail_log = ReservationLog(
                reservation_id = reservation_id,
                action_type    = "failure",
                sub_system     = "sub4",
                result         = "error",
                payload        = {"error": error_msg},
            )
            session.add(fail_log)
            session.commit()
    except Exception:
        # 로그 저장도 실패하면 콘솔 출력만
        print(f"[Sub4] ❌ 실패 로그 저장도 실패: {error_msg}")
