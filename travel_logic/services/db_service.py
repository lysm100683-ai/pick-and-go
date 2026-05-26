# services/db_service.py
"""
DB 업데이트 및 데이터 수집 서비스
"""

import random
import sys
import os

# backend 모듈 import를 위한 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import backend_postgres as backend  # DB부: backend_postgres 사용 (PostGIS 기반)
from ..domain.validators import check_is_domestic


class DBService:
    """데이터베이스 업데이트 및 데이터 수집 담당"""
    
    @staticmethod
    def update_db(city: str, styles: list) -> dict:
        """
        도시 및 스타일에 따른 장소 데이터 수집 및 DB 업데이트
        
        Args:
            city: 도시명
            styles: 사용자 선호 스타일 리스트
            
        Returns:
            업데이트 결과 딕셔너리
        """
        try:
            keywords = []
            
            # 1. 사용자 스타일 기반 키워드
            for style in styles:
                keywords.append(f"{city} {style}")
            
            # 2. 해외 지역 필수 카테고리 및 영어 키워드 추가
            if not check_is_domestic(city):
                keywords.extend([
                    f"{city} restaurant", 
                    f"{city} hotel", 
                    f"{city} cafe", 
                    f"{city} shopping mall", 
                    f"{city} museum"
                ])
            
            # 3. 국내/해외 공통 키워드
            keywords.extend([f"{city} 식당", f"{city} 숙소"])
            
            # 4. API 캐시 우회 및 강제 다양화를 위한 랜덤 접미사 추가
            random_suffix = random.choice([
                f"unique spot {random.randint(100, 999)}",
                f"near {city} historical sites",
                f"best rated {random.choice(['food', 'sights'])}",
                f"hidden gem {random.randint(1, 10)}"
            ])
            keywords.append(f"{city} attractions {random_suffix}")
            
            # 5. 캐시 데이터 유통기한 정리 (180일 지난 낡은 메모 폐기)
            # 관리자/사용자가 DB 업데이트를 요청할 때 찌꺼기도 함께 청소합니다.
            backend.cleanup_old_movement_cache(days=180)
            
            is_domestic = check_is_domestic(city)
            
            # backend.fetch_all_data 호출
            result = backend.fetch_all_data(city, keywords, is_domestic=is_domestic)
            
            print(f"🎉 [DB Update] '{city}' 데이터 업데이트 완료. 추가된 장소: {result.get('added_count', 0)}개")
            return result
            
        except Exception as e:
            print(f"❌ [DB Update Error] '{city}' 데이터 업데이트 중 오류 발생: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def ensure_data_exists(city: str, styles: list) -> bool:
        """
        도시 데이터가 충분한지 확인하고, 부족하면 자동 업데이트
        
        Args:
            city: 도시명
            styles: 사용자 선호 스타일
            
        Returns:
            데이터 존재 여부
        """
        places = backend.get_places(city)
        
        if not places:
            print(f"⚠️ [Auto-Update] '{city}'에 대한 장소 데이터가 부족합니다. 데이터 수집을 시작합니다.")
            update_result = DBService.update_db(city, styles)
            
            # 업데이트 후 다시 확인
            places = backend.get_places(city)
            
            if not places:
                print(f"❌ [Auto-Update Failed] DB 업데이트 후에도 '{city}' 데이터 로드 실패.")
                return False
            else:
                print(f"✅ [Auto-Update Success] '{city}' 신규 데이터 {update_result.get('added_count', 0)}개 로드 완료.")
                return True
        
        return True
