# strategies/foodie_strategy.py
"""
🍽️ 식도락 & 힐링 전략
"""

from typing import Dict, Any
from .base_strategy import ItineraryStrategy


class FoodieStrategy(ItineraryStrategy):
    """식도락 & 힐링 전략 - 맛집 중심 여유로운 일정"""
    
    def __init__(self):
        super().__init__()
        self.w_time = 0.05
        self.w_score = 15
        self.epsilon = 0.15
        self.food_boost = 100
        self.sight_boost = 0
    
    def get_weights(self) -> Dict[str, Any]:
        return {
            'W_time': self.w_time,
            'W_score': self.w_score,
            'epsilon': self.epsilon,
            'food_boost': self.food_boost,
            'sight_boost': self.sight_boost
        }
    
    def get_place_distribution(self, user_data: Dict[str, Any]) -> Dict[str, int]:
        """맛집 위주 장소 분배"""
        base_distribution = {
            'sights': 2,
            'foods': 3,
            'cafes': 1
        }
        
        return self.adjust_for_user_preferences(base_distribution, user_data)
