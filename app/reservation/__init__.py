# app/reservation/__init__.py
"""
예약부 파이프라인 패키지
설계도 기준 5단계 파이프라인:
  Sub1: 예약 검증부
  Sub2: 외부 예약 연동 관리부 (항공 + 숙소 병렬)
  Sub3: 예약 확정 검증
  Sub4: 예약 정보 저장부 (DB 트랜잭션)
  Sub5: 예약 결과 안내부
"""
from .sub1_validator import validate_reservation
from .sub2_external import book_parallel
from .sub3_confirmer import confirm_reservation
from .sub4_storage import save_reservation
from .sub5_notifier import build_success_response, build_fail_response

__all__ = [
    "validate_reservation",
    "book_parallel",
    "confirm_reservation",
    "save_reservation",
    "build_success_response",
    "build_fail_response",
]
