# strategies/nature_strategy.py
"""
🌿 자연 & 관광 전략
"""

from typing import Dict, Any
from .base_strategy import ItineraryStrategy


class NatureStrategy(ItineraryStrategy):
    """자연 & 관광 전략 - 명소와 자연 경관 중심"""
    
    def __init__(self):
        super().__init__()
        self.w_time = 0.08
        self.w_score = 8
        self.epsilon = 0.10
        self.food_boost = 0
        self.sight_boost = 100
    
    def get_weights(self) -> Dict[str, Any]:
        return {
            'W_time': self.w_time,
            'W_score': self.w_score,
            'epsilon': self.epsilon,
            'food_boost': self.food_boost,
            'sight_boost': self.sight_boost
        }
    
    def get_place_distribution(self, user_data: Dict[str, Any]) -> Dict[str, int]:
        """관광지 위주 장소 분배"""
        base_distribution = {
            'sights': 3,
            'foods': 2,
            'cafes': 0
        }
        
        return self.adjust_for_user_preferences(base_distribution, user_data)
