-- create_tables.sql - Direct SQL for table creation
-- PostGIS types and spatial indexes

-- Places table
CREATE TABLE IF NOT EXISTS places (
    id VARCHAR(100) PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    name VARCHAR(200) NOT NULL,
    city VARCHAR(100) NOT NULL,
    category VARCHAR(100),
    location geography(POINT,4326) NOT NULL,
    address TEXT,
    rating DECIMAL(2, 1),
    img_url TEXT,
    description TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_places_location ON places USING gist (location);
CREATE INDEX IF NOT EXISTS idx_places_city ON places (city);
CREATE INDEX IF NOT EXISTS idx_places_rating ON places (rating DESC);

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
