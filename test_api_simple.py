import requests
import json

# API 호출 테스트
url = "http://localhost:8000/api/v1/generate"

# 요청 데이터
data = {
    "dep_city": "인천",
    "dest_city": "서울",
    "start_date": "2026-03-01",
    "end_date": "2026-03-02",
    "travel_styles": ["문화탐방"],
    "budget_level": "중",
    "people": 1
}

print("=" * 60)
print("여행 일정 생성 API 테스트")
print("=" * 60)
print("\n요청 데이터:")
print(json.dumps(data, ensure_ascii=False, indent=2))
print("\n")

try:
    response = requests.post(url, json=data, timeout=30)
    
    print(f"상태 코드: {response.status_code}")
    print(f"\n응답 헤더:")
    for key, value in response.headers.items():
        print(f"  {key}: {value}")
    
    print(f"\n응답 본문:")
    try:
        json_response = response.json()
        print(json.dumps(json_response, ensure_ascii=False, indent=2))
        
        if response.status_code == 200:
            print("\n✅ 성공! 여행 일정이 생성되었습니다.")
            if 'plans' in json_response:
                print(f"   생성된 테마 수: {len(json_response['plans'])}")
        else:
            print(f"\n❌ 에러 발생: {response.status_code}")
            
    except json.JSONDecodeError:
        print(response.text)
        
except requests.exceptions.Timeout:
    print("❌ 타임아웃: 서버 응답이 30초 내에 오지 않았습니다.")
except requests.exceptions.ConnectionError:
    print("❌ 연결 오류: 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
except Exception as e:
    print(f"❌ 예상치 못한 오류: {e}")

print("\n" + "=" * 60)
