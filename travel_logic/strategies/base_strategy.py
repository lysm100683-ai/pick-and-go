# strategies/base_strategy.py
"""
여행 일정 생성 전략의 추상 베이스 클래스
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from ..config.settings import DEFAULT_SIGHTS_PER_DAY, DEFAULT_FOODS_PER_DAY, DEFAULT_CAFES_PER_DAY


class ItineraryStrategy(ABC):
    """
    여행 일정 생성 전략 인터페이스
    각 테마별 전략은 이 클래스를 상속받아 구현
    """
    
    def __init__(self):
        """전략 초기화 (가중치 및 부스트 값 설정)"""
        self.w_time = 0.1
        self.w_score = 10
        self.epsilon = 0.05
        self.food_boost = 0
        self.sight_boost = 0
    
    @abstractmethod
    def get_weights(self) -> Dict[str, Any]:
        """
        테마별 가중치 반환
        
        Returns:
            {'W_time': float, 'W_score': float, 'epsilon': float, 
             'food_boost': int, 'sight_boost': int}
        """
        pass
    
    @abstractmethod
    def get_place_distribution(self, user_data: Dict[str, Any]) -> Dict[str, int]:
        """
        하루 일정에서 장소 타입별 개수 결정
        
        Args:
            user_data: 사용자 입력 데이터
            
        Returns:
            {'sights': int, 'foods': int, 'cafes': int}
        """
        pass
    
    def adjust_for_user_preferences(
        self, 
        distribution: Dict[str, int], 
        user_data: Dict[str, Any]
    ) -> Dict[str, int]:
        """
        사용자 선호도에 따라 장소 분배 조정

        - style: 사용자가 선택한 스타일에 맞게 각 테마 내 비중 보정 (±1)
        - pace/아이동반: 기존 로직 유지
        """
        styles = set(user_data.get('style', []))

        # ── style 기반 보정 (테마의 기본 성격을 유지하면서 사용자 취향 반영) ──
        # 맛집/휴양 선호 → 모든 테마에서 음식 슬롯 최소 1개 이상 확보
        if styles & {'맛집', '휴양', '카페투어'}:
            distribution['foods'] = max(distribution['foods'], 1)
            if '카페투어' in styles:
                distribution['cafes'] = max(distribution['cafes'], 1)
        # 자연/관광/문화 선호 → 관광 슬롯 최소 1개 이상 확보
        if styles & {'자연', '관광', '문화', '역사/문화'}:
            distribution['sights'] = max(distribution['sights'], 1)
        # 액티비티/쇼핑 선호 → 관광 슬롯 소폭 상향
        if styles & {'액티비티', '쇼핑'}:
            distribution['sights'] = min(4, distribution['sights'] + 1)

        # ── 일정 강도에 따른 조절 (기존 로직) ─────────────────────────────
        pace = user_data.get('pace', '보통')
        if pace == '여유' or '휴양' in styles:
            distribution['sights'] = max(1, distribution['sights'] - 1)
            distribution['foods']  = max(1, distribution['foods'] - 1)
            distribution['cafes']  = 1
        elif pace == '빡빡':
            distribution['sights'] = min(4, distribution['sights'] + 1)
            distribution['foods']  = min(3, distribution['foods'] + 1)
            distribution['cafes']  = 1
        
        # ── 동행인에 따른 조절 (기존 로직) ────────────────────────────────
        if user_data.get('with_kids'):
            distribution['sights'] = max(1, distribution['sights'] - 1)
            distribution['foods']  = max(1, distribution['foods'])
            distribution['cafes']  = 1
        
        if '커플' in user_data.get('companions', []):
            distribution['cafes'] = max(1, distribution['cafes'])
        
        return distribution
    
    def customize_schedule(
        self, 
        schedule: List[tuple], 
        user_data: Dict[str, Any]
    ) -> List[tuple]:
        """
        테마별 스케줄 커스터마이징 (기본 구현은 그대로 반환)
        
        Args:
            schedule: 기본 스케줄
            user_data: 사용자 입력 데이터
            
        Returns:
            커스터마이징된 스케줄
        """
        return schedule
