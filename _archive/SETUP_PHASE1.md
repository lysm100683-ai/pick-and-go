# Phase 1 Setup Guide: PostgreSQL + PostGIS Migration

## 🚀 빠른 시작 (Quick Start)

### 1단계: 환경 변수 설정

```bash
# .env.example을 복사하여 .env 파일 생성
copy .env.example .env

# .env 파일을 열고 API 키 설정 (이미 있다면 기존 값 사용)
# GMAPS_API_KEY=your_actual_google_key
# KAKAO_REST_KEY=your_actual_kakao_key
```

### 2단계: Python 패키지 설치

```bash
pip install -r requirements.txt
```

### 3단계: PostgreSQL + PostGIS 시작 (Docker)

```bash
# Docker Compose로 PostgreSQL 시작
docker-compose -f docker-compose.dev.yml up -d

# 실행 확인
docker ps
# pickandgo-db 컨테이너가 실행 중이어야 함

# 연결 테스트
docker exec -it pickandgo-db psql -U pickandgo_admin -d pickandgo_dev -c "SELECT PostGIS_Version();"
```

### 4단계: 데이터베이스 테이블 생성

```bash
# SQLAlchemy로 테이블 자동 생성
python -c "from db.connection import init_db; init_db()"
```

### 5단계: 데이터 마이그레이션 (SQLite → PostgreSQL)

```bash
# 마이그레이션 스크립트 실행
python scripts/migrate_sqlite_to_postgres.py
```

### 6단계: 검증

```bash
# PostgreSQL에 접속하여 데이터 확인
docker exec -it pickandgo-db psql -U pickandgo_admin -d pickandgo_dev

# SQL:
SELECT COUNT(*) FROM places;
SELECT COUNT(*) FROM movement_cache;
```

---

## 📋 트러블슈팅

### 🔴 문제: "DATABASE_URL 환경 변수가 설정되지 않았습니다"

**해결책**: `.env` 파일이 프로젝트 루트에 있고 내용이 올바른지 확인

```bash
# .env 내용 확인
type .env
```

### 🔴 문제: Docker 컨테이너 시작 실패

**해결책**: 포트 5432가 이미 사용 중일 수 있음

```bash
# 포트 사용 확인
netstat -ano | findstr :5432

# 다른 PostgreSQL이 실행 중이면 중지하거나
# docker-compose.dev.yml에서 포트 변경 (예: "5433:5432")
```

### 🔴 문제: 마이그레이션 중 "좌표 변환 실패"

**해결책**: SQLite 데이터에 유효하지 않은 좌표(0.0, null)가 있음. 스크립트가 자동으로 스킵함.

---

## ⏭️ 다음 단계

Phase 1 완료 후:
1. `travel_logic.py`를 `backend_postgres`를 사용하도록 수정
2. FastAPI 서버 재시작 및 테스트
3. 성능 벤치마크 실행
