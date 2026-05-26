# app/reservation/sub5_notifier.py
"""
Sub 5 — 예약 결과 안내부
설계도 흐름:
  ★ 성공 시:
    → 출력부에 반환값 응답 생성
    → 이메일 발송 (asyncio.to_thread → Resend HTTP API)
    → 끝
  ★ 실패 시:
    → 실패 사유에 따른 코드/메시지 생성
    → 실패 응답 반환

중요: 이메일은 BackgroundTasks로 분리 → 응답 시간에 영향 없음 (SRS M-12 준수)

환경변수:
  RESEND_API_KEY     Resend API Key (re_로 시작)
  RESEND_FROM_EMAIL  발신자 주소 (기본값: onboarding@resend.dev — 샌드박스용)
  값이 없으면 시뮬레이션 모드로 fallback
"""
import asyncio
import json
import os
from typing import List, Optional

import requests as _requests


# ── Resend 설정 ─────────────────────────────────────────────────────
_RESEND_BASE = "https://api.resend.com"
# 커스텀 도메인 미설정 시 Resend 제공 샌드박스 주소 (테스트용 수신자 본인에게만 발송 가능)
_RESEND_FROM_DEFAULT = "onboarding@resend.dev"


# ── 이메일 HTML 본문 생성 ────────────────────────────────────────────
def _build_email_html(
    reservation_id: str,
    dest_city: str,
    total_amount: float,
    items: List[dict],
) -> str:
    """예약 확정 이메일 HTML 본문 생성"""
    item_rows = ""
    for item in items:
        item_type_label = "항공" if item.get("item_type") == "flight" else "숙소"
        amount = float(item.get("amount", 0))
        partner = item.get("partner_name", "-")
        booking_id = item.get("partner_booking_id", "-")
        item_rows += (
            f"<tr>"
            f"<td style='padding:8px;border:1px solid #ddd'>{item_type_label}</td>"
            f"<td style='padding:8px;border:1px solid #ddd'>{partner}</td>"
            f"<td style='padding:8px;border:1px solid #ddd'>{booking_id}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;text-align:right'>"
            f"{amount:,.0f}원</td>"
            f"</tr>"
        )

    return f"""
<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto">
  <div style="background:#1a73e8;padding:20px;text-align:center">
    <h1 style="color:#fff;margin:0">Pick&amp;Go 예약 확정</h1>
  </div>
  <div style="padding:24px">
    <p>안녕하세요! <strong>{dest_city}</strong> 여행 예약이 확정되었습니다.</p>
    <p style="color:#555">예약 번호: <code style="background:#f5f5f5;padding:2px 6px">{reservation_id}</code></p>

    <table style="width:100%;border-collapse:collapse;margin-top:16px">
      <thead>
        <tr style="background:#f0f4ff">
          <th style="padding:8px;border:1px solid #ddd;text-align:left">구분</th>
          <th style="padding:8px;border:1px solid #ddd;text-align:left">파트너</th>
          <th style="padding:8px;border:1px solid #ddd;text-align:left">예약번호</th>
          <th style="padding:8px;border:1px solid #ddd;text-align:right">금액</th>
        </tr>
      </thead>
      <tbody>{item_rows}</tbody>
      <tfoot>
        <tr style="font-weight:bold;background:#f9f9f9">
          <td colspan="3" style="padding:8px;border:1px solid #ddd;text-align:right">합계</td>
          <td style="padding:8px;border:1px solid #ddd;text-align:right">
            {total_amount:,.0f}원
          </td>
        </tr>
      </tfoot>
    </table>

    <p style="margin-top:24px;color:#888;font-size:13px">
      본 메일은 자동 발송된 예약 확인 메일입니다.<br>
      문의: support@pick-and-go.example.com
    </p>
  </div>
</body>
</html>
""".strip()


# ── Resend 실 발송 (동기, to_thread용) ──────────────────────────────
def _send_mailgun_sync(to_email: str, subject: str, html_body: str) -> bool:
    """
    Resend API로 이메일 발송.
    함수명은 하위 호환성 유지 (테스트 Mock 경로 변경 최소화).
    반환값: True(성공) / False(실패 또는 키 미설정)
    """
    key = os.getenv("RESEND_API_KEY", "")
    if not key:
        return False                        # 키 미설정 → fallback

    from_email = os.getenv("RESEND_FROM_EMAIL", _RESEND_FROM_DEFAULT)
    try:
        r = _requests.post(
            f"{_RESEND_BASE}/emails",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json",
            },
            data=json.dumps({
                "from":    from_email,
                "to":      [to_email],
                "subject": subject,
                "html":    html_body,
            }),
            timeout=15,
        )
        if r.status_code in (200, 201):
            return True
        print(f"[Sub5/Resend] 발송 실패 — HTTP {r.status_code}: {r.text[:200]}")
        return False
    except Exception as exc:
        print(f"[Sub5/Resend] 예외 발생 — {exc}")
        return False


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
        "status":         "confirmed",
        "total_amount":   float(confirmed_reservation.get("total_amount", 0)),
        "currency":       confirmed_reservation.get("currency", "KRW"),
        "items":          items_out,
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
        "status":        "failed",
        "error_code":    error_code,
        "error_message": error_message,
        "retryable":     retryable,
        "failed_items":  failed_items or [],
    }


# ── 이메일 알림 발송 (비동기 백그라운드) ─────────────────────────────

async def send_confirmation_notification(
    reservation_id: str,
    user_id: str,
    dest_city: str,
    user_email: Optional[str] = None,
    items: Optional[List[dict]] = None,
    total_amount: float = 0.0,
) -> None:
    """
    예약 확정 알림 이메일 발송 (BackgroundTasks로 비동기 실행).
    응답 반환 후 백그라운드 실행 → SRS M-12(≤15초) 영향 없음.

    Args:
        reservation_id: 확정된 예약 ID
        user_id:        사용자 ID (로그용)
        dest_city:      목적지 도시 (이메일 제목/본문)
        user_email:     수신자 이메일. None이면 시뮬레이션으로 fallback
        items:          예약 항목 리스트 (항공/숙소)
        total_amount:   총 결제 금액
    """
    if user_email:
        subject  = f"[Pick&Go] {dest_city} 여행 예약이 확정되었습니다"
        html     = _build_email_html(reservation_id, dest_city, total_amount, items or [])
        sent = await asyncio.to_thread(_send_mailgun_sync, user_email, subject, html)
        if sent:
            print(
                f"[Sub5/BG] 📧 이메일 발송 완료 — "
                f"user:{user_id}, to:{user_email}, res_id:{reservation_id}"
            )
        else:
            # 발송 실패 → 응답에는 이미 "이메일로 영수증이 발송됩니다" 메시지가 포함되어 있으나
            # 백그라운드 실패이므로 사용자 응답에는 영향 없음
            print(
                f"[Sub5/BG] ⚠️ 이메일 발송 실패 (Mailgun 오류) — "
                f"user:{user_id}, res_id:{reservation_id}"
            )
    else:
        # user_email 없음 → 시뮬레이션
        await asyncio.sleep(0.5)
        print(
            f"[Sub5/BG] 📧 알림 발송 시뮬레이션 — "
            f"user:{user_id}, res_id:{reservation_id}, 목적지:{dest_city}"
        )
        # TODO Phase 2: 유저 테이블에서 이메일 조회 후 실 발송
