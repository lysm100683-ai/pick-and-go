# tests/test_e2e_reservation.py
"""
예약 파이프라인 E2E 통합 테스트 (Sub1 → Sub2 → Sub3 → Sub4 → Sub5)

각 시나리오:
  TC-E2E-01: 정상 예약 전체 흐름
  TC-E2E-02: Sub2 부분 실패 → 자동 롤백 + 실패 응답
  TC-E2E-03: Sub3 확정 실패 → Sub2 롤백 + 실패 응답  [신규: Sub3→Sub2 연동]
  TC-E2E-04: Sub4 DB 저장 실패 → Sub2 롤백 + 실패 응답 [신규: Sub4→Sub2 연동]
  TC-E2E-05: 파트너사 응답 지연 → 10초 타임아웃 + 롤백  [신규: Sub2 타임아웃]
  TC-E2E-06: Sub5 이메일 발송 — Mailgun 성공/실패/시뮬레이션 3-way 검증
"""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

# ── 테스트용 Request 모조 객체 ──────────────────────────────────────
def _make_request(**overrides):
    defaults = dict(
        user_id="user_test_001",
        itinerary_id="ITIN_001",
        trip_data={"days": [{"places": ["경복궁", "남산타워"]}]},
        dep_city="ICN",
        dest_city="NRT",
        start_date="2027-01-10",
        end_date="2027-01-13",
        people=2,
        payment=SimpleNamespace(method="card", card_last4="1234", budget_krw=2_000_000),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── 확정 예약 더미 데이터 ───────────────────────────────────────────
_BOOKING_RESULTS = [
    {
        "item_type": "flight",
        "partner_name": "amadeus_mock",
        "partner_booking_id": "FL-ABCD1234",
        "status": "confirmed",
        "amount": 400_000,
        "currency": "KRW",
        "details": {},
        "error_msg": None,
    },
    {
        "item_type": "hotel",
        "partner_name": "booking_com_mock",
        "partner_booking_id": "HT-EFGH5678",
        "status": "confirmed",
        "amount": 240_000,
        "currency": "KRW",
        "details": {},
        "error_msg": None,
    },
]


class TestReservationPipelineE2E(unittest.IsolatedAsyncioTestCase):
    """예약 파이프라인 Sub1~Sub5 전체 통합 시나리오"""

    # ── TC-E2E-01: 정상 흐름 ─────────────────────────────────────
    @patch("app.reservation.sub1_validator._check_duplicate_sync", return_value=False)
    @patch("app.reservation.sub1_validator.log_attempt", new_callable=AsyncMock)  # SRS M-13 로그 Mock
    @patch("app.reservation.sub3_confirmer.MOCK_VERIFY", True)  # 단위 테스트: 가짜 booking_id로 실 API 호출 방지
    @patch("app.reservation.sub4_storage.get_db_session")
    @patch("app.reservation.sub2_external.MOCK_FLIGHT", True)   # 단위 테스트: Mock 강제
    @patch("app.reservation.sub2_external.MOCK_HOTEL",  True)   # 단위 테스트: Mock 강제
    @patch("app.reservation.sub2_external.MOCK_FLIGHT_SUCCESS_RATE", 1.0)
    @patch("app.reservation.sub2_external.MOCK_HOTEL_SUCCESS_RATE", 1.0)
    async def test_01_happy_path(self, mock_session_factory, _mock_log_attempt, _mock_dup_check):
        """TC-E2E-01: 모든 단계 성공 → reservation_id 반환"""
        from app.reservation.sub1_validator import validate_reservation
        from app.reservation.sub2_external import book_parallel
        from app.reservation.sub3_confirmer import confirm_reservation
        from app.reservation.sub4_storage import save_reservation
        from app.reservation.sub5_notifier import build_success_response

        # Sub4 DB mock
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session_factory.return_value = mock_session

        req = _make_request()

        # Sub1
        ctx = await validate_reservation(req)
        self.assertEqual(ctx["dest_city"], "NRT")

        # Sub2
        bookings = await book_parallel(ctx)
        self.assertEqual(len(bookings), 2)
        self.assertTrue(all(b["status"] == "confirmed" for b in bookings))

        # Sub3
        confirmed = await confirm_reservation(ctx, bookings)
        self.assertIn("reservation_id", confirmed)
        self.assertEqual(confirmed["status"], "confirmed")
        self.assertGreater(confirmed["total_amount"], 0)

        # Sub4
        saved_id = await save_reservation(confirmed)
        self.assertEqual(saved_id, confirmed["reservation_id"])

        # Sub5
        response = build_success_response(confirmed, saved_id)
        self.assertEqual(response["status"], "confirmed")
        self.assertEqual(response["reservation_id"], saved_id)
        self.assertGreater(response["total_amount"], 0)

        print("✅ [TC-E2E-01] 정상 예약 전체 흐름 통과")

    # ── TC-E2E-02: Sub2 부분 실패 → 롤백 ────────────────────────
    @patch("app.reservation.sub1_validator._check_duplicate_sync", return_value=False)
    @patch("app.reservation.sub1_validator.log_attempt", new_callable=AsyncMock)  # SRS M-13 로그 Mock
    @patch("app.reservation.sub2_external.MOCK_FLIGHT", True)   # Mock 강제 (성공률 제어용)
    @patch("app.reservation.sub2_external.MOCK_HOTEL",  True)   # Mock 강제 (실패 시뮬레이션)
    @patch("app.reservation.sub2_external.MOCK_HOTEL_SUCCESS_RATE", 0.0)
    @patch("app.reservation.sub2_external.MOCK_FLIGHT_SUCCESS_RATE", 1.0)
    async def test_02_sub2_partial_failure_rollback(self, _mock_log_attempt, _mock_dup_check):
        """TC-E2E-02: 숙소 매진 → 항공 자동 롤백, BookingFailedError 발생"""
        from app.reservation.sub1_validator import validate_reservation
        from app.reservation.sub2_external import book_parallel, BookingFailedError

        req = _make_request()
        ctx = await validate_reservation(req)

        with self.assertRaises(BookingFailedError) as cm:
            await book_parallel(ctx)

        self.assertIn("hotel", cm.exception.failed_items)
        self.assertTrue(cm.exception.retryable)
        print("✅ [TC-E2E-02] 숙소 매진 시 항공 자동 롤백 + BookingFailedError 확인")

    # ── TC-E2E-03: Sub3 실패 → Sub2 외부 예약 롤백 ───────────────
    async def test_03_sub3_failure_triggers_sub2_rollback(self):
        """TC-E2E-03: Sub3 확정 실패 시 rollback_bookings 호출 여부 검증"""
        from app.reservation.sub2_external import rollback_bookings
        from app.reservation.sub3_confirmer import ConfirmationError

        # Sub3가 실패를 던지는 상황을 시뮬레이션
        invalid_bookings = [
            {**_BOOKING_RESULTS[0], "status": "failed"},  # 항공이 실패 상태
            _BOOKING_RESULTS[1],
        ]

        with patch("app.reservation.sub2_external._cancel_item", new_callable=AsyncMock) as mock_cancel:
            # Sub3는 실패 → 호출자(main.py)가 rollback_bookings 호출
            # 여기서는 rollback_bookings 자체가 confirmed 항목만 취소하는지 검증
            await rollback_bookings(invalid_bookings)

            # status='failed'인 항목은 partner_booking_id가 없어 취소 안 됨
            # status='confirmed'인 hotel만 취소돼야 함
            self.assertEqual(mock_cancel.call_count, 1)
            cancelled_item = mock_cancel.call_args[0][0]
            self.assertEqual(cancelled_item["item_type"], "hotel")

        print("✅ [TC-E2E-03] Sub3 실패 시 확정된 항목만 선별 롤백 확인")

    # ── TC-E2E-04: Sub4 DB 실패 → Sub2 외부 예약 롤백 ────────────
    @patch("app.reservation.sub1_validator._check_duplicate_sync", return_value=False)
    @patch("app.reservation.sub1_validator.log_attempt", new_callable=AsyncMock)  # SRS M-13 로그 Mock
    @patch("app.reservation.sub3_confirmer.MOCK_VERIFY", True)  # 단위 테스트: 가짜 booking_id로 실 API 호출 방지
    @patch("app.reservation.sub4_storage.get_db_session")
    async def test_04_sub4_db_failure_triggers_rollback(self, mock_session_factory, _mock_log_attempt, _mock_dup_check):
        """TC-E2E-04: DB 저장 실패 시 rollback_bookings가 호출되어 외부 예약 취소"""
        from app.reservation.sub3_confirmer import confirm_reservation
        from app.reservation.sub4_storage import save_reservation, StorageError
        from app.reservation.sub2_external import rollback_bookings

        # DB 세션이 예외를 던지도록 설정
        mock_session_factory.side_effect = Exception("DB 연결 오류 (테스트용)")

        req = _make_request()
        from app.reservation.sub1_validator import validate_reservation
        ctx = await validate_reservation(req)
        confirmed = await confirm_reservation(ctx, _BOOKING_RESULTS)

        # Sub4 실패 확인
        with self.assertRaises(StorageError) as cm:
            await save_reservation(confirmed)
        self.assertEqual(cm.exception.code, "DB_SAVE_FAILED")

        # Sub4 실패 후 main.py가 rollback_bookings를 호출하는 경로 검증
        with patch("app.reservation.sub2_external._cancel_item", new_callable=AsyncMock) as mock_cancel:
            await rollback_bookings(confirmed.get("items", []))
            # 항공 + 숙소 두 건 모두 취소 요청
            self.assertEqual(mock_cancel.call_count, 2)
            cancelled_types = {c[0][0]["item_type"] for c in mock_cancel.call_args_list}
            self.assertSetEqual(cancelled_types, {"flight", "hotel"})

        print("✅ [TC-E2E-04] Sub4 DB 실패 시 항공+숙소 전체 Saga 롤백 확인")

    # ── TC-E2E-05: 파트너사 응답 지연 → 타임아웃 → 롤백 ─────────
    async def test_05_partner_timeout_triggers_rollback(self):
        """TC-E2E-05: 항공 API 응답 0.5초 지연 + 타임아웃 50ms → BookingFailedError"""
        from app.reservation.sub1_validator import validate_reservation
        from app.reservation.sub2_external import book_parallel, BookingFailedError
        import app.reservation.sub2_external as sub2

        req = _make_request()

        # Sub1 중복 DB 조회를 Mock으로 우회 (네트워크 불필요)
        with patch("app.reservation.sub1_validator._check_duplicate_sync", return_value=False), \
             patch("app.reservation.sub1_validator.log_attempt", new_callable=AsyncMock):  # SRS M-13 로그 Mock
            ctx = await validate_reservation(req)

        # 항공 응답을 0.5초 지연시키는 슬로우 Mock
        async def _slow_flight(_ctx):
            await asyncio.sleep(0.5)
            return {"item_type": "flight", "status": "confirmed",
                    "partner_booking_id": "FL-SLOW", "amount": 300_000,
                    "currency": "KRW", "details": {}, "error_msg": None,
                    "partner_name": "mock"}

        orig_timeout = sub2.BOOKING_TIMEOUT_SEC
        sub2.BOOKING_TIMEOUT_SEC = 0.05   # 50ms — 0.5초 지연보다 짧게 설정
        try:
            with patch("app.reservation.sub2_external.MOCK_FLIGHT", True), \
                 patch("app.reservation.sub2_external.MOCK_HOTEL",  True), \
                 patch("app.reservation.sub2_external.MOCK_HOTEL_SUCCESS_RATE", 1.0), \
                 patch("app.reservation.sub2_external._mock_book_flight",
                       side_effect=_slow_flight):
                with self.assertRaises(BookingFailedError) as cm:
                    await book_parallel(ctx)
        finally:
            sub2.BOOKING_TIMEOUT_SEC = orig_timeout   # 원복

        self.assertIn("flight", cm.exception.failed_items)
        self.assertIn("초과", cm.exception.message)
        print("✅ [TC-E2E-05] 파트너사 응답 지연 → 타임아웃 + BookingFailedError 확인")


    # ── TC-E2E-06: Sub5 이메일 발송 ────────────────────────────────
    async def test_06_sub5_email_notification(self):
        """TC-E2E-06: Sub5 이메일 발송 3-way 검증
          (A) Mailgun 성공  → sent=True, 함수 정상 종료
          (B) Mailgun 실패  → sent=False, 예외 없이 정상 종료
          (C) user_email 없음 → 시뮬레이션 모드, 예외 없이 정상 종료
        """
        from app.reservation.sub5_notifier import (
            build_success_response,
            build_fail_response,
            send_confirmation_notification,
        )

        # ── 응답 구조 검증 ──
        confirmed = {
            "reservation_id": "RES-TEST-001",
            "status": "confirmed",
            "total_amount": 640_000,
            "currency": "KRW",
            "dest_city": "NRT",
            "items": _BOOKING_RESULTS,
        }
        success_resp = build_success_response(confirmed, "RES-TEST-001")
        self.assertEqual(success_resp["status"], "confirmed")
        self.assertEqual(success_resp["reservation_id"], "RES-TEST-001")
        self.assertEqual(len(success_resp["items"]), 2)
        self.assertGreater(success_resp["total_amount"], 0)
        self.assertIn("NRT", success_resp["message"])

        fail_resp = build_fail_response("BOOKING_FAILED", "숙소 매진", retryable=True, failed_items=["hotel"])
        self.assertEqual(fail_resp["status"], "failed")
        self.assertEqual(fail_resp["error_code"], "BOOKING_FAILED")
        self.assertTrue(fail_resp["retryable"])
        self.assertIn("hotel", fail_resp["failed_items"])

        # ── (A) Mailgun 성공 시뮬레이션 ──
        with patch(
            "app.reservation.sub5_notifier._send_mailgun_sync",
            return_value=True,
        ) as mock_send:
            await send_confirmation_notification(
                reservation_id="RES-TEST-001",
                user_id="user_test_001",
                dest_city="NRT",
                user_email="tester@example.com",
                items=_BOOKING_RESULTS,
                total_amount=640_000,
            )
            mock_send.assert_called_once()
            call_args = mock_send.call_args[0]
            self.assertEqual(call_args[0], "tester@example.com")   # to_email
            self.assertIn("NRT", call_args[1])                      # subject
            self.assertIn("Pick&amp;Go", call_args[2])               # html body (HTML-escaped &)

        # ── (B) Mailgun 실패 — 예외 없이 정상 종료 ──
        with patch(
            "app.reservation.sub5_notifier._send_mailgun_sync",
            return_value=False,
        ):
            # 예외 없이 완료되어야 함
            await send_confirmation_notification(
                reservation_id="RES-TEST-001",
                user_id="user_test_001",
                dest_city="NRT",
                user_email="tester@example.com",
                items=_BOOKING_RESULTS,
                total_amount=640_000,
            )

        # ── (C) user_email 없음 → 시뮬레이션 ──
        with patch("app.reservation.sub5_notifier._send_mailgun_sync") as mock_send:
            await send_confirmation_notification(
                reservation_id="RES-TEST-001",
                user_id="user_test_001",
                dest_city="NRT",
                # user_email 미전달
            )
            mock_send.assert_not_called()   # 실 발송 함수 호출 없어야 함

        print("✅ [TC-E2E-06] Sub5 이메일 발송 3-way 검증 통과")


if __name__ == "__main__":
    unittest.main(verbosity=2)
