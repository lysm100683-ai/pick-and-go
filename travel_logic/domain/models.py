# domain/models.py
"""
여행 일정 생성에 사용되는 데이터 모델
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class Place:
    """장소 정보"""
    id: str
    name: str
    lat: float
    lng: float
    category: str
    rating: float
    city: str = ""
    source: str = ""
    address: str = ""
    img_url: str = ""
    desc: str = ""
    score: int = 0
    matched_tags: List[str] = field(default_factory=list)
    is_start_point: bool = False
    type_key: str = ""
    
    def is_valid(self) -> bool:
        """좌표와 평점이 유효한지 확인"""
        return (
            self.lat != 0.0 and 
            self.lng != 0.0 and 
            self.rating > 0 and
            bool(self.name)
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Place':
        """딕셔너리에서 Place 객체 생성"""
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            lat=float(data.get('lat', 0.0)),
            lng=float(data.get('lng', 0.0)),
            category=data.get('category', ''),
            rating=float(data.get('rating', 0.0)),
            city=data.get('city', ''),
            source=data.get('source', ''),
            address=data.get('address', ''),
            img_url=data.get('img_url', ''),
            desc=data.get('desc', ''),
            score=int(data.get('score', 0)),
            matched_tags=data.get('matched_tags', []),
            is_start_point=data.get('is_start_point', False),
            type_key=data.get('type_key', '')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Place 객체를 딕셔너리로 변환"""
        return {
            'id': self.id,
            'name': self.name,
            'lat': self.lat,
            'lng': self.lng,
            'category': self.category,
            'rating': self.rating,
            'city': self.city,
            'source': self.source,
            'address': self.address,
            'img_url': self.img_url,
            'desc': self.desc,
            'score': self.score,
            'matched_tags': self.matched_tags,
            'is_start_point': self.is_start_point,
            'type_key': self.type_key
        }


@dataclass
class ItineraryItem:
    """일정 항목 (특정 시간에 방문할 장소)"""
    time: str
    type: str
    name: str
    desc: str
    address: str
    lat: float
    lng: float
    url: str
    raw_score: int
    img: str
    type_key: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ItineraryItem':
        """딕셔너리에서 ItineraryItem 객체 생성"""
        return cls(
            time=data.get('time', ''),
            type=data.get('type', ''),
            name=data.get('name', ''),
            desc=data.get('desc', ''),
            address=data.get('address', ''),
            lat=float(data.get('lat', 0.0)),
            lng=float(data.get('lng', 0.0)),
            url=data.get('url', ''),
            raw_score=int(data.get('raw_score', 0)),
            img=data.get('img', ''),
            type_key=data.get('type_key', '')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """ItineraryItem 객체를 딕셔너리로 변환"""
        return {
            'time': self.time,
            'type': self.type,
            'name': self.name,
            'desc': self.desc,
            'address': self.address,
            'lat': self.lat,
            'lng': self.lng,
            'url': self.url,
            'raw_score': self.raw_score,
            'img': self.img,
            'type_key': self.type_key
        }


@dataclass
class Day:
    """하루 일정"""
    day: int
    places: List[Dict[str, Any]]  # ItineraryItem의 딕셔너리 리스트
    
    def to_dict(self) -> Dict[str, Any]:
        """Day 객체를 딕셔너리로 변환"""
        return {
            'day': self.day,
            'places': self.places
        }


@dataclass
class Itinerary:
    """전체 여행 일정"""
    theme: str
    desc: str
    score: int
    tags: List[str]
    days: List[Dict[str, Any]]  # Day의 딕셔너리 리스트
    
    def to_dict(self) -> Dict[str, Any]:
        """Itinerary 객체를 딕셔너리로 변환"""
        return {
            'theme': self.theme,
            'desc': self.desc,
            'score': self.score,
            'tags': self.tags,
            'days': self.days
        }
