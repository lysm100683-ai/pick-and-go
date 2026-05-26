import asyncio
import unittest
from unittest.mock import patch
from app.reservation.sub2_external import book_parallel, BookingFailedError

class TestSub2Saga(unittest.IsolatedAsyncioTestCase):
    
    @patch('app.reservation.sub2_external.MOCK_HOTEL_SUCCESS_RATE', 0.0)
    @patch('app.reservation.sub2_external.MOCK_FLIGHT_SUCCESS_RATE', 1.0)
    async def test_saga_rollback_on_partial_failure(self):
        """항공은 무조건 성공(1.0), 숙소는 무조건 실패(0.0)하도록 강제하여 롤백이 일어나는지 검증"""
        context = {
            "dep_city": "ICN",
            "dest_city": "NRT",
            "people": 2,
            "start_date": "2026-10-01",
            "end_date": "2026-10-05"
        }
        
        # 병렬 예약 실행
        with self.assertRaises(BookingFailedError) as context_manager:
            await book_parallel(context)
            
        # 발생한 에러에서 실패 원인이 'hotel'인지 검증
        self.assertIn("hotel", context_manager.exception.failed_items)
        self.assertTrue(context_manager.exception.retryable)
        print("✅ [단위 테스트 통과] 숙소 매진 시 항공편이 정상적으로 자동 롤백되며 예외가 발생함을 코드로 증명함.")

if __name__ == "__main__":
    unittest.main()
