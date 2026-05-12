"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

[비개발자 설명]
이 파일은 DB 구조 변경 이력 하나를 담는 파일입니다.
upgrade() 함수: 변경 사항을 DB에 적용합니다.
downgrade() 함수: 변경 사항을 되돌립니다 (롤백).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# 이 마이그레이션 파일의 고유 ID (자동 생성됨)
revision: str = ${repr(up_revision)}
# 바로 이전 버전의 ID (연결 고리 역할)
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """
    DB 구조 변경 적용
    → 'alembic upgrade head' 명령 실행 시 이 함수가 호출됩니다.
    """
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """
    DB 구조 변경 롤백 (이전 상태로 되돌리기)
    → 'alembic downgrade -1' 명령 실행 시 이 함수가 호출됩니다.
    """
    ${downgrades if downgrades else "pass"}
