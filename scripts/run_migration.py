#!/usr/bin/env python3
# run_migration.py
"""
Pick&Go DB 마이그레이션 스크립트
=====================================
기존 PostgreSQL DB에 신규 컬럼을 안전하게 추가합니다.
이미 컬럼이 존재하면 건너뛰고, 데이터는 유지됩니다.

사용법:
    python run_migration.py

환경 변수:
    DATABASE_URL — PostgreSQL 접속 URL (.env 파일 또는 환경 변수에 설정)

추가되는 컬럼:
    places.sub_category  VARCHAR(100)  — 세부 카테고리 (예: 한식, 자연경관)
    places.review_count  INTEGER       — 리뷰 수 (점수 가중치 산정용)
    places.verified_at   TIMESTAMP     — 마지막 영업 확인 시각
"""

import os
import sys

# 프로젝트 루트 경로를 sys.path에 추가 (어디서 실행해도 import 가능)
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv
load_dotenv()  # .env 파일 로드

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError


def run_migration():
    """
    마이그레이션 실행 함수.

    각 단계는 독립적으로 실행됩니다.
    한 단계가 실패해도 나머지 단계는 계속 진행됩니다.
    """
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL 환경 변수가 설정되지 않았습니다.")
        print("   .env 파일에 DATABASE_URL=postgresql://... 형식으로 추가하세요.")
        sys.exit(1)

    engine = create_engine(db_url, echo=False)

    # ─── 마이그레이션 정의 ─────────────────────────────────────────────────
    # 각 항목: (단계 번호, 설명, SQL 구문)
    # IF NOT EXISTS 사용 → 이미 컬럼이 있어도 오류 없이 건너뜀
    migrations = [
        (
            1,
            "places 테이블에 sub_category 컬럼 추가 (세부 카테고리)",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS sub_category VARCHAR(100);"
        ),
        (
            2,
            "places 테이블에 review_count 컬럼 추가 (리뷰 수, 점수 가중치용)",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS review_count INTEGER DEFAULT 0;"
        ),
        (
            3,
            "places 테이블에 verified_at 컬럼 추가 (영업 확인 시각)",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP WITHOUT TIME ZONE;"
        ),
        (
            4,
            "sub_category 인덱스 생성 (카테고리 조회 성능 향상)",
            "CREATE INDEX IF NOT EXISTS idx_places_sub_category ON places (sub_category);"
        ),
        (
            5,
            "verified_at 인덱스 생성 (경고 배지 조회 성능 향상)",
            "CREATE INDEX IF NOT EXISTS idx_places_verified_at ON places (verified_at);"
        ),
        (
            6,
            "기존 장소 review_count NULL → 0으로 초기화",
            "UPDATE places SET review_count = 0 WHERE review_count IS NULL;"
        ),
        (
            7,
            "기존 장소 verified_at 초기화 (updated_at 기준, NULL인 장소만)",
            "UPDATE places SET verified_at = updated_at WHERE verified_at IS NULL AND updated_at IS NOT NULL;"
        ),
        (
            8,
            "places.rating_5star 컬럼 추가",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_5star INTEGER DEFAULT 0;"
        ),
        (
            9,
            "places.rating_4star 컬럼 추가",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_4star INTEGER DEFAULT 0;"
        ),
        (
            10,
            "places.rating_3star 컬럼 추가",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_3star INTEGER DEFAULT 0;"
        ),
        (
            11,
            "places.rating_2star 컬럼 추가",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_2star INTEGER DEFAULT 0;"
        ),
        (
            12,
            "places.rating_1star 컬럼 추가",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_1star INTEGER DEFAULT 0;"
        ),
    ]

    print("=" * 60)
    print("  Pick&Go DB 마이그레이션 시작")
    print("=" * 60)

    success_count = 0
    skip_count    = 0
    fail_count    = 0

    with engine.connect() as conn:
        for step, desc, sql in migrations:
            print(f"\n[Step {step}] {desc}")
            print(f"  SQL: {sql.strip()}")
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"  ✅ 완료")
                success_count += 1
            except OperationalError as e:
                # 컬럼이 이미 존재하거나 인덱스가 이미 있는 경우
                err_str = str(e).lower()
                if "already exists" in err_str or "duplicate column" in err_str:
                    print(f"  ⏭️  이미 존재 — 건너뜀")
                    skip_count += 1
                else:
                    print(f"  ❌ 오류: {e}")
                    fail_count += 1
            except Exception as e:
                print(f"  ❌ 예상치 못한 오류: {e}")
                fail_count += 1

    print("\n" + "=" * 60)
    print(f"  마이그레이션 완료 — 성공: {success_count}, 건너뜀: {skip_count}, 실패: {fail_count}")
    print("=" * 60)

    if fail_count > 0:
        print("\n⚠️  일부 단계가 실패했습니다. 로그를 확인하세요.")
        sys.exit(1)
    else:
        print("\n🎉 모든 마이그레이션이 성공적으로 완료되었습니다!")
        print("   이제 픽앤고 서버를 재시작하면 새 기능이 활성화됩니다.")


if __name__ == "__main__":
    run_migration()
