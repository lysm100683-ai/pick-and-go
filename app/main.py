# app/main.py (최종 수정: 모듈 경로 및 Startup Cache 적용)
from fastapi import FastAPI, HTTPException, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from datetime import date
import asyncio
import time
import sys
import os

# ----------------------------------------------------------------
# [중요] 경로 설정 (모듈 로드 오류 해결을 위한 필수 로직)
# ----------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__)) 
root_dir = os.path.dirname(current_dir)                
sys.path.append(root_dir)

# 이제 루트 경로에 있는 모듈과 상대 모듈을 임포트합니다.
# travel_logic.py는 루트 디렉토리에 있다고 가정합니다.
import travel_logic as logic
import backend_postgres as backend  # PostgreSQL + PostGIS 백엔드
from .models import (
    TravelCondition, ItineraryResponse, DBUpdateRequest,
    ReservationRequest, ReservationResponse, ReservationFailResponse,
)
from .reservation.sub1_validator import validate_reservation, ReservationValidationError
from .reservation.sub2_external  import book_parallel, BookingFailedError
from .reservation.sub3_confirmer import confirm_reservation, ConfirmationError
from .reservation.sub4_storage   import save_reservation, StorageError
from .reservation.sub5_notifier  import build_success_response, build_fail_response, send_confirmation_notification

# --- FastAPI 앱 초기화 ---
app = FastAPI(
    title="PicknGo Core API",
    version="2.0.0",
    description="모바일/웹 확장을 위한 고성능 여행 일정 추천 서버"
)

# --- CORS 설정 (유지) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 유틸리티: 비동기 래퍼 ---
async def run_in_thread(func, *args):
    return await asyncio.to_thread(func, *args)


# 🚀 NEW: 서버 시작 이벤트
@app.on_event("startup")
def startup_event():
    """
    서버 시작 시점 초기화
    backend_postgres는 PostgreSQL 직접 연결을 사용하므로 캐시 로드 불필요
    """
    print("[OK] FastAPI Server Started - Using PostgreSQL + PostGIS Backend") 


# ================================================================
# 📡 API 엔드포인트 정의
# ================================================================

@app.get("/")
def health_check():
    return {"status": "ok", "message": "PicknGo API Server is Running!"}


# 1. 일정 생성 API (핵심)
@app.post("/api/v1/generate", response_model=ItineraryResponse, summary="여행 일정 생성")
async def generate_itinerary(req: TravelCondition, response: Response):
    t_start = time.perf_counter()
    try:
        d_start = date.fromisoformat(req.start_date)
        d_end   = date.fromisoformat(req.end_date)
        duration = (d_end - d_start).days + 1

        if duration <= 0:
            raise HTTPException(status_code=400, detail="종료일이 시작일보다 빠릅니다.")

        input_data = req.model_dump()
        print(f"🔄 [Processing] {req.dest_city} {duration}일 일정 생성 시작...")

        plans = await run_in_thread(logic.generate_plans, input_data, duration)

        elapsed = time.perf_counter() - t_start
        # 응답 헤더에 소요 시간 포함 (목표 사양 ≤ 5초 검증용)
        response.headers["X-Generation-Time"] = f"{elapsed:.3f}s"

        if elapsed > 5.0:
            print(f"⚠️  [SLOW] 일정 생성 {elapsed:.3f}s — 목표 ≤5초 초과")
        else:
            print(f"✅ [Success] {len(plans) if plans else 0}개 테마 일정 생성 완료 ({elapsed:.3f}s)")

        if not plans:
            return ItineraryResponse(plans=[])
        return ItineraryResponse(plans=plans)

    except Exception as e:
        elapsed = time.perf_counter() - t_start
        print(f"❌ [Error] 일정 생성 실패 ({elapsed:.3f}s): {e}")
        detail_str = str(e)
        if len(detail_str) > 500:
            detail_str = detail_str[:500] + "..."
        raise HTTPException(status_code=500, detail=detail_str)


# 2. DB 업데이트 API (백그라운드 처리)
@app.post("/api/v1/update-db", summary="데이터 수집 요청 (백그라운드)")
async def trigger_db_update(req: DBUpdateRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(logic.update_db, req.dest_city, req.styles)
    
    print(f"⏳ [Background] {req.dest_city} 데이터 업데이트 작업 예약됨.")
    return {
        "status": "accepted",
        "message": f"'{req.dest_city}' 데이터 수집 작업이 백그라운드에서 시작되었습니다."
    }


# 3. 예약 확정 API — Sub1~5 5단계 파이프라인
@app.post(
    "/api/v1/reservation",
    summary="예약 요청 및 확정 (Sub1~5 파이프라인)",
    description="예약 검증 → 외부 병렬 예약 → 확정 검증 → DB 저장 → 결과 안내 순으로 처리",
)
async def create_reservation(
    req: ReservationRequest,
    background_tasks: BackgroundTasks,
    response: Response,
):
    """
    설계도 5단계 파이프라인:
      Sub1: 예약 검증부
      Sub2: 외부 예약 연동 (항공 + 숙소 병렬)
      Sub3: 예약 확정 검증
      Sub4: DB 저장 (트랜잭션)
      Sub5: 결과 안내 (성공/실패 응답)
    """
    t_start = time.perf_counter()
    print(f"\n{'='*50}")
    print(f"[Reservation] 🎫 예약 요청 수신 — user:{req.user_id}, {req.dep_city}→{req.dest_city}")
    print(f"{'='*50}")

    # ── Sub 1: 예약 검증부 ─────────────────────────────────────
    try:
        validated_context = await validate_reservation(req)
    except ReservationValidationError as e:
        return build_fail_response(
            error_code=e.code,
            error_message=e.message,
            retryable=e.retryable,
        )

    # ── Sub 2: 외부 예약 연동 관리부 (병렬) ───────────────────
    try:
        booking_results = await book_parallel(validated_context)
    except BookingFailedError as e:
        return build_fail_response(
            error_code="BOOKING_FAILED",
            error_message=e.message,
            retryable=e.retryable,
            failed_items=e.failed_items,
        )
    except Exception as e:
        return build_fail_response(
            error_code="EXTERNAL_API_ERROR",
            error_message=f"외부 예약 서비스 오류: {str(e)}",
            retryable=True,
        )

    # ── Sub 3: 예약 확정 검증 ─────────────────────────────────
    try:
        confirmed_reservation = await confirm_reservation(validated_context, booking_results)
    except ConfirmationError as e:
        return build_fail_response(
            error_code=e.code,
            error_message=e.message,
            retryable=False,
        )

    # ── Sub 4: 예약 정보 저장 (DB 트랜잭션) ───────────────────
    try:
        saved_id = await save_reservation(confirmed_reservation)
    except StorageError as e:
        return build_fail_response(
            error_code=e.code,
            error_message=e.message,
            retryable=True,
        )

    # ── Sub 5: 결과 안내 ──────────────────────────────────────
    # 이메일/SMS 발송은 Back그라운드로 분리 → 응답 시간 단축 (SRS M-12 준수)
    background_tasks.add_task(
        send_confirmation_notification,
        saved_id,
        req.user_id,
        req.dest_city,
    )

    result = build_success_response(confirmed_reservation, saved_id)
    elapsed = time.perf_counter() - t_start
    response.headers["X-Reservation-Time"] = f"{elapsed:.3f}s"

    if elapsed > 15.0:
        print(f"⚠️  [SLOW] 예약 확정 {elapsed:.3f}s — 목표 ≤15초 초과")
    else:
        print(f"[Reservation] ✅ 완료 — reservation_id:{saved_id} ({elapsed:.3f}s)")
    return result