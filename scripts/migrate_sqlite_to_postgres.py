# scripts/migrate_sqlite_to_postgres.py
"""
SQLite → PostgreSQL + PostGIS 데이터 마이그레이션 스크립트

이 스크립트는 기존 travel_data.db의 데이터를 PostgreSQL로 이전합니다.
"""
import sqlite3
import psycopg2
from psycopg2.extras import execute_batch
from datetime import datetime
import os
import shutil
from dotenv import load_dotenv

load_dotenv()


def migrate_places():
    """Places 테이블 마이그레이션"""
    
    print("[1/2] PLACES 테이블 마이그레이션 시작")
    print("=" * 60)
    
    # 기존 SQLite 연결
    if not os.path.exists('travel_data.db'):
        print("[WARN] travel_data.db 파일이 없습니다. 스킵합니다.")
        return 0
    
    sqlite_conn = sqlite3.connect('travel_data.db')
    sqlite_cursor = sqlite_conn.cursor()
    
    # PostgreSQL 연결
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL 환경 변수가 설정되지 않았습니다.")
    
    pg_conn = psycopg2.connect(database_url)
    pg_cursor = pg_conn.cursor()
    
    print("[INFO] SQLite에서 데이터 읽기 중...")
    sqlite_cursor.execute("SELECT * FROM places")
    rows = sqlite_cursor.fetchall()
    
    print(f"   총 {len(rows)}개 장소 발견")
    
    # PostGIS 포맷으로 변환
    insert_query = """
        INSERT INTO places (id, source, name, city, category, location, 
                           address, rating, img_url, description, updated_at)
        VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            location = EXCLUDED.location,
            rating = EXCLUDED.rating,
            updated_at = EXCLUDED.updated_at
    """
    
    data = []
    skipped = 0
    
    for row in rows:
        # row = (id, source, name, city, category, lat, lng, address, rating, img_url, desc, updated_at)
        lat = row[5]
        lng = row[6]
        
        # 유효하지 않은 좌표 필터링
        if lat in (0.0, None) or lng in (0.0, None):
            skipped += 1
            continue
        
        try:
            data.append((
                row[0],  # id
                row[1],  # source
                row[2],  # name
                row[3],  # city
                row[4],  # category
                float(lng), float(lat),  # PostGIS는 경도, 위도 순서!
                row[7],  # address
                float(row[8]) if row[8] else 0.0,  # rating
                row[9],  # img_url
                row[10] if row[10] else '',  # description
                row[11] if row[11] else datetime.now().isoformat()  # updated_at
            ))
        except Exception as e:
            print(f"   [ERROR] 행 변환 실패 (ID: {row[0]}): {e}")
            skipped += 1
            continue
    
    print(f"[OK] {len(data)}개 장소 변환 완료 (스킵: {skipped}개)")
    
    # 배치 삽입
    print("[INFO] PostgreSQL에 데이터 삽입 중...")
    execute_batch(pg_cursor, insert_query, data, page_size=100)
    pg_conn.commit()
    
    print(f"[OK] PostgreSQL에 {len(data)}개 장소 저장 완료!")
    print(f"[WARN] 유효하지 않은 좌표로 스킵된 항목: {skipped}개")
    
    pg_cursor.close()
    pg_conn.close()
    sqlite_cursor.close()
    sqlite_conn.close()
    
    return len(data)


def migrate_movement_cache():
    """MovementCache 테이블 마이그레이션"""
    
    print("\n[2/2] MOVEMENT_CACHE 테이블 마이그레이션 시작")
    print("=" * 60)
    
    sqlite_conn = sqlite3.connect('travel_data.db')
    sqlite_cursor = sqlite_conn.cursor()
    
    pg_conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    pg_cursor = pg_conn.cursor()
    
    print("[INFO] 이동 시간 캐시 읽기 중...")
    
    try:
        sqlite_cursor.execute("SELECT * FROM movement_cache")
        rows = sqlite_cursor.fetchall()
    except Exception as e:
        print(f"[WARN] movement_cache 테이블 없음 또는 오류: {e}")
        return 0
    
    print(f"   총 {len(rows)}개 캐시 항목 발견")
    
    insert_query = """
        INSERT INTO movement_cache (origin, destination, mode, duration_seconds, is_korea, cached_at)
        VALUES (ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """
    
    data = []
    skipped = 0
    
    for row in rows:
        # row = (origin_key, dest_key, mode, duration, is_korea)
        # origin_key 파싱 (예: "37.5665,126.9780")
        try:
            origin_parts = row[0].split(',')
            dest_parts = row[1].split(',')
            
            if len(origin_parts) != 2 or len(dest_parts) != 2:
                skipped += 1
                continue
            
            origin_lat, origin_lng = float(origin_parts[0]), float(origin_parts[1])
            dest_lat, dest_lng = float(dest_parts[0]), float(dest_parts[1])
            
            data.append((
                origin_lng, origin_lat,  # origin (lng, lat)
                dest_lng, dest_lat,      # destination (lng, lat)
                row[2],  # mode
                int(row[3]),  # duration_seconds
                bool(row[4]),  # is_korea
                datetime.now()  # cached_at
            ))
        except Exception as e:
            print(f"   [ERROR] 행 파싱 실패: {e}")
            skipped += 1
            continue
    
    print(f"[OK] {len(data)}개 캐시 항목 변환 완료 (스킵: {skipped}개)")
    
    if data:
        print("[INFO] PostgreSQL에 데이터 삽입 중...")
        execute_batch(pg_cursor, insert_query, data, page_size=100)
        pg_conn.commit()
        print(f"[OK] {len(data)}개 캐시 항목 저장 완료!\n")
    
    pg_cursor.close()
    pg_conn.close()
    sqlite_cursor.close()
    sqlite_conn.close()
    
    return len(data)


def main():
    """메인 마이그레이션 함수"""
    print("\n" + "=" * 60)
    print("  SQLite -> PostgreSQL 마이그레이션")
    print("=" * 60 + "\n")
    
    # 1. 백업 생성
    if os.path.exists('travel_data.db'):
        backup_path = f"travel_data.db.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy('travel_data.db', backup_path)
        print(f"[INFO] 백업 완료: {backup_path}\n")
    
    # 2. 마이그레이션 실행
    try:
        places_count = migrate_places()
        cache_count = migrate_movement_cache()
        
        print("\n" + "=" * 60)
        print("  마이그레이션 완료!")
        print("=" * 60)
        print(f"   - Places: {places_count}개")
        print(f"   - Movement Cache: {cache_count}개")
        print()
        
    except Exception as e:
        print(f"\n[ERROR] 마이그레이션 실패: {e}")
        raise


if __name__ == "__main__":
    main()
