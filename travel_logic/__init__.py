# travel_logic/__init__.py
"""
Travel Logic 모듈
여행 일정 생성을 위한 메인 인터페이스
"""

from .itinerary_generator import generate_plans
from .services.db_service import DBService
from .domain.validators import check_is_domestic
from .exceptions import InsufficientPlacesError

# update_db는 DBService의 정적 메서드를 직접 노출
update_db = DBService.update_db

__all__ = [
    'generate_plans',
    'update_db',
    'check_is_domestic',
    'InsufficientPlacesError',
]
