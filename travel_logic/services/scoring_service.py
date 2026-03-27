# services/scoring_service.py
"""
장소 점수 계산 및 필터링 서비스
"""

from typing import List, Dict, Any
from ..config.settings import DEFAULT_MIN_RATING


class ScoringService:
    """장소 점수 계산 및 필터링 담당"""
    
    @staticmethod
    def calculate_score(place: Dict[str, Any], user_data: Dict[str, Any]) -> tuple[int, List[str]]:
        """
        사용자 입력 조건을 반영하여 장소 점수 계산
        
        Args:
            place: 장소 정보
            user_data: 사용자 입력 데이터
            
        Returns:
            (점수, 매칭된 스타일 태그)
        """
        # 1. 기본 점수 (평점 기반)
        base = float(place.get('rating', 3.0)) * 10
        bonus = 0
        
        # 2. 스타일 매칭 점수
        style_keywords = {
            "휴양": ["beach", "park", "spa", "resort", "pool", "휴양", "해변", "공원"],
            "관광": ["museum", "tour", "historic", "monument", "attraction", "관광", "명소", "박물관", "유적"],
            "맛집": ["restaurant", "food", "dining", "cuisine", "식당", "음식점", "맛집"],
            "쇼핑": ["shopping", "mall", "market", "store", "쇼핑", "시장", "백화점"],
            "액티비티": ["activity", "sport", "adventure", "outdoor", "액티비티", "스포츠", "체험"],
            "자연": ["nature", "mountain", "forest", "lake", "river", "자연", "산", "숲", "호수"],
            "문화": ["culture", "art", "gallery", "theater", "문화", "예술", "갤러리", "극장"]
        }
        
        category_str = str(place.get('category', '')).lower()
        name_str = str(place.get('name', '')).lower()
        
        for style in user_data.get('style', []):
            if style in style_keywords:
                for keyword in style_keywords[style]:
                    if keyword.lower() in category_str or keyword.lower() in name_str:
                        bonus += 30  # 스타일 매칭 시 큰 보너스
                        break
        
        # 3. 사진 명소 선호 반영
        if user_data.get('photo_spot', False):
            photo_keywords = ["view", "scenic", "landmark", "tower", "전망", "뷰", "포토", "타워"]
            for keyword in photo_keywords:
                if keyword in category_str or keyword in name_str:
                    bonus += 20
                    break
        
        # 4. 어린이 동반 시 가족 친화적 장소 우대
        if user_data.get('with_kids', False):
            family_keywords = ["park", "zoo", "aquarium", "family", "kid", "공원", "동물원", "수족관", "가족"]
            for keyword in family_keywords:
                if keyword in category_str or keyword in name_str:
                    bonus += 25
                    break
            # 어린이 부적합 장소 감점
            avoid_keywords = ["bar", "club", "night", "술집", "나이트"]
            for keyword in avoid_keywords:
                if keyword in category_str or keyword in name_str:
                    bonus -= 50
                    break
        
        return min(100, int(base + bonus)), user_data.get('style', [])
    
    @staticmethod
    def filter_places(places: List[Dict[str, Any]], user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        사용자 선호도에 따라 장소 필터링
        
        Args:
            places: 장소 리스트
            user_data: 사용자 입력 데이터
            
        Returns:
            필터링된 장소 리스트
        """
        filtered = []
        
        for place in places:
            # 1. 평점 필터링 (최소 평점)
            min_rating = DEFAULT_MIN_RATING
            if user_data.get('budget_level') == '고':
                min_rating = 4.0
            elif user_data.get('budget_level') == '중':
                min_rating = 3.5
            
            if float(place.get('rating', 0)) < min_rating:
                continue
            
            # 2. 어린이 동반 시 부적합 장소 필터링
            if user_data.get('with_kids', False):
                category_str = str(place.get('category', '')).lower()
                name_str = str(place.get('name', '')).lower()
                avoid_keywords = ["bar", "club", "night", "adult", "술집", "나이트", "성인"]
                skip = False
                for keyword in avoid_keywords:
                    if keyword in category_str or keyword in name_str:
                        skip = True
                        break
                if skip:
                    continue
            
            # 3. 장애물 없는 접근성 필요 시
            if user_data.get('barrier_free', False) or user_data.get('stroller', False):
                # 장애물 없는 접근성 정보가 있으면 우대 (현재는 데이터 부족으로 스킵)
                pass
            
            filtered.append(place)
        
        return filtered
