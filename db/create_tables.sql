-- create_tables.sql - Direct SQL for table creation
-- PostGIS types and spatial indexes

-- Places table
CREATE TABLE IF NOT EXISTS places (
    id VARCHAR(100) PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    name VARCHAR(200) NOT NULL,
    city VARCHAR(100) NOT NULL,
    category VARCHAR(100),
    sub_category VARCHAR(100),                          -- 세부 카테고리 (예: 한식, 자연경관)
    location geography(POINT,4326) NOT NULL,
    address TEXT,
    rating DECIMAL(2, 1),
    review_count INTEGER DEFAULT 0,                     -- 리뷰 수 (점수 가중치 산정에 활용)
    img_url TEXT,
    description TEXT,
    created_at  TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    updated_at  TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    verified_at TIMESTAMP WITHOUT TIME ZONE             -- 영업 확인 마지막 시각 (NULL = 미확인)
);

CREATE INDEX IF NOT EXISTS idx_places_location     ON places USING gist (location);
CREATE INDEX IF NOT EXISTS idx_places_city         ON places (city);
CREATE INDEX IF NOT EXISTS idx_places_category     ON places (category);
CREATE INDEX IF NOT EXISTS idx_places_sub_category ON places (sub_category);
CREATE INDEX IF NOT EXISTS idx_places_rating       ON places (rating DESC);
CREATE INDEX IF NOT EXISTS idx_places_verified_at  ON places (verified_at);

-- [Migration] 기존 DB에 컬럼 추가 시 아래 ALTER 구문 실행
-- (이미 있는 컬럼이면 에러 가능, IF NOT EXISTS 사용 권장)
-- ALTER TABLE places ADD COLUMN IF NOT EXISTS sub_category  VARCHAR(100);
-- ALTER TABLE places ADD COLUMN IF NOT EXISTS review_count  INTEGER DEFAULT 0;
-- ALTER TABLE places ADD COLUMN IF NOT EXISTS verified_at   TIMESTAMP WITHOUT TIME ZONE;

-- Movement cache table
CREATE TABLE IF NOT EXISTS movement_cache (
    id SERIAL PRIMARY KEY,
    origin geography(POINT,4326) NOT NULL,
    destination geography(POINT,4326) NOT NULL,
    mode VARCHAR(20) NOT NULL,
    duration_seconds INTEGER NOT NULL,
    is_korea BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_movement_cache_origin ON movement_cache USING gist (origin);
CREATE INDEX IF NOT EXISTS idx_movement_cache_destination ON movement_cache USING gist (destination);

-- Reservations table
CREATE TABLE IF NOT EXISTS reservations (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    trip_data JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
);
