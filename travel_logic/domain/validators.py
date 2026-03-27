# domain/validators.py
"""
입력 데이터 검증 및 유틸리티 함수
"""

from ..config.settings import KOREAN_CITIES


def check_is_domestic(city_name: str) -> bool:
    """
    도시명이 국내 여행지인지 판단
    
    Args:
        city_name: 도시명
        
    Returns:
        국내 여행지 여부
    """
    if not city_name:
        return False
    
    # 한국 도시 목록 확인
    if any(k in city_name for k in KOREAN_CITIES):
        return True
    
    # 키워드 확인
    if "한국" in city_name or "대한민국" in city_name:
        return True
    
    return False


def validate_user_data(user_data: dict) -> bool:
    """
    사용자 입력 데이터 유효성 검증
    
    Args:
        user_data: 사용자 입력 데이터
        
    Returns:
        유효성 여부
    """
    required_fields = ['dest_city', 'start_date', 'end_date', 'style', 'people']
    
    for field in required_fields:
        if field not in user_data:
            return False
        if not user_data[field]:
            return False
    
    return True
