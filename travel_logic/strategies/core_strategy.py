# strategies/core_strategy.py
"""
✨ 핵심 코스 전략
"""

from typing import Dict, Any
from .base_strategy import ItineraryStrategy


class CoreStrategy(ItineraryStrategy):
    """핵심 코스 전략 - 균형잡힌 효율적인 일정"""
    
    def __init__(self):
        super().__init__()
        self.w_time = 0.1
        self.w_score = 10
        self.epsilon = 0.05
        self.food_boost = 0
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
        """균형잡힌 장소 분배"""
        base_distribution = {
            'sights': 2,
            'foods': 2,
            'cafes': 0
        }
        
        # 스타일에 따른 조절
        styles = user_data.get('style', [])
        if '액티비티' in styles or '자연' in styles:
            base_distribution['sights'] = 3
        elif '맛집' in styles:
            base_distribution['foods'] = 3
            base_distribution['cafes'] = 1
        elif '쇼핑' in styles:
            base_distribution['cafes'] = 1
        
        return self.adjust_for_user_preferences(base_distribution, user_data)
