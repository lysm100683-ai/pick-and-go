# strategies/active_strategy.py
"""
🔥 액티브 & 핫플 전략
"""

from typing import Dict, Any
from .base_strategy import ItineraryStrategy


class ActiveStrategy(ItineraryStrategy):
    """액티브 & 핫플 전략 - 활동적인 장소와 인기 명소"""
    
    def __init__(self):
        super().__init__()
        self.w_time = 0.12
        self.w_score = 12
        self.epsilon = 0.08
        self.food_boost = 0
        self.sight_boost = 50
    
    def get_weights(self) -> Dict[str, Any]:
        return {
            'W_time': self.w_time,
            'W_score': self.w_score,
            'epsilon': self.epsilon,
            'food_boost': self.food_boost,
            'sight_boost': self.sight_boost
        }
    
    def get_place_distribution(self, user_data: Dict[str, Any]) -> Dict[str, int]:
        """활동적인 장소 위주 분배"""
        base_distribution = {
            'sights': 3,
            'foods': 2,
            'cafes': 1
        }
        
        return self.adjust_for_user_preferences(base_distribution, user_data)
