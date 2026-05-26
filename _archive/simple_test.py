# simple_test.py - Simple integration test without emoji
import sys
from backend_postgres import get_places, get_places_within_radius

def main():
    print("="*60)
    print("PostgreSQL + PostGIS Integration Test")
    print("="*60)
    
    # Test 1: Connection
    print("\n[1/3] Testing database connection...")
    try:
        places = get_places('Seoul', limit=1)
        print("  OK - Database connection successful")
    except Exception as e:
        print(f"  FAIL - Connection failed: {e}")
        return 1
    
    # Test 2: Query performance
    print("\n[2/3] Testing query performance...")
    try:
        import time
        start = time.time()
        places = get_places('Seoul', limit=100)
        duration_ms = (time.time() - start) * 1000
        print(f"  OK - Query completed in {duration_ms:.2f}ms")
        print(f"  Found {len(places)} places")
    except Exception as e:
        print(f"  FAIL - Query failed: {e}")
        return 1
    
    # Test 3: PostGIS spatial query
    print("\n[3/3] Testing PostGIS spatial functions...")
    try:
        # Seoul City Hall coordinates
        nearby = get_places_within_radius(37.5665, 126.978, 5000, min_rating=0)
        print(f"  OK - Spatial query successful")
        print(f"  Found {len(nearby)} places within 5km")
        if nearby:
            print(f"  Nearest place: {nearby[0]['name']} ({nearby[0]['distance_km']}km)")
    except Exception as e:
        print(f"  FAIL - Spatial query failed: {e}")
        return 1
    
    print("\n" + "="*60)
    print("All tests passed!")
    print("="*60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
