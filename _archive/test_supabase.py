"""Supabase 최종 연결 테스트 및 테이블 생성"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

print(f"[연결 시도] {DATABASE_URL[:60]}...")

try:
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=15)
    cur = conn.cursor()
    cur.execute("SELECT version();")
    print(f"[OK] 연결 성공! {cur.fetchone()[0]}")

    print("\n[DB 초기화] 기존 스키마 확인 중...")
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    conn.commit()
    print("  [OK] PostGIS extension loaded")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS places (
            id VARCHAR(100) PRIMARY KEY,
            source VARCHAR(50) NOT NULL,
            name VARCHAR(200) NOT NULL,
            city VARCHAR(100) NOT NULL,
            category VARCHAR(100),
            location geography(POINT,4326) NOT NULL,
            address TEXT,
            rating DECIMAL(2,1),
            img_url TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_places_location ON places USING gist(location);
        CREATE INDEX IF NOT EXISTS idx_places_city ON places(city);
        CREATE INDEX IF NOT EXISTS idx_places_rating ON places(rating DESC);
        
        CREATE TABLE IF NOT EXISTS movement_cache (
            id SERIAL PRIMARY KEY,
            origin geography(POINT,4326) NOT NULL,
            destination geography(POINT,4326) NOT NULL,
            mode VARCHAR(20) NOT NULL,
            duration_seconds INTEGER NOT NULL,
            is_korea BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_movement_cache_origin ON movement_cache USING gist (origin);
        CREATE INDEX IF NOT EXISTS idx_movement_cache_destination ON movement_cache USING gist (destination);

        CREATE TABLE IF NOT EXISTS reservations (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(100) NOT NULL,
            trip_data JSONB NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );
    """)
    conn.commit()
    print("  [OK] All tables created successfully")

    # 테이블 목록 확인
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public';")
    tables = [row[0] for row in cur.fetchall()]
    print("\n[Created Tables]")
    for t in tables:
        print(f"  - {t}")

    cur.close()
    conn.close()
    print("\n[SUCCESS] Supabase setup is complete!")

except Exception as e:
    import traceback
    print("\n[FAIL] Error occurred:")
    traceback.print_exc()
