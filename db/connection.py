# db/connection.py - 데이터베이스 연결 관리
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from config import Config

# SQLAlchemy 엔진 생성
engine = create_engine(
    Config.DATABASE_URL,
    pool_size=Config.DB_POOL_SIZE,
    max_overflow=Config.DB_MAX_OVERFLOW,
    pool_pre_ping=True,    # 연결 유효성 자동 검사
    pool_recycle=3600,     # 1시간마다 연결 재활용
    echo=False             # SQL 쿼리 로깅 (개발 시 True로 변경)
)

# 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db_session() -> Session:
    """
    데이터베이스 세션 컨텍스트 매니저
    
    Usage:
        with get_db_session() as session:
            places = session.query(Place).all()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """
    [주의] 이 함수는 최초 개발 환경 세팅 시에만 사용하세요.
    이후 DB 구조 변경은 반드시 Alembic으로 관리합니다.

    [비개발자 설명]
    이 함수는 DB에 테이블이 전혀 없을 때 처음 만들어주는 역할입니다.
    테이블이 이미 있으면 아무 것도 하지 않습니다.
    한 번 만든 이후의 구조 변경(컬럼 추가 등)은 Alembic으로 관리합니다.

    DB 구조 변경 절차 (Alembic):
      1. db/models.py 에서 ORM 모델 수정
      2. alembic revision --autogenerate -m "변경 내용 요약"
         → alembic/versions/ 폴더에 변경 이력 파일 자동 생성
      3. alembic upgrade head
         → 실제 DB에 변경 사항 적용
      4. 문제 발생 시: alembic downgrade -1  → 바로 이전 상태로 롤백
    """
    from db.models import Base
    Base.metadata.create_all(bind=engine)
    print("데이터베이스 테이블 생성 완료")
