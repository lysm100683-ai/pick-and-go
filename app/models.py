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
    with_kids: bool = False
    stroller: bool = False
    barrier_free: bool = False
    crowd_avoid: str = "보통"
    temp_range: Tuple[int, int] = (15, 25)
    rainy_ok: bool = False
    photo_spot: bool = False

    # Step 3. 고급 설정
    keywords: str = Field(default="", max_length=1000)
    time_constraints: str = Field(default="", max_length=1000)
    seat_pref: str = "무관"
    baggage: str = "기내만"
    max_transfers: int = 1
    english_ok: bool = False
    visa_free: bool = False

    # Step 4. 추가 입력형 조건 (입력형 20개 달성)
    food_allergy_text: str = Field(default="", max_length=1000, description="음식 알레르기 및 기피 음식")
    daily_budget_manwon: int = Field(default=30, ge=1, description="하루 총 예산 (만원)")
    preferred_airline: str = Field(default="", max_length=100, description="선호 항공사 (예: 대한항공, 아시아나)")
    interest_places: str = Field(default="", max_length=500, description="꼭 가보고 싶은 장소나 명소")
    trip_purpose: str = Field(default="", max_length=200, description="여행 목적 또는 테마 (예: 신혼여행, 가족 추억 여행)")
    notes: str = Field(default="", max_length=1000, description="기타 특이사항 또는 요청사항")
    arrival_time_pref: str = Field(default="", max_length=50, description="도착 희망 시간대 (예: 오전 10시 이전)")
    departure_time_pref: str = Field(default="", max_length=50, description="출발 희망 시간대 (예: 오후 3시 이후)")
    
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


# ----------------------------------------------------------------
# 3. 장소 부족 에러 응답 모델 [yeongmin]
# ----------------------------------------------------------------

class InsufficientPlacesDetail(BaseModel):
    """장소 부족 시 422 응답 구조 (프론트엔드 모달 안내용)"""
    city: str
    available: int
    required: int
    budget_level: str
    relaxed: bool = False
    message: str


# ----------------------------------------------------------------
# 4. 예약부 모델 (Reservation Models)
# ----------------------------------------------------------------

class PaymentInfo(BaseModel):
    """결제 정보"""
    method: str = Field(default="card", description="결제 수단: card, transfer")
    card_last4: Optional[str] = Field(default=None, description="카드 끝 4자리 (마스킹용)")
    budget_krw: int = Field(default=0, ge=0, description="총 예산 (원)")


class ReservationRequest(BaseModel):
    """
    Sub 1 예약 검증부 입력 모델
    처리부(일정 생성)의 출력을 그대로 전달받음
    """
    user_id: str = Field(..., description="사용자 식별자")
    user_email: Optional[str] = Field(default=None, description="예약 확정 이메일 수신 주소 (미입력 시 이메일 발송 생략)")
    itinerary_id: Optional[str] = Field(default=None, description="선택된 일정 ID")
    trip_data: dict = Field(..., description="선택된 일정 전체 데이터 (처리부 출력)")
    start_date: str = Field(..., description="여행 시작일 (YYYY-MM-DD)")
    end_date: str = Field(..., description="여행 종료일 (YYYY-MM-DD)")
    dest_city: str = Field(..., description="여행지 도시")
    dep_city: str = Field(..., description="출발지 도시")
    people: int = Field(..., ge=1, le=8, description="여행 인원")
    payment: PaymentInfo = Field(default_factory=PaymentInfo)


class ItemResult(BaseModel):
    """Sub 2 외부 예약 연동 결과 — 항목별"""
    item_type: str           # 'flight' | 'hotel'
    partner_name: str        # 파트너사 이름
    partner_booking_id: Optional[str] = None  # 성공 시 예약번호
    status: str              # 'confirmed' | 'failed'
    amount: float = 0.0
    currency: str = "KRW"
    details: dict = {}
    error_msg: Optional[str] = None


class ReservationResponse(BaseModel):
    """Sub 5 예약 성공 응답 모델"""
    reservation_id: str
    status: str = "confirmed"
    total_amount: float
    currency: str = "KRW"
    items: List[ItemResult] = []
    message: str = "예약이 확정되었습니다. 이메일로 영수증이 발송됩니다."


class ReservationFailResponse(BaseModel):
    """Sub 5 예약 실패 응답 모델"""
    status: str = "failed"
    error_code: str          # 'VALIDATION_ERROR' | 'BOOKING_FAILED' | 'ROLLBACK_COMPLETE' 등
    error_message: str
    retryable: bool = False  # 재시도 가능 여부
    failed_items: List[str] = []  # 실패한 항목 (flight/hotel)