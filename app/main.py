# app/main.py (병합: yeongmin + main)
# ─────────────────────────────────────────────────────────────
# [yeongmin] DB 마이그레이션 자동 실행, generate-relaxed, generate-fetch 엔드포인트
# [main]     예약 5단계 파이프라인 (Sub1~5), 예약 성공률 통계 API
# ─────────────────────────────────────────────────────────────
from fastapi import FastAPI, HTTPException, BackgroundTasks, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import date
import asyncio
import time
import sys
import os

# ----------------------------------------------------------------
# [중요] 경로 설정
# ----------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir    = os.path.dirname(current_dir)
sys.path.append(root_dir)

import travel_logic as logic
import backend_postgres as backend
from travel_logic import InsufficientPlacesError
from fastapi.responses import JSONResponse

from .models import (
    TravelCondition,
    ItineraryResponse,
    DBUpdateRequest,
    InsufficientPlacesDetail,
    ReservationRequest,
)

# 예약 Sub 모듈 (main 브랜치)
from .reservation.sub1_validator import validate_reservation, ReservationValidationError
from .reservation.sub2_external  import book_parallel, rollback_bookings, BookingFailedError
from .reservation.sub3_confirmer import confirm_reservation, ConfirmationError
from .reservation.sub4_storage   import save_reservation, StorageError
from .reservation.sub5_notifier  import (
    build_success_response,
    build_fail_response,
    send_confirmation_notification,
)
from .reservation.sub_metrics import log_pipeline_failure, get_stats_summary

# --- FastAPI 앱 초기화 ---
app = FastAPI(
    title="PicknGo Core API",
    version="2.0.0",
    description="모바일/웹 확장을 위한 고성능 여행 일정 추천 + 예약 서버",
)

# --- CORS 설정 ---
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


# ================================================================
# 🚀 서버 시작 이벤트 [yeongmin: DB 마이그레이션 자동 실행]
# ================================================================
@app.on_event("startup")
def startup_event():
    """
    서버 시작 시점 초기화.
    1. DB 마이그레이션 자동 실행 (신규 컬럼 추가 — 기존 데이터 유지)
    2. PostgreSQL 연결 확인 메시지 출력
    """
    try:
        from sqlalchemy import create_engine, text
        from config import Config

        _mig_engine = create_engine(Config.DATABASE_URL, echo=False)

        _migration_sqls = [
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS sub_category  VARCHAR(100);",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS review_count  INTEGER DEFAULT 0;",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS verified_at   TIMESTAMP WITHOUT TIME ZONE;",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_5star  INTEGER DEFAULT 0;",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_4star  INTEGER DEFAULT 0;",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_3star  INTEGER DEFAULT 0;",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_2star  INTEGER DEFAULT 0;",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_1star  INTEGER DEFAULT 0;",
            "CREATE INDEX IF NOT EXISTS idx_places_sub_category ON places (sub_category);",
            "CREATE INDEX IF NOT EXISTS idx_places_verified_at  ON places (verified_at);",
            "UPDATE places SET review_count = 0 WHERE review_count IS NULL;",
            "UPDATE places SET verified_at = updated_at WHERE verified_at IS NULL AND updated_at IS NOT NULL;",
        ]

        with _mig_engine.connect() as conn:
            for sql in _migration_sqls:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                except Exception:
                    pass  # 이미 존재하면 건너뜀

        print("[OK] DB 마이그레이션 체크 완료 (신규 컬럼 자동 추가)")

    except Exception as e:
        print(f"[WARN] DB 마이그레이션 건너뜀: {e}")

    print("[OK] FastAPI Server Started - Using PostgreSQL + PostGIS Backend")


# ================================================================
# 📡 API 엔드포인트 정의
# ================================================================

@app.get("/")
def health_check():
    return {"status": "ok", "message": "PicknGo API Server is Running!"}


# ──────────────────────────────────────────────────────────────
# 1. 일정 생성 API (핵심) [main: X-Generation-Time 헤더 추가]
# ──────────────────────────────────────────────────────────────
@app.post("/api/v1/generate", response_model=ItineraryResponse, summary="여행 일정 생성")
async def generate_itinerary(req: TravelCondition, response: Response):
    t_start = time.perf_counter()
    try:
        d_start  = date.fromisoformat(req.start_date)
        d_end    = date.fromisoformat(req.end_date)
        duration = (d_end - d_start).days + 1

        if duration <= 0:
            raise HTTPException(status_code=400, detail="종료일이 시작일보다 빠릅니다.")

        input_data = req.model_dump()
        print(f"🔄 [Processing] {req.dest_city} {duration}일 일정 생성 시작...")

        plans = await run_in_thread(logic.generate_plans, input_data, duration)

        elapsed = time.perf_counter() - t_start
        response.headers["X-Generation-Time"] = f"{elapsed:.3f}s"

        if elapsed > 5.0:
            print(f"⚠️  [SLOW] 일정 생성 {elapsed:.3f}s — 목표 ≤5초 초과")
        else:
            print(f"✅ [Success] {len(plans) if plans else 0}개 테마 일정 생성 완료 ({elapsed:.3f}s)")

        if not plans:
            return ItineraryResponse(plans=[])
        return ItineraryResponse(plans=plans)

    except InsufficientPlacesError as e:
        msg = (
            f"'{e.city}'에서 조건에 맞는 관광지가 {e.available}개뿐입니다 "
            f"(일정 생성 최소 {e.required}개 필요)."
        )
        print(f"⚠️ [InsufficientPlaces] {msg}")
        return JSONResponse(
            status_code=422,
            content=InsufficientPlacesDetail(
                city=e.city,
                available=e.available,
                required=e.required,
                budget_level=e.budget_level,
                relaxed=e.relaxed,
                message=msg,
            ).model_dump(),
        )

    except Exception as e:
        elapsed = time.perf_counter() - t_start
        print(f"❌ [Error] 일정 생성 실패 ({elapsed:.3f}s): {e}")
        detail_str = str(e)
        if len(detail_str) > 500:
            detail_str = detail_str[:500] + "..."
        raise HTTPException(status_code=500, detail=detail_str)


# ──────────────────────────────────────────────────────────────
# 2. DB 업데이트 API (백그라운드 처리)
# ──────────────────────────────────────────────────────────────
@app.post("/api/v1/update-db", summary="데이터 수집 요청 (백그라운드)")
async def trigger_db_update(req: DBUpdateRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(logic.update_db, req.dest_city, req.styles)
    print(f"⏳ [Background] {req.dest_city} 데이터 업데이트 작업 예약됨.")
    return {
        "status": "accepted",
        "message": f"'{req.dest_city}' 데이터 수집 작업이 백그라운드에서 시작되었습니다.",
    }


# ──────────────────────────────────────────────────────────────
# 3. 조건 완화 재생성 API [yeongmin]
# ──────────────────────────────────────────────────────────────
@app.post("/api/v1/generate-relaxed", response_model=ItineraryResponse, summary="조건 완화 후 일정 재생성")
async def generate_relaxed(req: TravelCondition):
    """
    Phase 1 하드 필터의 예산 평점 기준을 한 단계 낮춰 일정을 재생성합니다.
    예) 예산 '고' → 4.0점 기준 → 3.0점으로 완화
    """
    try:
        d_start  = date.fromisoformat(req.start_date)
        d_end    = date.fromisoformat(req.end_date)
        duration = (d_end - d_start).days + 1

        if duration <= 0:
            raise HTTPException(status_code=400, detail="종료일이 시작일보다 빠릅니다.")

        input_data = req.model_dump()
        input_data['_relax_filter'] = True

        print(f"🔄 [Relaxed] {req.dest_city} {duration}일 조건 완화 재생성 시작...")
        plans = await run_in_thread(logic.generate_plans, input_data, duration)

        if not plans:
            return ItineraryResponse(plans=[])

        print(f"✅ [Relaxed] {len(plans)}개 테마 일정 생성 완료.")
        return ItineraryResponse(plans=plans)

    except InsufficientPlacesError as e:
        msg = (
            f"'{e.city}'의 장소가 조건 완화 후에도 부족합니다 "
            f"({e.available}개 유효 / 필요 {e.required}개)."
        )
        return JSONResponse(
            status_code=422,
            content=InsufficientPlacesDetail(
                city=e.city, available=e.available, required=e.required,
                budget_level=e.budget_level, relaxed=True, message=msg,
            ).model_dump(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:500])


# ──────────────────────────────────────────────────────────────
# 4. 실시간 데이터 검색 후 재생성 API [yeongmin]
# ──────────────────────────────────────────────────────────────
@app.post("/api/v1/generate-fetch", response_model=ItineraryResponse, summary="실시간 검색 후 일정 재생성")
async def generate_after_fetch(req: TravelCondition):
    """
    Google/Kakao API를 실시간으로 호출하여 부족한 장소를 수집한 뒤 일정을 재생성합니다.
    """
    try:
        d_start  = date.fromisoformat(req.start_date)
        d_end    = date.fromisoformat(req.end_date)
        duration = (d_end - d_start).days + 1

        if duration <= 0:
            raise HTTPException(status_code=400, detail="종료일이 시작일보다 빠릅니다.")

        input_data = req.model_dump()
        city   = req.dest_city
        styles = req.style

        print(f"🔍 [Fetch] {city} 실시간 데이터 수집 시작...")
        fetch_result = await run_in_thread(logic.update_db, city, styles)
        added = fetch_result.get('added_count', 0) if isinstance(fetch_result, dict) else 0
        print(f"✅ [Fetch] {added}개 데이터 새로 확보. 일정 재생성 시작...")

        plans = await run_in_thread(logic.generate_plans, input_data, duration)

        if not plans:
            return ItineraryResponse(plans=[])

        print(f"✅ [Fetch] {len(plans)}개 테마 일정 생성 완료.")
        return ItineraryResponse(plans=plans)

    except InsufficientPlacesError as e:
        msg = (
            f"실시간 검색 후에도 '{e.city}'의 장소가 부족합니다 "
            f"({e.available}개 유효 / 필요 {e.required}개)."
        )
        return JSONResponse(
            status_code=422,
            content=InsufficientPlacesDetail(
                city=e.city, available=e.available, required=e.required,
                budget_level=e.budget_level, relaxed=e.relaxed, message=msg,
            ).model_dump(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:500])


# ──────────────────────────────────────────────────────────────
# 5. 예약 확정 API — Sub1~5 5단계 파이프라인 [main]
# ──────────────────────────────────────────────────────────────
@app.post(
    "/api/v1/reservation",
    summary="예약 요청 및 확정 (Sub1~5 파이프라인)",
    description="예약 검증 → 외부 병렬 예약 → 확정 검증 → DB 저장 → 결과 안내 순으로 처리",
)
async def create_reservation(
    req: ReservationRequest,
    background_tasks: BackgroundTasks,
    response: Response,
    demo_fail: bool = Query(False, description="시연용 강제 실패 모드 (demo_fail=true)"),
):
    """
    Sub1: 예약 검증부
    Sub2: 외부 예약 연동 (항공 + 숙소 병렬)
    Sub3: 예약 확정 검증
    Sub4: DB 저장 (트랜잭션)
    Sub5: 결과 안내 (성공/실패 응답)
    """
    if demo_fail:
        print("[Reservation] 🎭 시연 모드 — 강제 실패 응답 반환")
        return build_fail_response(
            error_code="BOOKING_FAILED",
            error_message="항공 또는 숙소 예약 중 오류가 발생했습니다. 다른 일정을 선택해 주세요.",
            retryable=True,
            failed_items=[],
        )

    t_start = time.perf_counter()
    print(f"\n{'='*50}")
    print(f"[Reservation] 🎫 예약 요청 수신 — user:{req.user_id}, {req.dep_city}→{req.dest_city}")
    print(f"{'='*50}")

    # Sub 1: 예약 검증부
    try:
        validated_context = await validate_reservation(req)
    except ReservationValidationError as e:
        return build_fail_response(
            error_code=e.code,
            error_message=e.message,
            retryable=e.retryable,
        )

    # Sub 2: 외부 예약 연동 관리부 (병렬)
    try:
        booking_results = await book_parallel(validated_context)
    except BookingFailedError as e:
        await log_pipeline_failure(
            error_code="BOOKING_FAILED", failed_sub="sub2",
            user_id=req.user_id, dest_city=req.dest_city,
        )
        return build_fail_response(
            error_code="BOOKING_FAILED",
            error_message=e.message,
            retryable=e.retryable,
            failed_items=e.failed_items,
        )
    except Exception as e:
        await log_pipeline_failure(
            error_code="EXTERNAL_API_ERROR", failed_sub="sub2",
            user_id=req.user_id, dest_city=req.dest_city,
        )
        return build_fail_response(
            error_code="EXTERNAL_API_ERROR",
            error_message=f"외부 예약 서비스 오류: {str(e)}",
            retryable=True,
        )

    # Sub 3: 예약 확정 검증
    try:
        confirmed_reservation = await confirm_reservation(validated_context, booking_results)
    except ConfirmationError as e:
        await rollback_bookings(booking_results)
        await log_pipeline_failure(
            error_code=e.code, failed_sub="sub3",
            user_id=req.user_id, dest_city=req.dest_city,
        )
        return build_fail_response(
            error_code=e.code,
            error_message=e.message,
            retryable=False,
        )

    # Sub 4: 예약 정보 저장 (DB 트랜잭션)
    try:
        saved_id = await save_reservation(confirmed_reservation)
    except StorageError as e:
        await rollback_bookings(confirmed_reservation.get("items", []))
        return build_fail_response(
            error_code=e.code,
            error_message=e.message,
            retryable=True,
        )

    # Sub 5: 결과 안내 (BackgroundTasks로 이메일/SMS 분리)
    background_tasks.add_task(
        send_confirmation_notification,
        saved_id,
        req.user_id,
        req.dest_city,
        req.user_email,
        confirmed_reservation.get("items", []),
        float(confirmed_reservation.get("total_amount", 0)),
    )

    result  = build_success_response(confirmed_reservation, saved_id)
    elapsed = time.perf_counter() - t_start
    response.headers["X-Reservation-Time"] = f"{elapsed:.3f}s"

    if elapsed > 15.0:
        print(f"⚠️  [SLOW] 예약 확정 {elapsed:.3f}s — 목표 ≤15초 초과")
    else:
        print(f"[Reservation] ✅ 완료 — reservation_id:{saved_id} ({elapsed:.3f}s)")
    return result


# ──────────────────────────────────────────────────────────────
# 6. 예약 성공률 통계 API [main]
# ──────────────────────────────────────────────────────────────
@app.get(
    "/api/v1/metrics",
    summary="예약 성공률 통계 (SRS M-13)",
    description="최근 N일 예약 시도/성공/실패 카운트와 성공률 반환. 기본 7일.",
)
async def get_reservation_metrics(days: int = 7):
    """SRS M-13: 예약 성공률 ≥ 99.9% 측정 결과 반환."""
    days = min(max(days, 1), 90)
    stats = await get_stats_summary(period_days=days)
    return stats


# ──────────────────────────────────────────────────────────────
# 7. 국내 도시 목록 API (Demo Fix 1)
# ──────────────────────────────────────────────────────────────
@app.get(
    "/api/v1/cities",
    summary="DB 기반 국내 도시 목록",
    description="places 테이블에 데이터가 있는 국내 도시 목록을 반환합니다.",
)
def list_cities():
    return {"cities": backend.get_domestic_cities()}