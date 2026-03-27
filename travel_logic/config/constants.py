# config/constants.py
"""
여행 일정 생성에 사용되는 상수 정의
"""

# 📌 권장 체류 시간 (초 단위)
VISIT_TIMES = {
    "관광": 2.5 * 3600,  # 관광지 2.5시간
    "식사": 1.5 * 3600,   # 식사 1.5시간
    "카페": 1.0 * 3600,   # 카페/휴식 1.0시간
    "숙소": 0.5 * 3600,  # 숙소 복귀/출발 30분
    "default": 2.0 * 3600 # 기타 2.0시간
}

# 식사 시간대
LUNCH_START_RANGE = (11, 13)
DINNER_START_RANGE = (17, 20)

# 🚀 테마별 Cost 가중치 및 Epsilon 정의
THEME_WEIGHTS = {
    "✨ 핵심 코스": {
        "W_time": 0.1, 
        "W_score": 10, 
        "epsilon": 0.05, 
        "food_boost": 0, 
        "sight_boost": 0
    },
    "🍽️ 식도락 & 힐링": {
        "W_time": 0.05, 
        "W_score": 15, 
        "epsilon": 0.15, 
        "food_boost": 100, 
        "sight_boost": 0
    },
    "🌿 자연 & 관광": {
        "W_time": 0.08, 
        "W_score": 8, 
        "epsilon": 0.10, 
        "food_boost": 0, 
        "sight_boost": 100
    },
    "🔥 액티브 & 핫플": {
        "W_time": 0.12, 
        "W_score": 12, 
        "epsilon": 0.08, 
        "food_boost": 0, 
        "sight_boost": 50
    },
}
