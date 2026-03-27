# config/settings.py
"""
환경별 설정 및 국내 도시 목록
"""

# 국내 도시 목록
KOREAN_CITIES = [
    "서울", "부산", "제주", "인천", "대구", "대전", "광주", "울산", "수원", "강릉",
    "경주", "전주", "여수", "속초", "춘천", "가평", "양평", "포항", "거제", "남해",
    "통영", "군산", "목포", "순천", "안동", "청주", "충주", "천안", "세종"
]

# 기본 설정
DEFAULT_MIN_RATING = 3.0
DEFAULT_MIN_HOTEL_RATING = 3
DEFAULT_SIGHTS_PER_DAY = 2
DEFAULT_FOODS_PER_DAY = 2
DEFAULT_CAFES_PER_DAY = 0
