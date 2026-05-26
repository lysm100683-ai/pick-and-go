# scripts/send_test_email.py
"""
Mailgun 이메일 발송 테스트 스크립트
사용법:
  python scripts/send_test_email.py 수신자@이메일.com
"""
import sys
import os

# 프로젝트 루트 기준으로 .env 로드
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.reservation.sub5_notifier import _send_mailgun_sync, _build_email_html

def main():
    to_email = sys.argv[1] if len(sys.argv) > 1 else None
    if not to_email:
        print("사용법: python scripts/send_test_email.py 수신자@이메일.com")
        sys.exit(1)

    print(f"[테스트] 발송 대상: {to_email}")
    print(f"[테스트] Resend API Key: {'설정됨' if os.getenv('RESEND_API_KEY') else '(미설정)'}")

    # 샘플 예약 데이터로 HTML 생성
    html = _build_email_html(
        reservation_id="TEST-0001",
        dest_city="NRT (도쿄)",
        total_amount=640_000,
        items=[
            {"item_type": "flight", "partner_name": "Duffel", "partner_booking_id": "FL-TEST1234", "amount": 400_000},
            {"item_type": "hotel", "partner_name": "LiteAPI",  "partner_booking_id": "HT-TEST5678", "amount": 240_000},
        ],
    )

    ok = _send_mailgun_sync(
        to_email=to_email,
        subject="[Pick&Go] 테스트 이메일 — 예약 확정 알림",
        html_body=html,
    )

    if ok:
        print("[SUCCESS] 발송 성공! 받은 편지함을 확인하세요.")
    else:
        print("[FAIL] 발송 실패. 아래를 확인하세요:")
        print("  1. .env RESEND_API_KEY 값이 올바른지 확인")
        print("  2. Resend 대시보드 -> API Keys 에서 키 상태 확인")
        print("  3. onboarding@resend.dev 발신 시 수신자는 본인 이메일만 가능")

if __name__ == "__main__":
    main()
