# app/reservation/sub5_notifier.py
"""
Sub 5 — 예약 결과 안내부
설계도 흐름:
  ★ 성공 시:
    → 출력부에 반환값 응답 생성
    → 이메일/SMS 발송 (비동기 백그라운드)
    → 끝
  ★ 실패 시:
    → 실패 사유에 따른 코드/메시지 생성
    → 실패 응답 반환

중요: 이메일/SMS는 BackgroundTasks로 분리 → 응답 시간에 영향 없음 (SRS M-12 준수)
"""
import asyncio
from typing import List, Optional


# ── 성공 응답 생성 ──────────────────────────────────────────────────

def build_success_response(confirmed_reservation: dict, saved_reservation_id: str) -> dict:
    """
    예약 성공 시 최종 응답 딕셔너리 생성.
    Sub4 저장 완료 후 호출.

    Args:
        confirmed_reservation: Sub3 확정 예약 묶음
        saved_reservation_id:  Sub4에서 반환된 DB 저장 완료 ID
    Returns:
        dict: ReservationResponse 호환 딕셔너리
    """
    items_out = []
    for item in confirmed_reservation.get("items", []):
        items_out.append({
            "item_type":          item.get("item_type"),
            "partner_name":       item.get("partner_name"),
            "partner_booking_id": item.get("partner_booking_id"),
            "status":             item.get("status", "confirmed"),
            "amount":             float(item.get("amount", 0)),
            "currency":           item.get("currency", "KRW"),
            "details":            item.get("details", {}),
            "error_msg":          None,
        })

    print(f"[Sub5] ✅ 성공 응답 생성 — reservation_id:{saved_reservation_id}")

    return {
        "reservation_id": saved_reservation_id,
        "status": "confirmed",
        "total_amount": float(confirmed_reservation.get("total_amount", 0)),
        "currency": confirmed_reservation.get("currency", "KRW"),
        "items": items_out,
        "message": (
            f"{confirmed_reservation.get('dest_city', '여행지')} 예약이 확정되었습니다. "
            "이메일로 영수증이 발송됩니다."
        ),
    }


# ── 실패 응답 생성 ──────────────────────────────────────────────────

def build_fail_response(
    error_code: str,
    error_message: str,
    retryable: bool = False,
    failed_items: Optional[List[str]] = None,
) -> dict:
    """
    예약 실패 시 최종 오류 응답 딕셔너리 생성.

    Args:
        error_code:    실패 코드 (Sub1~Sub4에서 발생한 코드)
        error_message: 사용자에게 보여줄 메시지
        retryable:     재시도 가능 여부
        failed_items:  실패한 항목 리스트 (flight/hotel)
    Returns:
        dict: ReservationFailResponse 호환 딕셔너리
    """
    print(f"[Sub5] ❌ 실패 응답 생성 — code:{error_code}, retryable:{retryable}")

    return {
        "status": "failed",
        "error_code": error_code,
        "error_message": error_message,
        "retryable": retryable,
        "failed_items": failed_items or [],
    }


# ── 이메일/SMS 발송 (비동기 백그라운드) ─────────────────────────────

async def send_confirmation_notification(reservation_id: str, user_id: str, dest_city: str) -> None:
    """
    예약 확정 알림 발송 (BackgroundTasks로 비동기 실행).
    응답 반환 후 백그라운드에서 실행 → SRS M-12(≤15초) 영향 없음.

    실제 구현:
      - SMTP 이메일 발송 (예: SendGrid, AWS SES)
      - SMS 발송 (예: Twilio, 알리고)
    """
    # 현재: 시뮬레이션 (실제 발송 없음)
    await asyncio.sleep(0.5)  # 발송 지연 시뮬레이션
    print(
        f"[Sub5/BG] 📧 알림 발송 시뮬레이션 — "
        f"user:{user_id}, res_id:{reservation_id}, 목적지:{dest_city}"
    )
    # TODO Phase 2: 실제 이메일/SMS 연동
    # await send_email(user_email, template="reservation_confirmed", data={...})
    # await send_sms(user_phone, message=f"{dest_city} 예약 확정: {reservation_id}")
