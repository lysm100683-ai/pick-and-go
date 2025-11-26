# app/models.py
from pydantic import BaseModel, Field
from typing import List, Tuple, Optional

# --- [요청 모델] 모든 입력 조건을 수용하는 완전한 모델 ---
class TravelCondition(BaseModel):
    # Step 1. 기본 정보
    dep_city: str
    dest_city: str
    start_date: str
    end_date: str
    people: int = Field(..., ge=1, le=10)
    companions: List[str] = []
    budget_level: str

    # Step 2. 상세 취향
    style: List[str] = []
    transport: List[str] = []
    pace: str = "보통"
    walk_minutes: int = 45
    lodging_types: List[str] = []
    star_rating: int = 4
    price_per_night_manwon: int = 20
    
    # 음식 및 편의
    food_prefs: List[str] = []
    food_allergy_text: str = ""
    with_kids: bool = False
    stroller: bool = False
    barrier_free: bool = False
    crowd_avoid: str = "보통"
    temp_range: Tuple[int, int] = (15, 25)
    rainy_ok: bool = False
    photo_spot: bool = False

    # Step 3. 고급 설정
    keywords: str = ""
    time_constraints: str = ""
    seat_pref: str = "무관"
    baggage: str = "기내만"
    max_transfers: int = 1
    english_ok: bool = False
    visa_free: bool = False

# --- [응답 모델] ---
class PlaceItem(BaseModel):
    time: str
    type: str
    name: str
    desc: str
    lat: float
    lng: float
    url: str
    raw_score: int
    img: str

class DayPlan(BaseModel):
    day: int
    places: List[PlaceItem]

class Itinerary(BaseModel):
    theme: str
    desc: str
    score: int
    tags: List[str]
    days: List[DayPlan]

class ItineraryResponse(BaseModel):
    plans: List[Itinerary]

# --- [DB 업데이트 모델] ---
class DBUpdateRequest(BaseModel):
    dest_city: str
    styles: List[str]