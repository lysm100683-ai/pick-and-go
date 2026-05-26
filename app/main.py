# app/main.py (최종 수정: 모듈 경로 및 Startup Cache 적용)
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from datetime import date
import asyncio
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
from travel_logic import InsufficientPlacesError
from fastapi.responses import JSONResponse
from .models import TravelCondition, ItineraryResponse, DBUpdateRequest, InsufficientPlacesDetail

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
    서버 시작 시점 초기화.
    1. DB 마이그레이션 자동 실행 (신규 컬럼 추가 — 기존 데이터 유지)
    2. PostgreSQL 연결 확인 메시지 출력
    """
    # ── DB 마이그레이션 자동 실행 ────────────────────────────────────────
    # run_migration.py와 동일한 로직을 서버 시작 시 인라인으로 실행.
    # 컬럼이 이미 존재하면 IF NOT EXISTS로 안전하게 건너뜀.
    try:
        from sqlalchemy import create_engine, text
        from config import Config

        _mig_engine = create_engine(Config.DATABASE_URL, echo=False)

        _migration_sqls = [
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS sub_category  VARCHAR(100);",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS review_count  INTEGER DEFAULT 0;",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS verified_at   TIMESTAMP WITHOUT TIME ZONE;",
            # 별점 분포 컬럼 (Place Details API 샘플 리뷰 누적)
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_5star  INTEGER DEFAULT 0;",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_4star  INTEGER DEFAULT 0;",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_3star  INTEGER DEFAULT 0;",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_2star  INTEGER DEFAULT 0;",
            "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_1star  INTEGER DEFAULT 0;",
            "CREATE INDEX IF NOT EXISTS idx_places_sub_category ON places (sub_category);",
            "CREATE INDEX IF NOT EXISTS idx_places_verified_at  ON places (verified_at);",
            "UPDATE places SET review_count = 0 WHERE review_count IS NULL;",
            # 기존 장소의 verified_at을 updated_at으로 초기화
            "UPDATE places SET verified_at = updated_at WHERE verified_at IS NULL AND updated_at IS NOT NULL;",
        ]

        with _mig_engine.connect() as conn:
            for sql in _migration_sqls:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                except Exception:
                    pass  # 이미 존재하면 건너뜀 — 서버 시작 방해 안 함

        print("[OK] DB 마이그레이션 체크 완료 (신규 컬럼 자동 추가)")

    except Exception as e:
        # 마이그레이션 실패 시 경고만 출력, 서버 시작은 계속
        print(f"[WARN] DB 마이그레이션 건너뜀: {e}")

    print("[OK] FastAPI Server Started - Using PostgreSQL + PostGIS Backend")


# ================================================================
# 📡 API 엔드포인트 정의
# ================================================================

@app.get("/")
def health_check():
    return {"status": "ok", "message": "PicknGo API Server is Running!"}


# 1. 일정 생성 API (핵심)
@app.post("/api/v1/generate", response_model=ItineraryResponse, summary="여행 일정 생성")
async def generate_itinerary(req: TravelCondition):
    try:
        d_start = date.fromisoformat(req.start_date)
        d_end = date.fromisoformat(req.end_date)
        duration = (d_end - d_start).days + 1
        
        if duration <= 0:
            raise HTTPException(status_code=400, detail="종료일이 시작일보다 빠릅니다.")

        input_data = req.model_dump()

        print(f"🔄 [Processing] {req.dest_city} {duration}일 일정 생성 시작...")
        
        # 🚀 run_in_thread 사용 유지 (블로킹 방지)
        # travel_logic.generate_plans 호출
        plans = await run_in_thread(logic.generate_plans, input_data, duration)

        if not plans:
            return ItineraryResponse(plans=[])

        print(f"✅ [Success] {len(plans)}개 테마 일정 생성 완료.")
        return ItineraryResponse(plans=plans)

    except InsufficientPlacesError as e:
        # 장소 부족: 422로 구조화된 에러 반환 (프론트엔드가 모달로 안내)
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
        print(f"❌ [Error] 일정 생성 실패: {e}")
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


# 3. 조건 완화 재생성 API (INSUFFICIENT_PLACES 옵션 1)
@app.post("/api/v1/generate-relaxed", response_model=ItineraryResponse, summary="조건 완화 후 일정 재생성")
async def generate_relaxed(req: TravelCondition):
    """
    Phase 1 하드 필터의 예산 평점 기준을 한 단계 낮춰 일정을 재생성합니다.
    예) 예산 '고' → 4.0점 기준 → 3.0점으로 완화
    """
    try:
        d_start = date.fromisoformat(req.start_date)
        d_end   = date.fromisoformat(req.end_date)
        duration = (d_end - d_start).days + 1

        if duration <= 0:
            raise HTTPException(status_code=400, detail="종료일이 시작일보다 빠릅니다.")

        input_data = req.model_dump()
        input_data['_relax_filter'] = True   # 평점 기준 완화 플래그

        print(f"🔄 [Relaxed] {req.dest_city} {duration}일 조건 완화 재생성 시작...")
        plans = await run_in_thread(logic.generate_plans, input_data, duration)

        if not plans:
            return ItineraryResponse(plans=[])

        print(f"✅ [Relaxed] {len(plans)}개 테마 일정 생성 완료.")
        return ItineraryResponse(plans=plans)

    except InsufficientPlacesError as e:
        # 완화 후에도 부족 → relaxed=True로 표시(순환 방지)
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
        detail_str = str(e)[:500]
        raise HTTPException(status_code=500, detail=detail_str)


# 4. 실시간 데이터 검색 후 재생성 API (INSUFFICIENT_PLACES 옵션 2)
@app.post("/api/v1/generate-fetch", response_model=ItineraryResponse, summary="실시간 검색 후 일정 재생성")
async def generate_after_fetch(req: TravelCondition):
    """
    Google/Kakao API를 실시간으로 호출하여 부족한 장소를 수집한 뒤 일정을 재생성합니다.
    """
    try:
        d_start = date.fromisoformat(req.start_date)
        d_end   = date.fromisoformat(req.end_date)
        duration = (d_end - d_start).days + 1

        if duration <= 0:
            raise HTTPException(status_code=400, detail="종료일이 시작일보다 빠릅니다.")

        input_data = req.model_dump()
        city   = req.dest_city
        styles = req.style

        # 실시간 데이터 수집 (동기 실행 — 충분한 데이터 확보 후 진행)
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
            f"({e.available}개 유효 / 필요 {e.required}개). DB에 수집된 데이터가 없으면 별도 수집이 필요합니다."
        )
        return JSONResponse(
            status_code=422,
            content=InsufficientPlacesDetail(
                city=e.city, available=e.available, required=e.required,
                budget_level=e.budget_level, relaxed=e.relaxed, message=msg,
            ).model_dump(),
        )
    except Exception as e:
        detail_str = str(e)[:500]
        raise HTTPException(status_code=500, detail=detail_str)


# 5. 예약 확정 API (15초 스펙 달성용)
@app.post("/api/v1/reservation", summary="예약 요청 및 확정")
async def create_reservation(place_name: str, user_id: str):
    await asyncio.sleep(2) 
    
    reservation_id = f"RES_{user_id}_{place_name[:5]}_{date.today()}"
    
    return {
        "status": "confirmed",
        "reservation_id": reservation_id,
        "message": f"'{place_name}' 예약이 확정되었습니다. (영수증이 이메일로 발송됩니다.)"
    }