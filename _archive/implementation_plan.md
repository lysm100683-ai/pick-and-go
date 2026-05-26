# Pick & Go — Next.js + Supabase + Vercel + Render 전환 계획

## 목표 아키텍처

```
[사용자 브라우저]
       ↓
[Vercel — Next.js 14]   ← 프론트엔드 UI
       ↓ API 호출
[Render.com — FastAPI]  ← 기존 Python 코드 그대로
       ↓
[Supabase — PostgreSQL + PostGIS]
 ├── places 테이블
 ├── movement_cache 테이블
 └── reservations 테이블
```

### 비용 요약 — 전부 무료
| 서비스 | 무료 한도 | 사용 목적 |
|--------|---------|---------|
| **Vercel** | 무제한 (hobby) | Next.js 프론트엔드 |
| **Render.com** | 750시간/월 | FastAPI 백엔드 |
| **Supabase** | 500MB / 5GB 트래픽 | PostgreSQL + PostGIS |

---

## 구현 단계

### Phase A — Supabase DB 설정 ← 완료!
- [x] Supabase 프로젝트 생성 및 DB URL 확보
- [x] PostGIS 확장 활성화
- [x] 스키마(테이블) 생성
- [x] 기존 로컬 데이터 마이그레이션

### Phase B — Next.js 프론트엔드 구축
- [x] `npx create-next-app@latest frontend` 생성 (휴대용 Node.js 사용)
- [x] 여행 조건 입력 페이지 구현 (트렌디한 다크모드 UI)
- [x] 일정 추천 결과 페이지 구현 (탭 및 지도 컨테이너 포함)
- [x] FastAPI 백엔드 연결 (로컬 연동 테스트 완료)

### Phase C — Render.com FastAPI 배포
- [x] `Dockerfile` 또는 [requirements.txt](file:///c:/projects/pick-and-go/requirements.txt) 준비
- [x] Render 프로젝트 생성 + GitHub 연결
- [x] Supabase DATABASE_URL 환경변수 설정
- [x] FastAPI 배포 완료

### Phase D — Vercel Next.js 배포
- [ ] GitHub에 frontend 폴더 푸시
- [ ] Vercel 프로젝트 import
- [ ] 환경변수 설정 (Render API URL 등)
- [ ] 배포 완료 → 공개 URL 확보

---

## 주요 설계 결정

### 백엔드 API 처리 방식
Vercel은 **Python 서버리스 함수**를 지원합니다.
기존 [travel_logic.py](file:///c:/projects/pick-and-go/travel_logic.py) / [backend_postgres.py](file:///c:/projects/pick-and-go/backend_postgres.py) 코드를 **거의 그대로** 재활용 가능.

```
frontend/
├── app/               ← Next.js 페이지
│   ├── page.tsx       ← 여행 조건 입력
│   └── result/
│       └── page.tsx   ← 일정 결과
├── api/               ← Python 서버리스
│   └── generate.py    ← travel_logic 호출
└── public/
```

### DB 연결
Supabase 제공 PostgreSQL URL을 `.env.local`에 넣으면 기존 SQLAlchemy 코드 그대로 작동.
```
DATABASE_URL=postgresql://postgres:...@db.xxxx.supabase.co:5432/postgres
```

---

## 검증 계획
1. 로컬에서 `npm run dev` 로 Next.js UI 확인
2. Supabase에 데이터 저장/조회 테스트
3. Vercel 배포 후 공개 URL에서 동작 확인
