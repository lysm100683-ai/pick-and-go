# db/models.py - SQLAlchemy ORM 모델 (PostGIS 지원)
from sqlalchemy import Column, String, DECIMAL, Text, TIMESTAMP, Boolean, Integer, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from geoalchemy2 import Geography
import uuid

Base = declarative_base()


class Place(Base):
    """장소 정보 테이블 (PostGIS 지리공간 타입 사용)"""
    __tablename__ = 'places'
    
    id = Column(String(100), primary_key=True)
    source = Column(String(50), nullable=False)  # 'google', 'kakao', etc.
    name = Column(String(200), nullable=False)
    city = Column(String(100), nullable=False)
    category = Column(String(100))
    
    # 🚀 PostGIS Geography 타입 (EPSG:4326 WGS84)
    location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    
    address = Column(Text)
    rating = Column(DECIMAL(2, 1), default=0.0)
    img_url = Column(Text)
    description = Column(Text)
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # 인덱스 정의
    __table_args__ = (
        Index('idx_places_location', 'location', postgresql_using='gist'),
        Index('idx_places_city', 'city'),
        Index('idx_places_category', 'category'),
        Index('idx_places_rating', 'rating'),
    )
    
    def to_dict(self, session=None):
        """ORM 객체를 딕셔너리로 변환"""
        if session:
            # PostGIS 좌표 추출
            coords = session.execute(
                func.ST_AsText(self.location)
            ).scalar()
            # POINT(lng lat) 형식 파싱
            lng, lat = map(float, coords.replace('POINT(', '').replace(')', '').split())
        else:
            lat, lng = 0.0, 0.0
        
        return {
            'id': self.id,
            'source': self.source,
            'name': self.name,
            'city': self.city,
            'category': self.category,
            'lat': lat,
            'lng': lng,
            'address': self.address,
            'rating': float(self.rating) if self.rating else 0.0,
            'img_url': self.img_url,
            'desc': self.description
        }


class MovementCache(Base):
    """이동 시간 캐시 테이블"""
    __tablename__ = 'movement_cache'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    origin = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    destination = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    mode = Column(String(20), nullable=False)  # 'driving', 'transit', 'walking'
    duration_seconds = Column(Integer, nullable=False)
    is_korea = Column(Boolean, default=False)
    cached_at = Column(TIMESTAMP, server_default=func.now())
    
    __table_args__ = (
        # 중복 API 호출 방지를 위한 복합 인덱스
        Index('idx_movement_cache_lookup', 'origin', 'destination', 'mode'),
    )


class Reservation(Base):
    """예약 정보 테이블 (Phase 4에서 활용)"""
    __tablename__ = 'reservations'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(100), nullable=False)
    itinerary_data = Column(Text, nullable=False)  # JSON 문자열
    
    status = Column(String(20), nullable=False, default='pending')
    payment_id = Column(String(100))
    total_amount = Column(DECIMAL(10, 2))
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    confirmed_at = Column(TIMESTAMP)
    
    __table_args__ = (
        Index('idx_reservations_user_id', 'user_id'),
        Index('idx_reservations_status', 'status'),
    )
