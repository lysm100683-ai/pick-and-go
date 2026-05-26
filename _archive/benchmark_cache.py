import sys
import os
import time

sys.path.append(os.getcwd())
from sqlalchemy import func, or_, and_
from db.connection import get_db_session
from db.models import MovementCache
from geoalchemy2 import WKTElement
from config import Config

def run_benchmark():
    print("="*60)
    print("PostGIS ST_Distance vs ST_DWithin 성능 비교 벤치마크")
    print("="*60)
    
    with get_db_session() as session:
        # 데이터 수 확인
        count = session.query(MovementCache).count()
        print(f"현재 DB 캐시 데이터 수량: {count}건")
        
        # 벤치마크를 위해 데이터가 너무 적으면 가상 데이터 1000건 삽입
        if count < 1000:
            print("\n벤치마크를 위해 가상 더미 데이터(1000건)를 임시로 삽입합니다...")
            for i in range(1000):
                lat = 37.0 + (i * 0.001)
                lng = 127.0 + (i * 0.001)
                cache = MovementCache(
                    origin=WKTElement(f'SRID=4326;POINT({lng} {lat})', srid=4326),
                    destination=WKTElement(f'SRID=4326;POINT({lng+0.01} {lat+0.01})', srid=4326),
                    mode='driving',
                    duration_seconds=1000,
                    is_korea=True
                )
                session.add(cache)
                if i % 500 == 0:
                    session.commit()
            session.commit()
            count = session.query(MovementCache).count()
            print(f"가상 데이터 삽입 완료! (현재 수량: {count}건)\n")

        # 테스트용 좌표
        origin_wkt = f'SRID=4326;POINT(127.0 37.0)'
        dest_wkt = f'SRID=4326;POINT(127.01 37.01)'
        origin_point = WKTElement(origin_wkt, srid=4326)
        dest_point = WKTElement(dest_wkt, srid=4326)
        
        # 1. 기존 방식 테스트
        print("[비교 1] AS-IS 방식: ST_Distance (풀 스캔 발생)")
        start_time = time.time()
        for _ in range(10): # 차이를 명확히 하기 위해 10번 반복 실행
            query_distance = session.query(MovementCache).filter(
                or_(
                    and_(
                        func.ST_Distance(MovementCache.origin, origin_point) < Config.CACHE_MATCH_TOLERANCE_METERS,
                        func.ST_Distance(MovementCache.destination, dest_point) < Config.CACHE_MATCH_TOLERANCE_METERS,
                    )
                )
            ).first()
        dist_time = (time.time() - start_time) / 10
        print(f" -> 1회 평균 실행 시간: {dist_time:.5f} 초\n")

        # 2. 개선 방식 테스트
        print("[비교 2] TO-BE 방식: ST_DWithin (GiST 공간 인덱스 사용)")
        start_time = time.time()
        for _ in range(10): # 10번 반복
            query_dwithin = session.query(MovementCache).filter(
                or_(
                    and_(
                        func.ST_DWithin(MovementCache.origin, origin_point, Config.CACHE_MATCH_TOLERANCE_METERS),
                        func.ST_DWithin(MovementCache.destination, dest_point, Config.CACHE_MATCH_TOLERANCE_METERS),
                    )
                )
            ).first()
        dwithin_time = (time.time() - start_time) / 10
        print(f" -> 1회 평균 실행 시간: {dwithin_time:.5f} 초\n")
        
        improvement = 0
        if dwithin_time > 0 and dist_time > 0:
            improvement = dist_time / dwithin_time
            
        print("="*60)
        print(f"결론: 신규 방식(ST_DWithin)이 기존 대비 약 {improvement:.1f}배 더 빠릅니다.")
        print("="*60)

if __name__ == "__main__":
    run_benchmark()
