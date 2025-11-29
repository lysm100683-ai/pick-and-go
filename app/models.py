# app/models.py
from pydantic import BaseModel, Field
from typing import List, Tuple, Optional

# ----------------------------------------------------------------
# 1. 요청 모델 (Request Models)
# ----------------------------------------------------------------

# --- [TravelCondition] 모든 입력 조건을 수용하는 완전한 모델 ---
class TravelCondition(BaseModel):
    """여행 일정 생성을 위한 상세 입력 조건"""
    
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
    local_transport: str = Field(default="자차", description="여행지 내 이동 수단: 자차, 렌트카, 대중교통") 
    pace: str = "보통"
    walk_minutes: int = 45
    lodging_types: List[str] = []
    star_rating: int = 4
    price_per_night_manwon: int = 20
    
    # 🚀 NEW: 희망 숙소 수 필드 추가
    num_hotels: int = Field(default=1, ge=1, description="전체 일정 중 숙소 변경 횟수 (1이면 고정)")
    
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
    
# --- [DBUpdateRequest] 데이터 수집 요청 모델 ---
class DBUpdateRequest(BaseModel):
    """백그라운드 DB 업데이트 요청을 위한 모델"""
    dest_city: str
    styles: List[str]

# ----------------------------------------------------------------
# 2. 응답 모델 (Response Models)
# ----------------------------------------------------------------

class PlaceItem(BaseModel):
    """일정 내 개별 장소 정보"""
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
    """하루 일정"""
    day: int
    places: List[PlaceItem]

class Itinerary(BaseModel):
    """테마별 일정"""
    theme: str
    desc: str
    score: int
    tags: List[str]
    days: List[DayPlan]

class ItineraryResponse(BaseModel):
    """최종 일정 추천 결과"""
    plans: List[Itinerary]