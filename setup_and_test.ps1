# setup_and_test.ps1 - PostgreSQL 자동 설정 및 테스트 스크립트
# 사용법: .\setup_and_test.ps1

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "  PostgreSQL + PostGIS 자동 설정 및 테스트" -ForegroundColor Yellow
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host ""

# 1. Docker 확인
Write-Host "[1/9] Docker 설치 확인..." -ForegroundColor Green
try {
    $dockerVersion = docker --version
    Write-Host "  ✓ Docker 설치됨: $dockerVersion" -ForegroundColor Gray
}
catch {
    Write-Host "  ✗ Docker가 설치되지 않았습니다!" -ForegroundColor Red
    Write-Host "  DOCKER_SETUP_GUIDE.md를 참고하여 Docker Desktop을 설치하세요." -ForegroundColor Yellow
    exit 1
}

# 2. 기존 컨테이너 정리
Write-Host "`n[2/9] 기존 컨테이너 정리..." -ForegroundColor Green
docker-compose -f docker-compose.dev.yml down -v 2>$null
Write-Host "  ✓ 정리 완료" -ForegroundColor Gray

# 3. PostgreSQL 시작
Write-Host "`n[3/9] PostgreSQL + PostGIS 컨테이너 시작..." -ForegroundColor Green
docker-compose -f docker-compose.dev.yml up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ PostgreSQL 시작 실패!" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ 컨테이너 시작 완료" -ForegroundColor Gray

# 4. PostgreSQL 준비 대기
Write-Host "`n[4/9] PostgreSQL 준비 대기 (15초)..." -ForegroundColor Green
Start-Sleep -Seconds 15
Write-Host "  ✓ 대기 완료" -ForegroundColor Gray

# 5. PostgreSQL 연결 테스트
Write-Host "`n[5/9] PostgreSQL 연결 테스트..." -ForegroundColor Green
try {
    docker exec pickandgo-db psql -U pickandgo_admin -d pickandgo_dev -c "SELECT 1;" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK PostgreSQL 연결 성공" -ForegroundColor Gray
    }
    else {
        Write-Host "  FAIL PostgreSQL 연결 실패" -ForegroundColor Red
        Write-Host "  로그 확인: docker logs pickandgo-db" -ForegroundColor Yellow
        exit 1
    }
}
catch {
    Write-Host "  FAIL PostgreSQL 연결 실패: $_" -ForegroundColor Red
    exit 1
}

# 6. PostGIS 확인
Write-Host "`n[6/9] PostGIS 확장 확인..." -ForegroundColor Green
try {
    $null = docker exec pickandgo-db psql -U pickandgo_admin -d pickandgo_dev -c "SELECT PostGIS_Version();" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK PostGIS 설치 확인" -ForegroundColor Gray
    }
    else {
        Write-Host "  FAIL PostGIS 확장 없음" -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "  FAIL PostGIS 확장 확인 실패: $_" -ForegroundColor Red
    exit 1
}

# 7. 테이블 생성
Write-Host "`n[7/9] 데이터베이스 테이블 생성..." -ForegroundColor Green
python -c "from db.connection import init_db; init_db()" 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ 테이블 생성 완료" -ForegroundColor Gray
}
else {
    Write-Host "  ✗ 테이블 생성 실패" -ForegroundColor Red
    exit 1
}

# 8. 데이터 마이그레이션 (SQLite DB가 있는 경우)
Write-Host "`n[8/9] 데이터 마이그레이션..." -ForegroundColor Green
if (Test-Path "travel_data.db") {
    python scripts/migrate_sqlite_to_postgres.py
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ 마이그레이션 완료" -ForegroundColor Gray
        
        # 데이터 개수 확인
        $placesCount = docker exec pickandgo-db psql -U pickandgo_admin -d pickandgo_dev -t -c "SELECT COUNT(*) FROM places;" 2>$null
        $cacheCount = docker exec pickandgo-db psql -U pickandgo_admin -d pickandgo_dev -t -c "SELECT COUNT(*) FROM movement_cache;" 2>$null
        Write-Host "    - Places: $($placesCount.Trim())개" -ForegroundColor Gray
        Write-Host "    - Movement Cache: $($cacheCount.Trim())개" -ForegroundColor Gray
    }
    else {
        Write-Host "  ✗ 마이그레이션 실패" -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "  ⊘ travel_data.db 없음, 스킵" -ForegroundColor Yellow
}

# 9. 성능 벤치마크
Write-Host "`n[9/9] 성능 벤치마크 실행..." -ForegroundColor Green
python tests/benchmark_queries.py
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ 벤치마크 완료" -ForegroundColor Gray
}
else {
    Write-Host "  ! 벤치마크 실패 (데이터 부족 가능)" -ForegroundColor Yellow
}

# 완료 메시지
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "  설정 및 테스트 완료!" -ForegroundColor Green
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host ""
Write-Host "다음 명령어로 PostgreSQL 관리:" -ForegroundColor Yellow
Write-Host "  - 컨테이너 상태: docker ps" -ForegroundColor Gray
Write-Host "  - 로그 확인: docker logs pickandgo-db" -ForegroundColor Gray
Write-Host "  - PostgreSQL 접속: docker exec -it pickandgo-db psql -U pickandgo_admin -d pickandgo_dev" -ForegroundColor Gray
Write-Host "  - 중지: docker-compose -f docker-compose.dev.yml down" -ForegroundColor Gray
Write-Host ""
