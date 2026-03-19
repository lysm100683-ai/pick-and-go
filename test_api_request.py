# test_api_request.py - Test API endpoint with PostgreSQL data
import requests
import json

# Test data - 제주 여행 (데이터베이스에 208개 제주 장소 있음)
test_request = {
    "dest_city": "제주",
    "dep_city": "서울",  # Required field
    "start_date": "2026-03-01",
    "end_date": "2026-03-03",
    "people": 2,  # Required field
    "budget_level": "medium",  # Required field
    "styles": ["sight", "food", "cafe"],
    "theme": "✨ 핵심 코스"
}

print("=" * 60)
print("Testing FastAPI with PostgreSQL Backend")
print("=" * 60)

# Health check
print("\n[1/3] Health Check...")
try:
    response = requests.get("http://127.0.0.1:8000/")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Generate itinerary
print("\n[2/3] Generate Itinerary...")
print(f"  Request: {test_request['dest_city']}, {test_request['start_date']} ~ {test_request['end_date']}")
try:
    response = requests.post(
        "http://127.0.0.1:8000/api/v1/generate",
        json=test_request,
        timeout=30
    )
    print(f"  Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        plans = data.get('plans', [])
        print(f"  Success! Generated {len(plans)} theme plans")
        
        if plans:
            first_plan = plans[0]
            print(f"    Theme: {first_plan.get('theme', 'Unknown')}")
            print(f"    Days: {len(first_plan.get('days', []))}")
            if first_plan.get('days'):
                first_day = first_plan['days'][0]
                print(f"    Day 1 places: {len(first_day.get('items', []))}")
    else:
        print(f"  ERROR: {response.text}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test backend directly
print("\n[3/3] Direct Backend Test...")
try:
    import sys
    sys.path.insert(0, 'c:/projects/pick-and-go')
    from backend_postgres import get_places
    
    jeju_places = get_places('제주', limit=10)
    print(f"  Found {len(jeju_places)} places in database")
    if jeju_places:
        print(f"  Sample: {jeju_places[0]['name']} (rating: {jeju_places[0]['rating']})")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)
