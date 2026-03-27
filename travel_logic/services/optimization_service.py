# services/optimization_service.py
"""
장소 선택 최적화 서비스
"""

import random
from typing import List, Dict, Any, Optional
from .distance_service import DistanceService


class OptimizationService:
    """Epsilon-greedy 및 Cost 기반 장소 선택 최적화"""
    
    def __init__(self, distance_service: DistanceService):
        self.distance_service = distance_service
    
    def select_next_place(
        self, 
        candidates: List[Dict[str, Any]], 
        current_place: Optional[Dict[str, Any]],
        strategy_weights: Dict[str, Any],
        is_korea: bool,
        mode: str,
        place_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Epsilon-greedy + Cost 기반으로 다음 방문 장소 선택
        
        Args:
            candidates: 후보 장소 리스트
            current_place: 현재 위치
            strategy_weights: 전략별 가중치 (W_time, W_score, epsilon, food_boost, sight_boost)
            is_korea: 국내 여행 여부
            mode: 이동 수단
            place_type: 장소 타입 ('식사', '카페', '관광')
            
        Returns:
            선택된 장소
        """
        if not candidates:
            return None
        
        epsilon = strategy_weights.get('epsilon', 0.05)
        
        # Epsilon-Greedy: epsilon 확률로 무작위 선택
        if random.random() < epsilon:
            return random.choice(candidates)
        
        # (1 - epsilon) 확률로 Cost 기반 최적화 선택
        selected = candidates[0]
        
        # 현재 위치가 유효한 경우에만 최적화 시도
        if current_place and current_place.get('lat', 0.0) != 0.0 and current_place.get('lng', 0.0) != 0.0:
            # 직선거리 기준 상위 10개 선택 (Top-5에서 확대 — 실제 이동 시간이 더 짧은 장소를 놓치지 않도록)
            candidates.sort(
                key=lambda p: self.distance_service.haversine_distance(
                    current_place['lat'], current_place['lng'], p['lat'], p['lng']
                )
            )
            top_candidates = candidates[:10]
            
            # 실제 이동시간 조회 (병렬, 캐시 우선)
            results = self.distance_service.get_travel_times_bulk(
                current_place['lat'], current_place['lng'], 
                top_candidates, is_korea, mode
            )
            
            # Cost 계산
            final_costs = []
            for travel_time, place in results:
                cost = self._calculate_cost(
                    travel_time, place, strategy_weights, place_type
                )
                final_costs.append((cost, place))
            
            # Cost가 가장 낮은 장소 선택
            final_costs.sort(key=lambda x: x[0])
            if final_costs:
                selected = final_costs[0][1]
        
        return selected
    
    def _calculate_cost(
        self, 
        travel_time: int, 
        place: Dict[str, Any],
        weights: Dict[str, Any],
        place_type: str
    ) -> float:
        """
        Cost 함수 계산
        
        Cost = W_time * TravelTime + W_score * (100 - Score)
        
        Args:
            travel_time: 이동시간 (초)
            place: 장소 정보
            weights: 가중치 정보
            place_type: 장소 타입
            
        Returns:
            Cost 값
        """
        W_time = weights.get('W_time', 0.1)
        W_score = weights.get('W_score', 10)
        
        # 테마별 부스트 적용
        boost = 0
        if place_type == '식사':
            boost = weights.get('food_boost', 0)
        elif place_type == '관광':
            boost = weights.get('sight_boost', 0)
        
        score = place.get('score', 50) + boost
        
        # Cost 계산
        cost = W_time * travel_time + W_score * (100 - score)
        
        return cost
