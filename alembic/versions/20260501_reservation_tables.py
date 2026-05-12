"""20260501_reservation_tables

Revision ID: a1b2c3d4e5f6
Revises: 20260403_1435_verify_guardrail
Create Date: 2026-05-01 00:08:00

[비개발자 설명]
이 파일은 예약부 구현을 위한 DB 구조 변경 이력입니다.

추가 테이블 3개:
  1. reservations      — 예약 기본 정보 (예약ID, 사용자, 상태, 총금액)
  2. reservation_items — 예약 세부 항목 (항공/숙소 각 1행)
  3. reservation_logs  — 예약 처리 이력 (성공/실패 이벤트)

기존 reservations 테이블:
  - Integer PK + trip_data(JSONB) + status 구조였음
  - UUID PK + itinerary_id + total_amount + people 컬럼 추가로 확장
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '20260403_1435'   # verify_guardrail 다음
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    예약부 DB 구조 생성
    → 'alembic upgrade head' 실행 시 호출
    """
    # ── 1. reservations 테이블 재구성 ──────────────────────────
    # 기존 테이블 삭제 후 재생성 (데이터가 없다면 DROP CASCADE 사용)
    op.drop_table('reservations')

    op.create_table(
        'reservations',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',      sa.String(100), nullable=False),
        sa.Column('itinerary_id', sa.String(100)),
        sa.Column('trip_data',    JSONB, nullable=False),
        sa.Column('status',       sa.String(20), nullable=False, server_default='pending'),
        sa.Column('total_amount', sa.Numeric(12, 2), server_default='0'),
        sa.Column('currency',     sa.String(10), server_default='KRW'),
        sa.Column('people',       sa.Integer, server_default='1'),
        sa.Column('created_at',   sa.TIMESTAMP, server_default=sa.text('now()')),
        sa.Column('updated_at',   sa.TIMESTAMP, server_default=sa.text('now()')),
    )
    op.create_index('idx_reservations_user_id',   'reservations', ['user_id'])
    op.create_index('idx_reservations_status',    'reservations', ['status'])
    op.create_index('idx_reservations_created_at','reservations', ['created_at'])

    # ── 2. reservation_items 테이블 생성 ───────────────────────
    op.create_table(
        'reservation_items',
        sa.Column('id',                UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('reservation_id',    UUID(as_uuid=True), sa.ForeignKey('reservations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('item_type',         sa.String(20), nullable=False),
        sa.Column('partner_name',      sa.String(100)),
        sa.Column('partner_booking_id',sa.String(200)),
        sa.Column('status',            sa.String(20), nullable=False, server_default='pending'),
        sa.Column('amount',            sa.Numeric(12, 2), server_default='0'),
        sa.Column('currency',          sa.String(10), server_default='KRW'),
        sa.Column('details',           JSONB),
        sa.Column('created_at',        sa.TIMESTAMP, server_default=sa.text('now()')),
    )
    op.create_index('idx_res_items_reservation_id', 'reservation_items', ['reservation_id'])
    op.create_index('idx_res_items_type',           'reservation_items', ['item_type'])

    # ── 3. reservation_logs 테이블 생성 ────────────────────────
    op.create_table(
        'reservation_logs',
        sa.Column('id',             sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('reservation_id', UUID(as_uuid=True), sa.ForeignKey('reservations.id', ondelete='SET NULL')),
        sa.Column('action_type',    sa.String(50), nullable=False),
        sa.Column('sub_system',     sa.String(30)),
        sa.Column('result',         sa.String(20)),
        sa.Column('payload',        JSONB),
        sa.Column('created_at',     sa.TIMESTAMP, server_default=sa.text('now()')),
    )
    op.create_index('idx_res_logs_reservation_id', 'reservation_logs', ['reservation_id'])
    op.create_index('idx_res_logs_action_type',    'reservation_logs', ['action_type'])


def downgrade() -> None:
    """
    예약부 DB 구조 롤백
    → 'alembic downgrade -1' 실행 시 호출
    """
    op.drop_table('reservation_logs')
    op.drop_table('reservation_items')
    op.drop_table('reservations')

    # reservations 테이블 원복 (구버전 스키마)
    op.create_table(
        'reservations',
        sa.Column('id',         sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id',    sa.String(100), nullable=False),
        sa.Column('trip_data',  JSONB, nullable=False),
        sa.Column('status',     sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.text('now()')),
    )
    op.create_index('idx_reservations_user_id', 'reservations', ['user_id'])
    op.create_index('idx_reservations_status',  'reservations', ['status'])
