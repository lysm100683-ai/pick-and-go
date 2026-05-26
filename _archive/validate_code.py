# validate_code.py - 코드 유효성 검증 스크립트
"""
PostgreSQL 연결 없이 코드 품질만 검증합니다.
"""
import sys
import importlib.util

def check_module(module_name, file_path=None):
    """모듈 import 가능 여부 확인"""
    try:
        if file_path:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            __import__(module_name)
        print(f"[OK] {module_name}")
        return True
    except Exception as e:
        print(f"[FAIL] {module_name}: {e}")
        return False

def main():
    """메인 검증 로직"""
    print("=" * 60)
    print("Phase 1 코드 유효성 검증")
    print("=" * 60)
    print()
    
    results = []
    
    # 1. 설정 모듈
    print("1. Config 모듈 검증...")
    results.append(check_module("config", "config.py"))
    
    # 2. ORM 모델
    print("\n2. ORM Models 검증...")
    results.append(check_module("db.models"))
    
    # 3. 데이터베이스 연결 (import만, 실제 연결 안 함)
    print("\n3. Database Connection 모듈 검증...")
    try:
        from db import connection
        print("[OK] db.connection (import만 확인)")
        results.append(True)
    except Exception as e:
        print(f"[FAIL] db.connection: {e}")
        results.append(False)
    
    # 4. Backend 모듈
    print("\n4. Backend 모듈 검증...")
    results.append(check_module("backend_postgres", "backend_postgres.py"))
    
    # 5. 마이그레이션 스크립트
    print("\n5. Migration 스크립트 검증...")
    results.append(check_module("scripts.migrate_sqlite_to_postgres"))
    
    # 6. 주요 함수 존재 확인
    print("\n6. 주요 함수 확인...")
    try:
        import backend_postgres as bp
        functions = ['get_places', 'get_places_within_radius', 'save_place', 
                    'get_movement_cache', 'save_movement_cache']
        all_present = all(hasattr(bp, f) for f in functions)
        if all_present:
            print(f"[OK] 모든 주요 함수 존재: {', '.join(functions)}")
            results.append(True)
        else:
            print("[FAIL] 일부 함수 누락")
            results.append(False)
    except Exception as e:
        print(f"[FAIL] 함수 확인 실패: {e}")
        results.append(False)
    
    # 7. Config 설정 확인
    print("\n7. Config 설정 확인...")
    try:
        from config import Config
        print(f"   DATABASE_URL: {'설정됨' if Config.DATABASE_URL else '미설정'}")
        print(f"   GMAPS_API_KEY: {'설정됨' if Config.GMAPS_API_KEY and Config.GMAPS_API_KEY != 'YOUR_GOOGLE_MAPS_API_KEY' else '미설정 (기본값)'}")
        print(f"   KAKAO_REST_KEY: {'설정됨' if Config.KAKAO_REST_KEY and Config.KAKAO_REST_KEY != 'YOUR_KAKAO_REST_API_KEY' else '미설정 (기본값)'}")
        results.append(True)
    except Exception as e:
        print(f"[FAIL] Config 설정 확인 실패: {e}")
        results.append(False)
    
    # 결과 요약
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    success_rate = (passed / total) * 100
    
    print(f"검증 결과: {passed}/{total} 통과 ({success_rate:.1f}%)")
    
    if passed == total:
        print("\n모든 코드 검증 통과!")
        print("다음 단계: PostgreSQL 설정 및 마이그레이션 실행")
        return 0
    else:
        print(f"\n{total - passed}개 항목 실패. 위 오류 메시지 확인 필요")
        return 1

if __name__ == "__main__":
    sys.exit(main())
