# Docker 설치 및 PostgreSQL 완전 테스트 가이드

## 📥 1단계: Docker Desktop 설치

### Windows에서 Docker Desktop 설치

1. **Docker Desktop 다운로드**
   - [Docker Desktop for Windows 다운로드](https://www.docker.com/products/docker-desktop/)
   - 또는 직접 다운로드: https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe

2. **설치 진행**
   - 다운로드한 `Docker Desktop Installer.exe` 실행
   - "Use WSL 2 instead of Hyper-V" 옵션 선택 (권장)
   - 설치 완료 후 **컴퓨터 재부팅**

3. **Docker Desktop 시작**
   - 시작 메뉴에서 "Docker Desktop" 실행
   - 첫 실행 시 약 2-3분 소요
   - 시스템 트레이에서 Docker 아이콘이 안정화될 때까지 대기

4. **설치 확인**
   ```powershell
   docker --version
   # 출력 예시: Docker version 24.0.7, build afdd53b
   
   docker ps
   # 출력: CONTAINER ID   IMAGE   COMMAND   CREATED   STATUS   PORTS
   ```

---

## ⚡ 2단계: 자동화된 완전 테스트 실행

Docker 설치가 완료되면 아래 스크립트를 실행하세요:

### 방법 1: PowerShell 스크립트 실행 (권장)

```powershell
# 프로젝트 디렉토리로 이동
cd c:\projects\pick-and-go

# 자동화 스크립트 실행
.\setup_and_test.ps1
```

### 방법 2: 수동 단계별 실행

```powershell
# 1. PostgreSQL 시작
docker-compose -f docker-compose.dev.yml up -d

# 2. PostgreSQL 준비 대기 (10초)
Start-Sleep -Seconds 10

# 3. 연결 확인
docker exec -it pickandgo-db psql -U pickandgo_admin -d pickandgo_dev -c "SELECT version();"

# 4. PostGIS 확인
docker exec -it pickandgo-db psql -U pickandgo_admin -d pickandgo_dev -c "SELECT PostGIS_Version();"

# 5. 테이블 생성
python -c "from db.connection import init_db; init_db()"

# 6. 데이터 마이그레이션
python scripts/migrate_sqlite_to_postgres.py

# 7. 데이터 확인
docker exec -it pickandgo-db psql -U pickandgo_admin -d pickandgo_dev -c "SELECT COUNT(*) FROM places;"
docker exec -it pickandgo-db psql -U pickandgo_admin -d pickandgo_dev -c "SELECT COUNT(*) FROM movement_cache;"

# 8. 성능 벤치마크
python tests/benchmark_queries.py

# 9. 코드 검증
python validate_code.py
```

---

## 🔍 3단계: 테스트 결과 확인

### 예상 결과

#### PostgreSQL 버전
```
PostgreSQL 15.x on x86_64-pc-linux-gnu
```

#### PostGIS 버전
```
3.4 USE_GEOS=... USE_PROJ=...
```

#### 테이블 생성
```
✅ 데이터베이스 테이블 생성 완료
```

#### 마이그레이션
```
✅ PostgreSQL에 XXX개 장소 저장 완료!
✅ PostgreSQL에 XXX개 캐시 항목 저장 완료!
```

#### 벤치마크 (예상 성능)
```
📊 테스트 1: 도시별 장소 100개 조회
   ✅ 완료: 5.23ms (100개 결과)

📊 테스트 2: 카테고리 필터링 (식당)
   ✅ 완료: 3.45ms (50개 결과)

📊 테스트 3: 반경 5km 내 평점 4.0+ 검색 (PostGIS)
   ✅ 완료: 4.12ms (XX개 결과)
```

---

## 🛠️ 트러블슈팅

### "docker: command not found"
→ Docker Desktop이 완전히 시작되지 않았을 수 있음
   - Docker Desktop GUI에서 "Engine running" 확인
   - PowerShell 재시작

### "Cannot connect to the Docker daemon"
→ Docker Desktop 실행 중인지 확인
   - 시스템 트레이에서 Docker 아이콘 확인
   - Docker Desktop 재시작

### "port 5432 already allocated"
→ 다른 PostgreSQL이 5432 포트 사용 중
```powershell
# 실행 중인 서비스 확인
Get-NetTCPConnection -LocalPort 5432

# 해결책 1: 기존 PostgreSQL 중지
# 해결책 2: docker-compose.dev.yml에서 포트 변경 (5432:5432 → 5433:5432)
```

### "psycopg2.OperationalError: connection refused"
→ PostgreSQL 시작 완료 대기 필요
```powershell
# 로그 확인
docker logs pickandgo-db

# 상태 확인
docker ps
```

### 마이그레이션 중 "유효하지 않은 좌표" 경고
→ 정상 동작 (SQLite에 0.0 좌표 있음)
   - 스크립트가 자동으로 필터링함

---

## 🧹 정리 명령어

### PostgreSQL 중지
```powershell
docker-compose -f docker-compose.dev.yml down
```

### 데이터까지 삭제 (완전 초기화)
```powershell
docker-compose -f docker-compose.dev.yml down -v
```

### 컨테이너 재시작
```powershell
docker-compose -f docker-compose.dev.yml restart
```

---

## 📊 Docker 설치 후 체크리스트

- [ ] Docker Desktop 다운로드
- [ ] Docker Desktop 설치
- [ ] 컴퓨터 재부팅
- [ ] Docker Desktop 실행
- [ ] `docker --version` 성공
- [ ] `docker ps` 성공
- [ ] `setup_and_test.ps1` 실행 (또는 수동 단계)
- [ ] 모든 테스트 통과

---

## 💡 다음 단계 (테스트 완료 후)

1. **API 통합 테스트**
   - FastAPI 서버 시작
   - `/api/v1/generate` 엔드포인트 테스트

2. **Streamlit 앱 연동**
   - `travel_logic.py`를 `backend_postgres` 사용하도록 수정

3. **Phase 2 계획**
   - Redis 캐싱 레이어 설계
   - 세션 관리 구현
