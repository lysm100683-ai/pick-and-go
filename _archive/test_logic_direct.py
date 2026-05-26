# Direct test of travel_logic without API
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import travel_logic as logic

# 테스트 데이터
test_data = {
    "dep_city": "인천",
    "dest_city": "서울",
    "start_date": "2026-03-01",
    "end_date": "2026-03-02",
    "style": ["문화탐방"],  # travel_logic.py에서 'style' 사용
    "budget_level": "중",
    "people": 1,
    "transport": ["항공"],
    "local_transport": "대중교통",
    "pace": "보통"
}

print("=" * 60)
print("travel_logic.generate_plans() 직접 테스트")
print("=" * 60)

try:
    print("\n1. generate_plans 호출...")
    result = logic.generate_plans(test_data, duration=1)
    
    print(f"\n2. 결과:")
    print(f"   생성된 플랜 수: {len(result) if result else 0}")
    
    if result:
        print(f"\n✅ 성공!")
        for i, plan in enumerate(result, 1):
            print(f"\n   플랜 {i}: {plan.get('theme', 'N/A')}")
            print(f"   설명: {plan.get('desc', 'N/A')}")
            print(f"   일차 수: {len(plan.get('days', []))}")
            if plan.get('days'):
                first_day = plan['days'][0]
                print(f"   1일차 장소 수: {len(first_day.get('places', []))}")
                if first_day.get('places'):
                    for j, place in enumerate(first_day['places'][:3], 1):
                        print(f"      {j}. {place.get('name', 'N/A')} ({place.get('type', 'N/A')})")
    else:
        print("\n❌ 결과가 비어있습니다!")
        
except Exception as e:
    print(f"\n❌ 에러 발생:")
    print(f"   타입: {type(e).__name__}")
    print(f"   메시지: {str(e)}")
    
    # 상세 traceback
    import traceback
    print(f"\n상세 Traceback:")
    traceback.print_exc()

print("\n" + "=" * 60)
