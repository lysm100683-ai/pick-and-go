# config.py - 중앙 설정 관리
"""
애플리케이션 설정을 중앙에서 관리합니다.
환경 변수를 한 번만 로드하고 검증합니다.
"""
from dotenv import load_dotenv
import os
import logging

# 환경 변수 로드 (한 번만 실행)
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pickandgo.log'),
        logging.StreamHandler()
    ]
)


class Config:
    """애플리케이션 설정 클래스"""
    
    # 데이터베이스 설정
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    # API 키
    GMAPS_API_KEY = os.getenv('GMAPS_API_KEY')
    KAKAO_REST_KEY = os.getenv('KAKAO_REST_KEY')
    
    # 캐시 설정
    CACHE_EXPIRY_SECONDS = int(os.getenv('CACHE_EXPIRY_SECONDS', '3600'))
    
    # 데이터베이스 연결 풀 설정
    DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '10'))
    DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '20'))
    
    # 성능 설정
    CACHE_MATCH_TOLERANCE_METERS = 100  # 캐시 매칭 허용 오차 (미터)
    
    @classmethod
    def validate(cls):
        """필수 설정 검증"""
        errors = []
        
        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL 환경 변수가 설정되지 않았습니다.")
        
        # 프로덕션 환경에서는 API 키 필수
        if os.getenv('ENVIRONMENT') == 'production':
            if not cls.GMAPS_API_KEY or cls.GMAPS_API_KEY == 'YOUR_GOOGLE_MAPS_API_KEY':
                errors.append("GMAPS_API_KEY가 올바르게 설정되지 않았습니다.")
            
            if not cls.KAKAO_REST_KEY or cls.KAKAO_REST_KEY == 'YOUR_KAKAO_REST_API_KEY':
                errors.append("KAKAO_REST_KEY가 올바르게 설정되지 않았습니다.")
        
        if errors:
            error_msg = "\n".join(errors)
            raise ValueError(f"설정 검증 실패:\n{error_msg}\n\n.env 파일을 확인해주세요.")
        
        return True


# 애플리케이션 시작 시 설정 검증 (선택적)
# Config.validate()  # 주석 해제하면 시작 시 검증
