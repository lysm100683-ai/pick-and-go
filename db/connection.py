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
    """데이터베이스 테이블 생성 (Alembic 사용 전 임시)"""
    from db.models import Base
    Base.metadata.create_all(bind=engine)
    print("✅ 데이터베이스 테이블 생성 완료")
