# db/models.py - SQLAlchemy ORM 모델 (PostGIS 지원)
# merge: Place 확장(yeongmin) + Reservation 전체 구조(main) 통합
from sqlalchemy import Column, String, DECIMAL, Text, TIMESTAMP, Boolean, Integer, Index, JSON, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from geoalchemy2 import Geography
import uuid

Base = declarative_base()


class Place(Base):
    """장소 정보 테이블 (PostGIS 지리공간 타입 사용)"""
    __tablename__ = 'places'

    id = Column(String(100), primary_key=True)
    source = Column(String(50), nullable=False)   # 'google', 'kakao', etc.
    name = Column(String(200), nullable=False)
    city = Column(String(100), nullable=False)
    category = Column(String(100))
    sub_category = Column(String(100))            # 세부 카테고리 (예: "한식", "자연경관") [yeongmin]

    # PostGIS Geography 타입 (EPSG:4326 WGS84)
    location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)

    address = Column(Text)
    rating = Column(DECIMAL(2, 1), default=0.0)
    review_count = Column(Integer, default=0)     # 전체 리뷰 수 — 베이지안 점수 계산 [yeongmin]

    # 별점 분포 — Google Place Details 상위 5개 리뷰 기반 누적 [yeongmin]
    rating_5star = Column(Integer, default=0)
    rating_4star = Column(Integer, default=0)
    rating_3star = Column(Integer, default=0)
    rating_2star = Column(Integer, default=0)
    rating_1star = Column(Integer, default=0)

    img_url = Column(Text)
    description = Column(Text)

    created_at  = Column(TIMESTAMP, server_default=func.now())
    updated_at  = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    verified_at = Column(TIMESTAMP, nullable=True)  # 영업 여부 마지막 확인 시각 [yeongmin]

    __table_args__ = (
        Index('idx_places_location',     'location', postgresql_using='gist'),
        Index('idx_places_city',         'city'),
        Index('idx_places_category',     'category'),
        Index('idx_places_sub_category', 'sub_category'),
        Index('idx_places_rating',       'rating', postgresql_ops={'rating': 'DESC'}),
        Index('idx_places_verified_at',  'verified_at'),
    )

    def to_dict(self, session=None):
        """ORM 객체를 딕셔너리로 변환"""
        if session:
            coords = session.execute(func.ST_AsText(self.location)).scalar()
            lng, lat = map(float, coords.replace('POINT(', '').replace(')', '').split())
        else:
            lat, lng = 0.0, 0.0

        return {
            'id':           self.id,
            'source':       self.source,
            'name':         self.name,
            'city':         self.city,
            'category':     self.category,
            'sub_category': self.sub_category or '',
            'lat':          lat,
            'lng':          lng,
            'address':      self.address,
            'rating':       float(self.rating) if self.rating else 0.0,
            'review_count': int(self.review_count) if self.review_count else 0,
            'rating_5star': int(self.rating_5star) if self.rating_5star else 0,
            'rating_4star': int(self.rating_4star) if self.rating_4star else 0,
            'rating_3star': int(self.rating_3star) if self.rating_3star else 0,
            'rating_2star': int(self.rating_2star) if self.rating_2star else 0,
            'rating_1star': int(self.rating_1star) if self.rating_1star else 0,
            'img_url':      self.img_url,
            'desc':         self.description,
            'verified_at':  self.verified_at.isoformat() if self.verified_at else None,
            'updated_at':   self.updated_at.isoformat() if self.updated_at else None,
        }


class MovementCache(Base):
    """이동 시간 캐시 테이블"""
    __tablename__ = 'movement_cache'

    id = Column(Integer, primary_key=True, autoincrement=True)
    origin = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    destination = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    mode = Column(String(20), nullable=False)     # 'driving', 'transit', 'walking'
    duration_seconds = Column(Integer, nullable=False)
    is_korea = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index('idx_movement_cache_origin',      'origin',      postgresql_using='gist'),
        Index('idx_movement_cache_destination', 'destination', postgresql_using='gist'),
    )


class Reservation(Base):
    """
    예약 기본 정보 테이블 (Sub3 확정 검증 결과 저장)
    reservations — 예약 ID(UUID), 사용자, 상태, 총 금액
    """
    __tablename__ = 'reservations'

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(String(100), nullable=False)
    itinerary_id = Column(String(100))               # 처리부에서 넘어온 일정 식별자
    trip_data    = Column(JSONB, nullable=False)      # 일정 원본 데이터
    status       = Column(String(20), nullable=False, default='pending')
    total_amount = Column(Numeric(12, 2), default=0)
    currency     = Column(String(10), default='KRW')
    people       = Column(Integer, default=1)
    created_at   = Column(TIMESTAMP, server_default=func.now())
    updated_at   = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_reservations_user_id',    'user_id'),
        Index('idx_reservations_status',     'status'),
        Index('idx_reservations_created_at', 'created_at'),
    )


class ReservationItem(Base):
    """
    예약 세부 항목 테이블 (항공 or 숙소 각 1행)
    reservation_items — 파트너별 예약 결과
    """
    __tablename__ = 'reservation_items'

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reservation_id     = Column(UUID(as_uuid=True), ForeignKey('reservations.id', ondelete='CASCADE'), nullable=False)
    item_type          = Column(String(20), nullable=False)   # 'flight' | 'hotel'
    partner_name       = Column(String(100))
    partner_booking_id = Column(String(200))
    status             = Column(String(20), nullable=False, default='pending')
    amount             = Column(Numeric(12, 2), default=0)
    currency           = Column(String(10), default='KRW')
    details            = Column(JSONB)
    created_at         = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index('idx_res_items_reservation_id', 'reservation_id'),
        Index('idx_res_items_type',           'item_type'),
    )


class ReservationLog(Base):
    """
    예약 처리 이력 테이블 (Sub4 저장 — 히스토리 + SRS M-13 통계)
    reservation_logs — 성공/실패/시도 모든 이벤트 기록
    """
    __tablename__ = 'reservation_logs'

    id             = Column(Integer, primary_key=True, autoincrement=True)
    reservation_id = Column(UUID(as_uuid=True), ForeignKey('reservations.id', ondelete='SET NULL'))
    action_type    = Column(String(50), nullable=False)  # 'attempt'|'success'|'failure'|'cancel'|'rollback'
    sub_system     = Column(String(30))                  # 'sub1'~'sub5'
    result         = Column(String(20))                  # 'ok' | 'error'
    payload        = Column(JSONB)
    created_at     = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index('idx_res_logs_reservation_id', 'reservation_id'),
        Index('idx_res_logs_action_type',    'action_type'),
    )
