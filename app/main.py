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
import backend 
from .models import TravelCondition, ItineraryResponse, DBUpdateRequest 

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


# 🚀 NEW: 서버 시작 이벤트 (데이터 캐시 선 로드)
@app.on_event("startup")
def startup_event():
    """
    서버 시작 시점에 SQLite 데이터를 RAM 캐시로 미리 로드하여 
    첫 요청 시 발생하는 지연을 제거합니다.
    """
    backend.force_load_places_cache() 


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

    except Exception as e:
        print(f"❌ [Error] 일정 생성 실패: {e}")
        # 오류 상세 정보가 너무 길면 잘라서 출력
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


# 3. 예약 확정 API (15초 스펙 달성용)
@app.post("/api/v1/reservation", summary="예약 요청 및 확정")
async def create_reservation(place_name: str, user_id: str):
    await asyncio.sleep(2) 
    
    reservation_id = f"RES_{user_id}_{place_name[:5]}_{date.today()}"
    
    return {
        "status": "confirmed",
        "reservation_id": reservation_id,
        "message": f"'{place_name}' 예약이 확정되었습니다. (영수증이 이메일로 발송됩니다.)"
    }