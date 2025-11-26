# app/main.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from datetime import date
import asyncio
import sys
import os

# ----------------------------------------------------------------
# [중요] 경로 설정
# app 폴더의 상위 폴더(루트)를 sys.path에 추가해야 
# travel_logic.py와 backend.py를 불러올 수 있습니다.
# ----------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__)) # .../pick-and-go/app
root_dir = os.path.dirname(current_dir)                # .../pick-and-go/
sys.path.append(root_dir)

# 이제 루트 경로에 있는 모듈을 임포트합니다.
import travel_logic as logic
from app.models import TravelCondition, ItineraryResponse, DBUpdateRequest


# --- FastAPI 앱 초기화 ---
app = FastAPI(
    title="PicknGo Core API",
    version="2.0.0",
    description="모바일/웹 확장을 위한 고성능 여행 일정 추천 서버"
)

# --- CORS 설정 (프론트엔드 연동 허용) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 개발 중에는 모든 도메인 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 유틸리티: 비동기 래퍼 ---
async def run_in_thread(func, *args):
    """
    CPU를 많이 쓰는 작업(일정 생성)이나 동기식 I/O 작업을 
    별도 스레드에서 실행하여 서버가 멈추지 않게 합니다.
    """
    return await asyncio.to_thread(func, *args)


# ================================================================
# 📡 API 엔드포인트 정의
# ================================================================

@app.get("/")
def health_check():
    """서버 상태 확인용"""
    return {"status": "ok", "message": "PicknGo API Server is Running!"}


# 1. 일정 생성 API (핵심)
@app.post("/api/v1/generate", response_model=ItineraryResponse, summary="여행 일정 생성")
async def generate_itinerary(req: TravelCondition):
    """
    [POST] 사용자의 여행 조건을 받아 최적의 일정 4개를 생성합니다.
    - 내부적으로 travel_logic.generate_plans를 비동기 스레드로 실행합니다.
    """
    try:
        # 1. 날짜 기간 계산
        try:
            d_start = date.fromisoformat(req.start_date)
            d_end = date.fromisoformat(req.end_date)
            duration = (d_end - d_start).days + 1
        except ValueError:
            raise HTTPException(status_code=400, detail="날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)")
        
        if duration <= 0:
            raise HTTPException(status_code=400, detail="종료일이 시작일보다 빠릅니다.")

        # 2. Pydantic 모델을 딕셔너리로 변환 (travel_logic 호환용)
        input_data = req.model_dump()

        # 3. 비동기 실행 (서버 블로킹 방지)
        print(f"🔄 [Processing] {req.dest_city} {duration}일 일정 생성 시작...")
        plans = await run_in_thread(logic.generate_plans, input_data, duration)

        if not plans:
            # 결과가 없는 경우 빈 리스트 반환 (클라이언트가 처리)
            return ItineraryResponse(plans=[])

        print(f"✅ [Success] {len(plans)}개 테마 일정 생성 완료.")
        return ItineraryResponse(plans=plans)

    except Exception as e:
        print(f"❌ [Error] 일정 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 2. DB 업데이트 API (백그라운드 처리)
@app.post("/api/v1/update-db", summary="데이터 수집 요청 (백그라운드)")
async def trigger_db_update(req: DBUpdateRequest, background_tasks: BackgroundTasks):
    """
    [POST] 특정 도시의 데이터를 수집하여 DB를 업데이트합니다.
    - 작업 시간이 길므로 'BackgroundTasks'를 사용하여 백그라운드에서 처리합니다.
    - 클라이언트는 즉시 'accepted' 응답을 받습니다 (UI 멈춤 없음).
    """
    # 백그라운드 작업 예약
    background_tasks.add_task(logic.update_db, req.dest_city, req.styles)
    
    print(f"⏳ [Background] {req.dest_city} 데이터 업데이트 작업 예약됨.")
    return {
        "status": "accepted",
        "message": f"'{req.dest_city}' 데이터 수집 작업이 백그라운드에서 시작되었습니다."
    }


# 3. 예약 확정 API (15초 스펙 달성용)
@app.post("/api/v1/reservation", summary="예약 요청 및 확정")
async def create_reservation(place_name: str, user_id: str):
    """
    [POST] 사용자의 예약 요청을 처리합니다.
    - 실제 파트너사 API와 연동될 예정입니다.
    - 현재는 시뮬레이션으로 2초 후 확정 응답을 보냅니다.
    """
    # API 통신 시뮬레이션 (비동기 대기)
    await asyncio.sleep(2) 
    
    reservation_id = f"RES_{user_id}_{place_name[:5]}_{date.today()}"
    
    return {
        "status": "confirmed",
        "reservation_id": reservation_id,
        "message": f"'{place_name}' 예약이 확정되었습니다. (영수증이 이메일로 발송됩니다.)"
    }