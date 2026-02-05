# tests/benchmark_queries.py - 성능 벤치마크 스크립트
"""
PostgreSQL + PostGIS 성능 테스트
SQLite 대비 성능 향상을 측정합니다.
"""
import time
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend_postgres import get_places, get_places_within_radius


def benchmark():
    """성능 벤치마크 실행"""
    print("\n" + "🔬 " * 25)
    print("🔬  PostgreSQL + PostGIS 성능 벤치마크")
    print("🔬 " * 25 + "\n")
    
    # 테스트 1: 도시별 장소 조회
    print("📊 테스트 1: 도시별 장소 100개 조회")
    start = time.time()
    places = get_places('제주', limit=100)
    duration = (time.time() - start) * 1000
    print(f"   ✅ 완료: {duration:.2f}ms ({len(places)}개 결과)\n")
    
    # 테스트 2: 카테고리 필터링
    print("📊 테스트 2: 카테고리 필터링 (식당)")
    start = time.time()
    restaurants = get_places('제주', category_filter='restaurant', limit=50)
    duration = (time.time() - start) * 1000
    print(f"   ✅ 완료: {duration:.2f}ms ({len(restaurants)}개 결과)\n")
    
    # 테스트 3: 반경 검색 (PostGIS ST_DWithin 활용)
    print("📊 테스트 3: 반경 5km 내 평점 4.0+ 검색 (PostGIS)")
    start = time.time()
    nearby = get_places_within_radius(
        33.5113, 126.493,  # 제주 공항 좌표
        5000,  # 5km
        city='제주',
        min_rating=4.0
    )
    duration = (time.time() - start) * 1000
    print(f"   ✅ 완료: {duration:.2f}ms ({len(nearby)}개 결과)\n")
    
    # 결과 샘플 출력
    if nearby:
        print("📍 가장 가까운 장소 TOP 3:")
        for i, place in enumerate(nearby[:3], 1):
            print(f"   {i}. {place['name']}")
            print(f"      - 거리: {place['distance_km']}km")
            print(f"      - 평점: {place['rating']}")
            print()
    
    print("=" * 70)
    print("✅ 벤치마크 완료!")
    print("=" * 70)
    print("\n💡 Tip: SQLite 버전과 비교하려면 backend.py의 함수들을 벤치마크하세요.")
    print()


if __name__ == "__main__":
    try:
        benchmark()
    except Exception as e:
        print(f"\n❌ 벤치마크 실패: {e}")
        print("\n💡 PostgreSQL이 실행 중이고 .env 설정이 올바른지 확인하세요.")
        import traceback
        traceback.print_exc()
