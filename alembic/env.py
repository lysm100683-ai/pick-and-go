# alembic/env.py — 마이그레이션 실행 환경 설정
#
# [비개발자 설명]
# 이 파일은 Alembic이 마이그레이션을 실행할 때 동작하는 핵심 스크립트입니다.
# 아래 세 가지 역할을 합니다:
#   1. .env 파일에서 DB 접속 정보(DATABASE_URL)를 읽어 연결
#   2. 현재 ORM 모델(Place, MovementCache, Reservation)과
#      실제 DB 테이블 구조를 비교해 차이를 자동 감지
#   3. 마이그레이션을 온라인(DB 실시간 연결) 또는 오프라인(SQL 파일 출력) 방식으로 실행

import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# 프로젝트 루트를 Python 경로에 추가해야 db/models.py 등을 import 할 수 있음
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .env 파일 로드 (DATABASE_URL, API 키 등)
# → 이 코드 덕분에 alembic.ini에 DB 주소를 직접 쓰지 않아도 됨
load_dotenv()

# Alembic 설정 객체 (alembic.ini 내용을 읽어옴)
config = context.config

# alembic.ini에 정의된 로깅 설정 적용 (터미널 출력 형식)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ORM 메타데이터 연결
# → Alembic이 Place, MovementCache, Reservation 모델을 인식하여
#   실제 DB 테이블과 비교할 수 있게 됨
from db.models import Base
target_metadata = Base.metadata

# .env의 DATABASE_URL을 Alembic 설정에 주입
# → alembic.ini의 sqlalchemy.url 빈칸을 런타임에 채워줌
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL 환경 변수가 설정되지 않았습니다. "
        ".env 파일에 DATABASE_URL을 추가해 주세요."
    )
config.set_main_option("sqlalchemy.url", database_url)


def include_object(object, name, type_, reflected, compare_to):
    """
    [보안 가드레일]
    DB 관리자가 우리 앱과 상관없는 시스템 공간(Supabase 등)의 테이블을 
    불필요하게 지우거나 건드리지 못하게 차단벽을 구축합니다.
    """
    if type_ == "table":
        # 우리가 파이썬에 직접 설계한 테이블표(target_metadata.tables)와
        # 마이그레이션 도구가 쓰는 자기 자신의 테이블(alembic_version)만 취급을 '허용'합니다.
        # 그 외의 모든 낯선 테이블(system, auth, storage 등)은 '무시'합니다.
        if name == "alembic_version" or name in target_metadata.tables:
            return True
        return False
    return True


def run_migrations_offline() -> None:
    """
    오프라인 모드 마이그레이션 — SQL 파일로 출력
    
    [비개발자 설명]
    DB에 직접 연결하지 않고 변경에 필요한 SQL 구문을 파일로만 출력합니다.
    DBA(DB 관리자)가 직접 검토 후 실행할 때 사용합니다.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,           # 컬럼 타입 변경도 감지 (예: VARCHAR → TEXT)
        compare_server_default=True, # 기본값 변경도 감지
        include_object=include_object, # 🚧 보안 가드레일 작동
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    온라인 모드 마이그레이션 — DB에 직접 연결하여 실행
    
    [비개발자 설명]
    실제 DB에 연결해 마이그레이션을 즉시 적용합니다.
    'alembic upgrade head' 명령 실행 시 이 함수가 호출됩니다.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        # NullPool: 마이그레이션은 짧은 작업이므로 커넥션 풀 불필요
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,           # 컬럼 타입 변경 감지
            compare_server_default=True, # 서버 기본값 변경 감지
            include_schemas=False,       # PostGIS 등 불필요한 전체 스키마 순회 방지
            include_object=include_object, # 🚧 보안 가드레일 작동
        )
        with context.begin_transaction():
            context.run_migrations()


# 실행 모드 판단: alembic 명령 방식에 따라 자동 선택됨
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
