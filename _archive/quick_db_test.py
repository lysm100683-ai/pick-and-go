# Quick Database Test and Data Insert Script
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import backend_postgres as backend

def test_and_populate():
    print("=" * 60)
    print("데이터베이스 연결 및 데이터 확인 테스트")
    print("=" * 60)
    
    # 1. 서울 데이터 확인
    print("\n1. 서울 장소 데이터 조회 중...")
    seoul_places = backend.get_places("서울")
    print(f"   결과: {len(seoul_places)}개의 장소 발견")
    
    if len(seoul_places) == 0:
        print("\n⚠️ 데이터베이스에 장소 데이터가 없습니다!")
        print("   샘플 데이터를 추가합니다...\n")
        
        # 샘플 데이터 추가
        sample_places = [
            {
                "id": "seoul_001",
                "source": "manual",
                "name": "경복궁",
                "city": "서울",
                "category": "관광명소",
                "lat": 37.5796, "lng": 126.9770,
                "address": "서울특별시 종로구 사직로 161",
                "rating": 4.6,
                "img_url": "https://source.unsplash.com/800x600/?gyeongbokgung",
                "desc": "조선시대 궁궐"
            },
            {
                "id": "seoul_002",
                "source": "manual",
                "name": "남산타워",
                "city": "서울",
                "category": "관광명소",
                "lat": 37.5512, "lng": 126.9882,
                "address": "서울특별시 용산구 남산공원길 105",
                "rating": 4.5,
                "img_url": "https://source.unsplash.com/800x600/?namsan-tower",
                "desc": "서울의 상징적인 타워"
            },
            {
                "id": "seoul_003",
                "source": "manual",
                "name": "명동교자",
                "city": "서울",
                "category": "식당",
                "lat": 37.5636, "lng": 126.9850,
                "address": "서울특별시 중구 명동10길 29",
                "rating": 4.3,
                "img_url": "https://source.unsplash.com/800x600/?korean-food",
                "desc": "유명 칼국수 맛집"
            },
            {
                "id": "seoul_004",
                "source": "manual",
                "name": "광장시장",
                "city": "서울",
                "category": "식당",
                "lat": 37.5701, "lng": 126.9997,
                "address": "서울특별시 종로구 창경궁로 88",
                "rating": 4.4,
                "img_url": "https://source.unsplash.com/800x600/?korean-market",
                "desc": "전통 시장 먹거리"
            },
            {
                "id": "seoul_005",
                "source": "manual",
                "name": "롯데호텔",
                "city": "서울",
                "category": "숙소",
                "lat": 37.5651, "lng": 126.9750,
                "address": "서울특별시 중구 을지로 30",
                "rating": 4.7,
                "img_url": "https://source.unsplash.com/800x600/?luxury-hotel",
                "desc": "5성급 호텔"
            },
            {
                "id": "seoul_006",
                "source": "manual",
                "name": "스타벅스 명동점",
                "city": "서울",
                "category": "카페",
                "lat": 37.5640, "lng": 126.9860,
                "address": "서울특별시 중구 명동길 52",
                "rating": 4.2,
                "img_url": "https://source.unsplash.com/800x600/?cafe",
                "desc": "카페"
            }
        ]
        
        for place in sample_places:
            try:
                backend.save_place(place)
                print(f"   ✅ {place['name']} 추가 완료")
            except Exception as e:
                print(f"   ❌ {place['name']} 추가 실패: {e}")
        
        print("\n2. 데이터 추가 후 재확인...")
        seoul_places = backend.get_places("서울")
        print(f"   결과: {len(seoul_places)}개의 장소 발견")
    
    # 샘플 데이터 출력
    if seoul_places:
        print("\n3. 샘플 데이터:")
        for i, place in enumerate(seoul_places[:3], 1):
            print(f"   {i}. {place['name']} ({place['category']}) - 평점: {place.get('rating', 'N/A')}")
    
    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)

if __name__ == "__main__":
    test_and_populate()
