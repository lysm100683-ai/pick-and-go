# app/reservation/sub2_external.py
"""
Sub 2 — 외부 예약 연동 관리부
설계도 흐름:
  1. 예약이 필요한 일정 요소 분리 (항공 + 숙소)
  2. 예약 파트너 API 형식으로 데이터 변환
  3. asyncio.gather()로 병렬 예약 시도 (항공 + 숙소 동시)
  4. 성공/실패 분리
  5. 하나라도 실패 → 이미 성공한 것도 취소(롤백) → 전체 실패 반환
  6. 모두 성공 → 예약 결과 리스트 반환

환경변수:
  MOCK_FLIGHT=true       → Mock 항공 예약 사용 (기본값 / false 시 Duffel 실 API)
  MOCK_HOTEL=true        → Mock 숙소 예약 사용 (기본값)
  DUFFEL_API_KEY=...     → Duffel 발급 API 토큰 (MOCK_FLIGHT=false 시 필수)
"""
import asyncio
import os
import uuid
import random
from typing import List, Dict, Any


MOCK_FLIGHT = os.getenv("MOCK_FLIGHT", "true").lower() == "true"
MOCK_HOTEL  = os.getenv("MOCK_HOTEL",  "true").lower() == "true"

# Mock 성공률 (환경변수로 조정 가능 — 실패 시뮬레이션: 0.95, 항상 성공: 1.0)
MOCK_FLIGHT_SUCCESS_RATE = float(os.getenv("MOCK_FLIGHT_SUCCESS_RATE", "1.0"))
MOCK_HOTEL_SUCCESS_RATE  = float(os.getenv("MOCK_HOTEL_SUCCESS_RATE",  "1.0"))

# 파트너사 API 응답 대기 타임아웃 (초) — 초과 시 실패로 처리 후 Saga 롤백 발동
BOOKING_TIMEOUT_SEC = float(os.getenv("BOOKING_TIMEOUT_SEC", "10.0"))


class BookingFailedError(Exception):
    """Sub 2 예약 실패 예외 (롤백 완료 포함)"""
    def __init__(self, failed_items: List[str], message: str, retryable: bool = True):
        self.failed_items = failed_items
        self.message = message
        self.retryable = retryable
        super().__init__(message)


# ── Mock API 함수들 ────────────────────────────────────────────────

async def _mock_book_flight(context: dict) -> dict:
    """
    Mock 항공 예약 (Amadeus API 대체)
    실제 연동 시 이 함수만 교체하면 됨
    """
    await asyncio.sleep(random.uniform(0.3, 1.2))  # API 응답 시뮬레이션

    success = random.random() < MOCK_FLIGHT_SUCCESS_RATE
    if success:
        return {
            "item_type": "flight",
            "partner_name": "amadeus_mock",
            "partner_booking_id": f"FL-{uuid.uuid4().hex[:8].upper()}",
            "status": "confirmed",
            "amount": random.randint(150_000, 600_000) * context.get("people", 1),
            "currency": "KRW",
            "details": {
                "flight_no": f"KE{random.randint(100, 999)}",
                "dep": context.get("dep_city", "ICN"),
                "arr": context.get("dest_city", "NRT"),
                "departure_date": context.get("start_date"),
                "return_date": context.get("end_date"),
                "seats": context.get("people", 1),
                "class": "Economy",
            },
            "error_msg": None,
        }
    else:
        return {
            "item_type": "flight",
            "partner_name": "amadeus_mock",
            "partner_booking_id": None,
            "status": "failed",
            "amount": 0,
            "currency": "KRW",
            "details": {},
            "error_msg": "항공편 좌석 부족 또는 일시적 오류 (Mock)",
        }


async def _mock_book_hotel(context: dict) -> dict:
    """
    Mock 숙소 예약 (Booking.com API 대체)
    실제 연동 시 이 함수만 교체하면 됨
    """
    await asyncio.sleep(random.uniform(0.2, 1.0))  # API 응답 시뮬레이션

    success = random.random() < MOCK_HOTEL_SUCCESS_RATE
    if success:
        return {
            "item_type": "hotel",
            "partner_name": "booking_com_mock",
            "partner_booking_id": f"HT-{uuid.uuid4().hex[:8].upper()}",
            "status": "confirmed",
            "amount": random.randint(80_000, 300_000) * context.get("duration", 1),
            "currency": "KRW",
            "details": {
                "hotel_name": f"{context.get('dest_city', '여행지')} 대표 호텔 (Mock)",
                "check_in": context.get("start_date"),
                "check_out": context.get("end_date"),
                "nights": context.get("duration", 1),
                "rooms": max(1, context.get("people", 1) // 2),
            },
            "error_msg": None,
        }
    else:
        return {
            "item_type": "hotel",
            "partner_name": "booking_com_mock",
            "partner_booking_id": None,
            "status": "failed",
            "amount": 0,
            "currency": "KRW",
            "details": {},
            "error_msg": "숙소 객실 소진 또는 일시적 오류 (Mock)",
        }


async def _with_timeout(coro, item_type: str) -> dict:
    """
    개별 예약 코루틴에 타임아웃 적용 (SRS M-14: 파트너사 응답 10초 초과 시 실패 처리).
    asyncio.TimeoutError 발생 시 실패 딕셔너리를 반환하여 Saga 롤백 흐름으로 진입.
    """
    try:
        return await asyncio.wait_for(coro, timeout=BOOKING_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        return {
            "item_type":          item_type,
            "partner_name":       "timeout",
            "partner_booking_id": None,
            "status":             "failed",
            "amount":             0,
            "currency":           "KRW",
            "details":            {},
            "error_msg": (
                f"파트너사 응답 없음 — {BOOKING_TIMEOUT_SEC:.0f}초 초과 (TimeoutError)"
            ),
        }


async def _cancel_item(item: dict) -> None:
    """
    예약 취소 API 호출 (롤백용 — Saga 보상 트랜잭션).
    MOCK_FLIGHT=false 이고 item_type == 'flight' 이면 Duffel 실 취소 API 호출.
    그 외(Mock, 숙소)는 시뮬레이션.
    """
    booking_id = item.get("partner_booking_id")
    if not booking_id:
        return

    item_type = item.get("item_type", "unknown")

    # Duffel 실 항공 취소
    if item_type == "flight" and not MOCK_FLIGHT:
        try:
            await asyncio.to_thread(_duffel_cancel_order, booking_id)
            print(f"[Sub2] 롤백(Duffel): flight {booking_id} 취소 완료")
        except Exception as e:
            print(f"[Sub2] 롤백 경고: flight {booking_id} 취소 실패 — {e}")
    # LiteAPI 실 숙소 취소
    elif item_type == "hotel" and not MOCK_HOTEL:
        try:
            await asyncio.to_thread(_liteapi_cancel_hotel, booking_id)
            print(f"[Sub2] 롤백(LiteAPI): hotel {booking_id} 취소 완료")
        except Exception as e:
            print(f"[Sub2] 롤백 경고: hotel {booking_id} 취소 실패 — {e}")
    else:
        # Mock 취소 시뮬레이션
        await asyncio.sleep(0.1)
        print(f"[Sub2] 롤백(Mock): {item_type} {booking_id} 취소 처리")


# ── 메인 함수 ──────────────────────────────────────────────────────

async def book_parallel(validated_context: dict) -> List[dict]:
    """
    항공 + 숙소를 asyncio.gather()로 병렬 예약 시도.
    하나라도 실패 시 성공한 항목을 롤백하고 BookingFailedError 발생.

    Args:
        validated_context: Sub1에서 반환된 검증 완료 컨텍스트
    Returns:
        List[dict]: 모든 예약 성공 시 결과 리스트 (flight + hotel)
    Raises:
        BookingFailedError: 하나 이상 실패 (롤백 완료)
    """
    print(f"[Sub2] 🚀 병렬 예약 시작 — {validated_context['dep_city']} → "
          f"{validated_context['dest_city']}, {validated_context['people']}명")

    # 1. 병렬 예약 시도 (각 항목에 개별 타임아웃 적용)
    flight_coro = _mock_book_flight(validated_context) if MOCK_FLIGHT else _real_book_flight(validated_context)
    hotel_coro  = _mock_book_hotel(validated_context)  if MOCK_HOTEL  else _real_book_hotel(validated_context)

    results: list = await asyncio.gather(
        _with_timeout(flight_coro, "flight"),
        _with_timeout(hotel_coro,  "hotel"),
        return_exceptions=True,
    )

    # 2. 예외 처리 (네트워크 오류 등)
    booking_results = []
    for r in results:
        if isinstance(r, Exception):
            booking_results.append({
                "item_type": "unknown",
                "partner_name": "unknown",
                "status": "failed",
                "amount": 0,
                "currency": "KRW",
                "details": {},
                "error_msg": f"예외 발생: {str(r)}",
            })
        else:
            booking_results.append(r)

    # 3. 성공/실패 분리
    succeeded = [r for r in booking_results if r["status"] == "confirmed"]
    failed    = [r for r in booking_results if r["status"] != "confirmed"]

    print(f"[Sub2] 결과 — 성공: {[r['item_type'] for r in succeeded]}, "
          f"실패: {[r['item_type'] for r in failed]}")

    # 4. 하나라도 실패 → 전체 롤백 (Saga 보상 트랜잭션)
    if failed:
        if succeeded:
            print(f"[Sub2] ⚠️ 일부 실패 감지 → 성공 항목 롤백 시작")
            rollback_tasks = [_cancel_item(item) for item in succeeded]
            await asyncio.gather(*rollback_tasks, return_exceptions=True)
            print(f"[Sub2] 롤백 완료")

        failed_types = [r["item_type"] for r in failed]
        raise BookingFailedError(
            failed_items=failed_types,
            message=f"예약 실패: {', '.join([r.get('error_msg','') for r in failed])}",
            retryable=True,
        )

    print(f"[Sub2] ✅ 전체 예약 성공")
    return booking_results


async def rollback_bookings(booking_results: List[dict]) -> None:
    """
    Saga 보상 트랜잭션: 이미 확정된 외부 예약을 일괄 취소.
    Sub3 또는 Sub4 실패 시 main.py에서 호출됨.
    """
    confirmed = [
        r for r in booking_results
        if r.get("status") == "confirmed" and r.get("partner_booking_id")
    ]
    if not confirmed:
        return

    print(f"[Sub2] ⚠️ Saga 보상 트랜잭션 발동 → "
          f"{[r['item_type'] for r in confirmed]} 취소 시작")
    rollback_tasks = [_cancel_item(item) for item in confirmed]
    await asyncio.gather(*rollback_tasks, return_exceptions=True)
    print(f"[Sub2] 롤백 완료 — {len(confirmed)}건 취소 처리")


# ── Duffel 실 API 연동 (동기 함수 — asyncio.to_thread로 호출) ──────
# SDK(duffel-api 0.6.x)가 구버전 API를 사용하므로 requests로 직접 호출

import requests as _requests

DUFFEL_API_BASE = "https://api.duffel.com"
DUFFEL_VERSION  = "v2"


def _duffel_headers() -> dict:
    """Duffel API 공통 헤더. DUFFEL_API_KEY 없으면 즉시 오류."""
    api_key = os.getenv("DUFFEL_API_KEY")
    if not api_key:
        raise EnvironmentError("DUFFEL_API_KEY 환경변수가 설정되지 않았습니다.")
    return {
        "Authorization":  f"Bearer {api_key}",
        "Duffel-Version": DUFFEL_VERSION,
        "Content-Type":   "application/json",
        "Accept":         "application/json",
    }


def _duffel_post(path: str, body: dict, _retry: int = 1) -> dict:
    """Duffel POST 요청 공통 처리. [M-6] retry 1회 + 명시적 10초 timeout."""
    last_exc = None
    for attempt in range(_retry + 1):
        try:
            r = _requests.post(
                f"{DUFFEL_API_BASE}{path}",
                headers=_duffel_headers(),
                json={"data": body},
                timeout=10,
            )
            r.raise_for_status()
            return r.json()["data"]
        except Exception as exc:
            last_exc = exc
            if attempt < _retry:
                import time; time.sleep(1)
    raise last_exc


def _duffel_get(path: str, params: dict = None, _retry: int = 1) -> dict:
    """Duffel GET 요청 공통 처리. [M-6] retry 1회 + 명시적 10초 timeout."""
    last_exc = None
    for attempt in range(_retry + 1):
        try:
            r = _requests.get(
                f"{DUFFEL_API_BASE}{path}",
                headers=_duffel_headers(),
                params=params,
                timeout=10,
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            last_exc = exc
            if attempt < _retry:
                import time; time.sleep(1)
    raise last_exc


# ── 도시명 → IATA 공항 코드 매핑 ──────────────────────────────────
# 폼에서 한국어 도시명(예: "도쿄")이 전달되면 Duffel이 422를 반환하므로 변환 필요.
_CITY_TO_IATA: dict[str, str] = {
    # 한국
    "서울": "ICN", "서울/인천": "ICN", "인천": "ICN", "김포": "GMP",
    "제주": "CJU", "부산": "PUS", "대구": "TAE", "청주": "CJJ",
    # 일본
    "도쿄": "NRT", "오사카": "KIX", "후쿠오카": "FUK", "삿포로": "CTS",
    "나고야": "NGO", "오키나와": "OKA",
    # 중국·대만·홍콩
    "베이징": "PEK", "상하이": "PVG", "홍콩": "HKG", "타이페이": "TPE",
    "광저우": "CAN", "청두": "CTU",
    # 동남아
    "방콕": "BKK", "싱가포르": "SIN", "쿠알라룸푸르": "KUL",
    "마닐라": "MNL", "자카르타": "CGK", "발리": "DPS", "하노이": "HAN",
    "호치민": "SGN", "다낭": "DAD",
    # 유럽
    "파리": "CDG", "런던": "LHR", "로마": "FCO", "바르셀로나": "BCN",
    "암스테르담": "AMS", "프랑크푸르트": "FRA", "이스탄불": "IST",
    "취리히": "ZRH", "빈": "VIE", "브뤼셀": "BRU",
    # 북미
    "뉴욕": "JFK", "로스앤젤레스": "LAX", "LA": "LAX",
    "샌프란시스코": "SFO", "시카고": "ORD", "밴쿠버": "YVR",
    "토론토": "YYZ", "시애틀": "SEA", "라스베이거스": "LAS",
    # 오세아니아·기타
    "시드니": "SYD", "멜버른": "MEL", "오클랜드": "AKL",
    "두바이": "DXB", "도하": "DOH",
}

def _to_iata(city: str) -> str:
    """도시명을 IATA 코드로 변환. 이미 3글자 코드면 대문자 그대로 반환."""
    city = city.strip()
    if len(city) == 3 and city.isalpha():
        return city.upper()
    return _CITY_TO_IATA.get(city, city)  # 매핑 없으면 원본 그대로 (Duffel이 검증)


def _duffel_book_flight_sync(context: dict) -> dict:
    """
    Duffel API v2로 항공권을 실제 예약하는 동기 함수.
    흐름:
      1. 항공편 검색  — 출발지·목적지·날짜·인원 전송
      2. 최저가 선택  — 검색 결과 중 total_amount 최소 항공편
      3. 예약 확정    — Duffel balance로 테스트 결제 후 order_id 발급
      4. 결과 반환    — 내부 포맷(partner_booking_id = order_id)으로 변환
    """
    dep    = _to_iata(context.get("dep_city",  "ICN"))
    dest   = _to_iata(context.get("dest_city", "NRT"))
    start  = str(context.get("start_date", ""))
    people = int(context.get("people", 1))

    # ── 1단계: 항공편 검색 ───────────────────────────────────────────
    offer_req = _duffel_post("/air/offer_requests", {
        "slices": [{"origin": dep, "destination": dest, "departure_date": start}],
        "passengers": [{"type": "adult"} for _ in range(people)],
        "cabin_class": "economy",
    })

    offers = offer_req.get("offers", [])
    if not offers:
        return {
            "item_type": "flight", "partner_name": "duffel",
            "partner_booking_id": None, "status": "failed",
            "amount": 0, "currency": "KRW", "details": {},
            "error_msg": f"{dep}→{dest} 구간 검색 결과 없음",
        }

    # ── 2단계: 최저가 항공편 선택 ────────────────────────────────────
    best = min(offers, key=lambda o: float(o["total_amount"]))

    # ── 3단계: 예약 확정 ─────────────────────────────────────────────
    # offer 내 passenger id와 탑승자 정보를 매핑해야 함
    order_passengers = [
        {
            "id":           pax["id"],
            "title":        "mr",
            "gender":       "m",
            "given_name":   "Test",
            "family_name":  "Passenger",
            "born_on":      "1990-01-01",
            "email":        "test@pickandgo.kr",
            "phone_number": "+821012345678",
        }
        for pax in best["passengers"]
    ]

    order = _duffel_post("/air/orders", {
        "selected_offers": [best["id"]],
        "passengers":      order_passengers,
        "payments": [{
            "type":     "balance",          # Duffel 잔액으로 테스트 결제
            "currency": best["total_currency"],
            "amount":   best["total_amount"],
        }],
        "type": "instant",
    })

    # ── 4단계: 내부 포맷으로 변환 후 반환 ────────────────────────────
    slices   = order.get("slices", [])
    segments = slices[0].get("segments", []) if slices else []
    seg      = segments[0] if segments else {}
    flight_no = (
        seg.get("marketing_carrier", {}).get("iata_code", "") +
        seg.get("marketing_carrier_flight_number", "")
    ) or "N/A"

    return {
        "item_type":          "flight",
        "partner_name":       "duffel",
        "partner_booking_id": order["id"],      # Duffel order ID — 취소 시 사용
        "status":             "confirmed",
        "amount":             int(float(order["total_amount"])),
        "currency":           order["total_currency"],
        "details": {
            "flight_no":       flight_no,
            "dep":             dep,
            "arr":             dest,
            "departure_date":  start,
            "seats":           people,
            "class":           "Economy",
            "duffel_offer_id": best["id"],
        },
        "error_msg": None,
    }


def _duffel_cancel_order(order_id: str) -> None:
    """
    Duffel API v2로 항공 예약을 취소하는 동기 함수 (Saga 롤백용).
    흐름:
      1. 취소 요청 생성 → cancellation_id 발급
      2. 취소 확정      → 이 시점에 실제 예약 취소 처리
    """
    # 1단계: 취소 요청 생성
    cancel = _duffel_post("/air/order_cancellations", {"order_id": order_id})
    cancel_id = cancel["id"]

    # 2단계: 취소 확정
    _requests.post(
        f"{DUFFEL_API_BASE}/air/order_cancellations/{cancel_id}/actions/confirm",
        headers=_duffel_headers(),
        timeout=30,
    ).raise_for_status()


async def _real_book_flight(context: dict) -> dict:
    """
    Duffel 실 API 항공 예약 (비동기 래퍼).
    Duffel SDK는 동기 방식이므로 asyncio.to_thread로 별도 스레드에서 실행.
    환경변수 MOCK_FLIGHT=false 설정 시 book_parallel()에서 호출됨.

    [BUG FIX] Duffel 실 API 실패(잔액 부족·키 제한·네트워크 오류 등) 시
    Mock 항공 예약으로 자동 폴백하여 전체 예약 파이프라인이 중단되지 않도록 함.
    로그에 ⚠️ 경고를 출력해 폴백 발생을 추적할 수 있게 함.
    """
    try:
        return await asyncio.to_thread(_duffel_book_flight_sync, context)
    except Exception as e:
        print(f"[Sub2] ⚠️ Duffel 실 API 실패 → Mock 항공 예약으로 자동 폴백: {e}")
        return await _mock_book_flight(context)


# ── LiteAPI 숙소 연동 (동기 함수 — asyncio.to_thread로 호출) ──────
# Duffel Stays 별도 계약 필요 → LiteAPI Sandbox로 대체
# auth: X-API-Key 헤더 (Bearer 아님)

LITEAPI_BASE    = "https://api.liteapi.travel/v3.0"
LITEAPI_TIMEOUT = 10  # [M-6] 30→10초 timeout (과도한 대기 방지)


def _liteapi_headers() -> dict:
    """LiteAPI 공통 헤더. LITEAPI_KEY 없으면 즉시 오류."""
    api_key = os.getenv("LITEAPI_KEY")
    if not api_key:
        raise EnvironmentError("LITEAPI_KEY 환경변수가 설정되지 않았습니다.")
    return {
        "X-API-Key":    api_key,
        "Content-Type": "application/json",
        "Accept":       "application/json",
    }


def _liteapi_post(path: str, body: dict, _retry: int = 1) -> dict:
    """LiteAPI POST 요청 공통 처리. [M-6] retry 1회 + 10초 timeout."""
    last_exc = None
    for attempt in range(_retry + 1):
        try:
            r = _requests.post(
                f"{LITEAPI_BASE}{path}",
                headers=_liteapi_headers(),
                json=body,
                timeout=LITEAPI_TIMEOUT,
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            last_exc = exc
            if attempt < _retry:
                import time; time.sleep(1)
    raise last_exc


def _liteapi_book_hotel_sync(context: dict) -> dict:
    """
    LiteAPI Sandbox로 숙소를 실제 예약하는 동기 함수.
    흐름:
      1. 호텔 요금 검색  — 목적지 IATA 공항코드 기반, 최저가 선택
      2. Prebook        — offerId → prebookId 발급 (가격·가용성 재확인)
      3. 예약 확정       — prebookId + 투숙객 정보 → bookingId 발급
      4. 결과 반환       — 내부 포맷으로 변환
    결제: ACC_CREDIT_CARD (Sandbox — 실제 청구 없음)
    """
    dest     = context.get("dest_city", "NRT")
    start    = str(context.get("start_date", ""))
    end      = str(context.get("end_date", ""))
    people   = int(context.get("people", 1))
    duration = int(context.get("duration", 1))

    # ── 1단계: 호텔 요금 검색 ────────────────────────────────────
    search_resp = _liteapi_post("/hotels/rates?rm=true", {
        "iataCode":         dest,
        "checkin":          start,
        "checkout":         end,
        "occupancies":      [{"adults": people}],
        "guestNationality": "KR",
        "currency":         "USD",
        "maxRatesPerHotel": 1,
    })

    hotels = search_resp.get("data", [])
    if not hotels:
        return {
            "item_type": "hotel", "partner_name": "liteapi",
            "partner_booking_id": None, "status": "failed",
            "amount": 0, "currency": "USD", "details": {},
            "error_msg": f"{dest} 지역 숙소 검색 결과 없음",
        }

    # 첫 번째 호텔의 첫 번째 객실 선택
    best_hotel = hotels[0]
    room_types = best_hotel.get("roomTypes", [])
    if not room_types:
        return {
            "item_type": "hotel", "partner_name": "liteapi",
            "partner_booking_id": None, "status": "failed",
            "amount": 0, "currency": "USD", "details": {},
            "error_msg": "이용 가능한 객실 없음",
        }

    rt        = room_types[0]
    offer_id  = rt["offerId"]
    rates     = rt.get("rates", [])
    amount    = (
        rates[0].get("retailRate", {}).get("total", [{}])[0].get("amount", 0)
        if rates else 0
    )

    # ── 2단계: Prebook ───────────────────────────────────────────
    pb_resp    = _liteapi_post("/rates/prebook", {
        "offerId":       offer_id,
        "usePaymentSdk": False,
    })
    prebook_id = pb_resp["data"]["prebookId"]

    # ── 3단계: 예약 확정 ──────────────────────────────────────────
    book_resp = _liteapi_post("/rates/book", {
        "prebookId": prebook_id,
        "holder": {
            "firstName": "Test",
            "lastName":  "Passenger",
            "email":     "test@pickandgo.kr",
        },
        "payment": {"method": "ACC_CREDIT_CARD"},   # Sandbox 테스트 결제
        "guestInfo": [
            {"guestFirstName": "Test",
             "guestLastName":  "Passenger",
             "guestEmail":     "test@pickandgo.kr"}
            for _ in range(max(1, people))
        ],
    })

    bk         = book_resp["data"]
    booking_id = bk["bookingId"]
    hotel_name = bk.get("hotel", {}).get("name", best_hotel.get("hotelId", "N/A"))

    # ── 4단계: 내부 포맷 변환 ─────────────────────────────────────
    return {
        "item_type":          "hotel",
        "partner_name":       "liteapi",
        "partner_booking_id": booking_id,
        "status":             "confirmed",
        "amount":             int(float(amount)) if amount else 0,
        "currency":           "USD",
        "details": {
            "hotel_name": hotel_name,
            "hotel_id":   best_hotel.get("hotelId"),
            "check_in":   start,
            "check_out":  end,
            "nights":     duration,
            "rooms":      1,
        },
        "error_msg": None,
    }


def _liteapi_cancel_hotel(booking_id: str) -> None:
    """
    LiteAPI 숙소 예약 취소 (Saga 롤백용).
    DELETE /bookings/{bookingId} → HTTP 200
    """
    _requests.delete(
        f"{LITEAPI_BASE}/bookings/{booking_id}",
        headers=_liteapi_headers(),
        timeout=LITEAPI_TIMEOUT,
    ).raise_for_status()


async def _real_book_hotel(context: dict) -> dict:
    """
    LiteAPI 실 API 숙소 예약 (비동기 래퍼).
    동기 함수를 asyncio.to_thread로 별도 스레드에서 실행.
    환경변수 MOCK_HOTEL=false 설정 시 book_parallel()에서 호출됨.
    """
    try:
        return await asyncio.to_thread(_liteapi_book_hotel_sync, context)
    except Exception as e:
        return {
            "item_type": "hotel",
            "partner_name": "liteapi",
            "partner_booking_id": None,
            "status": "failed",
            "amount": 0,
            "currency": "USD",
            "details": {},
            "error_msg": f"LiteAPI 오류: {e}",
        }
