# Pick&Go 코드 리서치 파일 (2026-04-13 최신 기준)

> 비전공자도 이해할 수 있도록 각 단계를 설명합니다.
> 베이지안 점수, 별점 분포 보너스 등 최신 변경사항 모두 반영.

---

## 📁 프로젝트 디렉토리 구조

```
pick&go/
├── app/
│   ├── main.py              ← FastAPI 서버 진입점. API 엔드포인트 정의
│   └── models.py            ← 요청/응답 데이터 형식 정의 (Pydantic)
│
├── db/
│   └── models.py            ← PostgreSQL 테이블 구조 정의 (SQLAlchemy ORM)
│
├── travel_logic/
│   ├── __init__.py          ← generate_plans(), update_db() 외부 인터페이스 노출
│   ├── itinerary_generator.py ← 일정 생성 핵심 로직 (메인 엔진)
│   ├── config/
│   │   ├── constants.py     ← 모든 수치 상수 정의 (점수, 카테고리, 경고 기준 등)
│   │   ├── settings.py      ← 기타 기본 설정값
│   │   └── __init__.py      ← config 패키지 외부 export 목록
│   ├── domain/
│   │   └── validators.py    ← check_is_domestic() 등 도메인 검증 함수
│   ├── services/
│   │   ├── scoring_service.py    ← 점수 계산, 필터링 (핵심 알고리즘)
│   │   ├── db_service.py         ← 데이터 수집 트리거 & 자동 업데이트
│   │   ├── distance_service.py   ← 이동거리/시간 계산 (Haversine + API)
│   │   └── optimization_service.py ← Epsilon-Greedy + Cost 기반 장소 선택
│   └── strategies/
│       ├── core_strategy.py      ← ✨ 핵심 코스 전략
│       ├── foodie_strategy.py    ← 🍽️ 식도락 & 힐링 전략
│       ├── nature_strategy.py    ← 🌿 자연 & 관광 전략
│       └── active_strategy.py   ← 🔥 액티브 & 핫플 전략
│
├── backend_postgres.py      ← DB 연결, 장소 조회/수집, 이동시간 API 호출
├── run_migration.py         ← 수동 DB 마이그레이션 스크립트
│
└── frontend/
    └── src/app/
        ├── page.tsx         ← 여행 조건 입력 화면 (프론트엔드 메인)
        └── result/page.tsx  ← 결과 표시 화면 (일정 카드 + 지도 + 경고 배지)
```

---

## ⚙️ Step 0 — 서버 시작 시 초기화 (`app/main.py`)

서버가 켜질 때 **딱 1번** 자동으로 실행되는 코드입니다.

```python
@app.on_event("startup")
def startup_event():
    # 신규 컬럼이 없으면 자동으로 추가 (IF NOT EXISTS — 기존 데이터 삭제 없음)
    _migration_sqls = [
        "ALTER TABLE places ADD COLUMN IF NOT EXISTS sub_category  VARCHAR(100);",
        "ALTER TABLE places ADD COLUMN IF NOT EXISTS review_count  INTEGER DEFAULT 0;",
        "ALTER TABLE places ADD COLUMN IF NOT EXISTS verified_at   TIMESTAMP;",
        "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_5star  INTEGER DEFAULT 0;",
        "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_4star  INTEGER DEFAULT 0;",
        "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_3star  INTEGER DEFAULT 0;",
        "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_2star  INTEGER DEFAULT 0;",
        "ALTER TABLE places ADD COLUMN IF NOT EXISTS rating_1star  INTEGER DEFAULT 0;",
        ...
    ]
```

**왜 필요한가?**
- `run_migration.py`를 수동으로 실행하지 않아도 서버가 켜질 때마다
  새로운 DB 컬럼이 자동 생성됨.
- `IF NOT EXISTS` 덕분에 이미 컬럼이 있어도 오류 없이 건너뜀.

### API 엔드포인트 3개

| 엔드포인트 | 역할 |
|-----------|------|
| `POST /api/v1/generate` | 여행 일정 생성 (핵심 API) |
| `POST /api/v1/update-db` | 장소 데이터 백그라운드 수집 |
| `POST /api/v1/reservation` | 예약 확정 (현재 더미 구현) |

---

## 🗄️ DB 테이블 구조 (`db/models.py`)

### places 테이블 — 장소 정보

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | String(100) PK | `"google_abc123"` 형태의 고유 ID |
| `source` | String(50) | 수집 출처: `"google"` 또는 `"kakao"` |
| `name` | String(200) | 장소 이름 |
| `city` | String(100) | 도시명 |
| `category` | String(100) | 대분류: `"음식점"`, `"카페/디저트"`, `"명소/관광"`, `"숙소"` |
| `sub_category` | String(100) | 세부분류: `"한식"`, `"자연경관"`, `"커피전문점"` 등 20종 |
| `location` | Geography(POINT) | PostGIS 지리 좌표 (위도·경도 통합 저장) |
| `address` | Text | 주소 |
| `rating` | DECIMAL(2,1) | 평점 0.0 ~ 5.0 (Kakao는 항상 0.0) |
| `review_count` | Integer | 전체 리뷰 수 (베이지안 점수 계산에 사용) |
| `rating_5star` | Integer | 5점 리뷰 누적 샘플 수 ← **신규** |
| `rating_4star` | Integer | 4점 리뷰 누적 샘플 수 ← **신규** |
| `rating_3star` | Integer | 3점 리뷰 누적 샘플 수 ← **신규** |
| `rating_2star` | Integer | 2점 리뷰 누적 샘플 수 ← **신규** |
| `rating_1star` | Integer | 1점 리뷰 누적 샘플 수 ← **신규** |
| `img_url` | Text | 이미지 URL (Google Photos 링크) |
| `description` | Text | 장소 설명 (types 기반 자동 생성) |
| `verified_at` | TIMESTAMP | 마지막 영업 확인 시각 (NULL = 미확인) |
| `updated_at` | TIMESTAMP | 마지막 DB 업데이트 시각 |
| `created_at` | TIMESTAMP | 최초 수집 시각 |

> **별점 분포 컬럼의 특징**:
> Google Place Details API는 상위 5개 리뷰만 제공하므로, 수집할 때마다 해당 5개의 별점을 **누적(+)** 방식으로 쌓습니다.
> 수집 횟수가 많아질수록 더 신뢰할 수 있는 경향을 파악할 수 있습니다.

---

## 📥 Step 1 — 데이터 수집 (`backend_postgres.py`)

### 1-1. 데이터 존재 확인 (`DBService.ensure_data_exists`)

```python
# 해당 도시 데이터가 DB에 없으면 자동 수집
places = backend.get_places(city)
if not places:
    DBService.update_db(city, styles)  # 수집 실행
```

### 1-2. Google Places 수집 (`fetch_google`)

수집 흐름:
```
① Text Search API 호출 (키워드당 최대 20개 장소 반환)
       ↓
② 각 장소의 types → sub_category 매핑
     "restaurant" → "음식점"
     "cafe"       → "커피전문점"
     "lodging"    → "호텔" 등
       ↓
③ Place Details API 호출 (place_id로 상위 5개 리뷰 조회) ← 신규
     → 각 리뷰의 별점(1~5) 집계 → rating_Xstar 계산
       ↓
④ _upsert_place()로 DB 저장/갱신
     기존 장소: review_count는 더 큰 값 유지, rating_Xstar는 누적(+)
     신규 장소: 모든 필드 INSERT
```

**수집되는 필드 (장소 단위)**:
- `user_ratings_total` → `review_count` (전체 리뷰 수)
- `rating` → `rating` (평균 평점 0~5)
- `reviews[].rating` → `rating_5star ~ rating_1star` (별점별 샘플 수)

### 1-3. Kakao Local 수집 (`fetch_kakao`)

```
① Kakao 키워드 검색 API 호출
       ↓
② category_group_code → (category, sub_category) 매핑
     'FD6' → ("음식점",    "음식점")
     'CE7' → ("카페/디저트","커피전문점")
     'AT4' → ("명소/관광",  "랜드마크")
     'CT1' → ("명소/관광",  "미술/박물관")
     'AD5' → ("숙소",       "호텔")
       ↓
③ _upsert_place()로 DB 저장
     ※ Kakao는 review_count 제공 안 함 → 0으로 저장
     ※ review_count는 max() 유지로 Google 수집분 보호
```

### 1-4. `_upsert_place()` 상세 동작

```python
def _upsert_place(session, place_data):
    existing = session.query(Place).filter(Place.id == place_data['id']).first()

    if existing:  # 이미 있는 장소: 갱신
        existing.rating       = place_data['rating']           # 평점 업데이트
        existing.review_count = max(기존값, 새값)               # 더 큰 값 유지
        existing.rating_5star += place_data['rating_5star']    # 누적 +
        existing.rating_4star += place_data['rating_4star']    # 누적 +
        # ... 나머지 별점도 동일
        existing.verified_at  = 지금                           # 수집 = 확인 완료

    else:  # 신규 장소: 삽입
        Place(id, source, name, city, ..., rating_5star, ..., verified_at=지금)
```

### 1-5. `get_places()` — DB에서 장소 조회

```python
def get_places(city, category_filter=None, limit=200):
    # PostGIS 쿼리로 좌표(lat, lng)를 한 번에 추출 (N+1 쿼리 방지)
    query = session.query(
        Place,
        ST_X(Place.location).label('lng'),
        ST_Y(Place.location).label('lat')
    ).filter(Place.city.contains(city))
    .order_by(Place.rating.desc())
    .limit(200)  # 기본 200개 (충분한 카테고리 풀 확보)
```

반환 딕셔너리에 포함된 필드:
- `rating`, `review_count`, `rating_5star ~ rating_1star` (점수 계산용)
- `verified_at`, `days_since_verified` (영업 경고용)
- `updated_at`, `days_since_updated` (최신성 보정용)
- `sub_category` (세부 카테고리 분류용)
- `source` (Kakao 면제 판단용)

---

## 🔍 Step 2 — Phase 1: 필터링 & 점수화 (`scoring_service.py`)

### 2-1. `hard_filter()` — 필수 조건 필터

첫 번째 단계: 아예 자격이 없는 장소를 **즉시 제거**합니다.

```python
for p in places:
    # 조건 1: 좌표가 0.0 or 없음 → 제거 (지도에 표시 불가)
    if lat == 0.0 or lng == 0.0: continue

    # 조건 2: 예산 수준별 최소 평점 미달 → 제거
    #   예산 "저" → 평점 2.0 미만 제거
    #   예산 "중" → 평점 3.0 미만 제거
    #   예산 "고" → 평점 4.0 미만 제거
    # 예외 1: 숙소·식당은 1점 완화 (필수 요소이므로)
    # 예외 2: Kakao 장소는 rating=0 → 면제 (API 미제공)
    if not is_kakao_no_rating and rating < effective_min: continue

    # 조건 3: 배리어프리 / 유모차 가능
    # → 현재 TourAPI 연동 전이라 미작동 (TODO)
```

사용 상수: `BUDGET_MIN_RATING`, `HOTEL_CATEGORIES`

### 2-2. `calculate_score()` — v3 베이지안 복합 점수 ← **핵심 변경**

점수는 아래 7개 요소를 합산하여 계산합니다.

#### ① 베이지안 기본 점수 (최대 75점)

```
이전 v2: score = 평점 × 15  (리뷰 1개든 10000개든 동일한 가중치)

현재 v3: bayesian_rating = (C × 3.5 + n × 평점) / (C + n)
          score           = bayesian_rating × 15

          C = 50 (기준 리뷰 수)
          n = 실제 리뷰 수

예시:
  평점 5.0, 리뷰   2개 → (50×3.5 + 2×5.0)/52  × 15 = 54.8점  ← 리뷰 부족 → 할인
  평점 5.0, 리뷰 200개 → (50×3.5 + 200×5.0)/250 × 15 = 70.5점  ← 신뢰도 높아 반영
  평점 4.0, 리뷰 500개 → (50×3.5 + 500×4.0)/550 × 15 = 59.3점
```

**원리**: 리뷰가 적은 장소는 글로벌 평균(3.5점)으로 끌어당겨 과신을 방지합니다.
리뷰가 많아질수록 실제 평점에 수렴합니다.

#### ② 별점 분포 보너스 (-5 ~ +5점) ← **신규**

```python
total = rating_5star + rating_4star + rating_3star + rating_2star + rating_1star
positive_ratio = (5★ + 4★) / total  # 긍정 비율
negative_ratio = (1★ + 2★) / total  # 부정 비율

# 판정 (부정 체크 우선)
if   negative_ratio >= 0.35: return -5   # 불만 심각
elif negative_ratio >= 0.20: return -2   # 불만 있음
elif positive_ratio >= 0.90: return +5   # 거의 모두 만족
elif positive_ratio >= 0.75: return +3
elif positive_ratio >= 0.60: return +1
else:                         return  0   # 보통
# 분포 데이터 없으면(모두 0) → 0점 (영향 없음)
```

**원리**: 같은 평점이라도 방문객 중 얼마나 많은 비율이 만족했는지를 구분합니다.
"평점 4.0인데 1★이 40%"인 장소는 패널티를 받습니다.

#### ③ 데이터 최신성 보정 (-5 ~ 0점)

```python
# updated_at 기준 경과일
days_since > 730일 (2년) → -5점   # 폐업 고위험
days_since > 365일 (1년) → -3점
days_since > 180일 (6개월) → -1점
이내                     →  0점
```

#### ④ 스타일 매칭 보너스 (+25점)

사용자가 선택한 취향(맛집, 관광, 자연 등)과
장소의 카테고리·이름·sub_category 키워드가 일치하면 +25점.

```python
style_keywords = {
    "맛집":    ["restaurant", "food", "식당", "음식점", ...],
    "자연":    ["nature", "mountain", "산", "숲", ...],
    "카페투어": ["cafe", "coffee", "카페", "커피", ...],
    ...
}
```

#### ⑤ 포토스팟 보너스 (+15점)

```python
if user_data.get('photo_spot', False):
    # 전망대, 타워, 뷰 명소 키워드 매칭 시 +15점
```

#### ⑥ 아이 동반 가족 친화 보너스 (+20점)

```python
if user_data.get('with_kids', False):
    # 동물원, 수족관, 공원, 가족 키워드 → +20점
```

#### ⑦ 성인 전용 패널티 (-50점)

```python
if user_data.get('with_kids', False):
    # 술집, 이자카야, bar, club, night → -50점
    # ADULT_ONLY_KEYWORDS 상수 사용
```

**최종 점수**: `min(100, max(0, int(베이지안 + 분포 + 최신성 + 스타일 + ...)))`

### 2-3. `categorize_visits()` — 장소 분류

```python
# 1순위: sub_category → SUB_CATEGORY_MAP 직접 매핑
"한식"     → foods
"커피전문점" → cafes
"자연경관"  → sights

# 2순위: category + name 키워드 → CATEGORY_KEYWORD_MAP fallback
"카페" 포함 → cafes
"식당" 포함 → foods
그 외       → sights
```

### 2-4. `extract_top_n()` — 후보 풀 크기 제한

```python
n = 여행일수 × 5  # CANDIDATE_POOL_RATIO = 5
# 5박6일 → 상위 30개만 추출
```

이미 score 내림차순 정렬된 상태에서 상위 N개를 선택합니다.

---

## 🗺️ Step 3 — 일정 생성 (`itinerary_generator.py`)

### 3-1. 테마 결정 (`_build_themes`)

사용자 입력을 분석해 2~4개 테마를 동적으로 선정합니다.

```python
테마 후보:
  ✨ 핵심 코스           → 항상 포함 (always=True)
  🍽️ 식도락 & 힐링      → 맛집·휴양 스타일 or 여유 페이스 or 커플·가족 동반
  🌿 자연 & 관광         → 자연·관광·문화 스타일 선택 시
  🔥 액티브 & 핫플       → 액티비티·쇼핑 스타일 or 빡빡 페이스 or 친구
```

최소 2개 보장: 조건 미충족 시 fallback 테마 추가.

### 3-2. 전략별 장소 배분 (Strategy Pattern)

| 전략 | 관광 | 식사 | 카페 | 특징 |
|------|------|------|------|------|
| CoreStrategy | 2 | 2 | 1 | 균형 잡힌 기본 코스 |
| FoodieStrategy | 1 | 3 | 1 | 식사 비중 최대화 |
| NatureStrategy | 3 | 2 | 1 | 관광지 중심 |
| ActiveStrategy | 3 | 2 | 1 | 활동적인 동선 |

### 3-3. 일일 스케줄 생성 (`_create_daily_schedule`)

하루 타임라인 슬롯을 랜덤 샘플링합니다.

```python
관광 슬롯: 10:30, 14:30, 16:30, 17:00 중 num_sights개
식사 슬롯: 12:00, 18:00 중 num_foods개
카페 슬롯: 15:30 (num_cafes개)
→ 시간 순 정렬
```

### 3-4. 장소 선택 최적화 (`OptimizationService`)

각 슬롯에서 다음 장소를 선택할 때 두 가지 방식 중 하나를 사용합니다.

```python
# Epsilon-Greedy 알고리즘
if random() < epsilon:
    # 탐험(Explore): 랜덤 선택 (epsilon 확률)
    # → 다양성 확보, 같은 결과 반복 방지
    return random.choice(candidates)
else:
    # 활용(Exploit): 최적 선택 (1-epsilon 확률)
    # → 현재 위치에서 거리순 상위 10개 → Kakao/Google API로 실제 이동시간 조회
    # → Cost 함수로 최적 장소 선택
    Cost = W_time × 이동시간 + W_score × (100 - 장소점수)
    return 가장 Cost가 낮은 장소
```

**Cost 함수 의미**:
- 이동시간이 짧고(분자 작음) 점수가 높을수록(100-score 작음) Cost가 낮음
- W_time, W_score 가중치로 테마별 우선순위를 다르게 설정
- 예: 🍽️식도락 테마는 W_score가 높아 → 이동시간보다 평점 우선

### 3-5. 이동시간 조회 (`DistanceService`)

```python
국내 여행:
  get_real_duration_kakao()  ← Kakao Mobility API (timeout=2초)
  → DB MovementCache에 저장 → 재요청 시 캐시 사용

해외 여행:
  get_real_duration_google_bulk()  ← Google Directions API
  → 병렬 처리 (ThreadPoolExecutor, max_workers=5)
  → DB MovementCache에 저장
```

**Haversine 거리 계산**: 상위 10개 후보 선별 시 직선 거리로 먼저 필터링.
API 호출 횟수를 줄이기 위한 사전 최적화.

### 3-6. `_make_place()` — 일정 항목 생성

DB 장소 정보를 프론트엔드용 일정 항목으로 변환합니다.

```python
return {
    "time":              "10:30",           # 방문 시작 시간
    "type":              "관광",             # 장소 유형 이름
    "name":              장소명(번역),        # 한국어 번역
    "desc":              "음식점 | 주소",      # 설명
    "lat":  33.45, "lng": 126.48,           # 좌표
    "raw_score":         78,                # 계산된 점수
    "staleness_warning": "caution",         # 영업 경고 (none/caution/danger)
    "sub_category":      "한식",             # 세부 카테고리
}
```

**`staleness_warning` 판단 로직**:
```python
if days_since_verified is None:            → 'danger'  (이력 없음 = 고위험)
elif days_since_verified >= 365일:          → 'danger'  (1년 이상 = 🔴)
elif days_since_verified >= 180일:          → 'caution' (6개월 이상 = 🟡)
else:                                       → 'none'    (정상)
# 숙소·공항은 항상 'none' (시스템 포인트)
```

---

## 📊 Step 4 — 테마 점수 계산 (`_calc_theme_score`)

생성된 일정 전체를 평가하여 **테마 대표 점수(60~99)**를 계산합니다.

```python
# 1. 일정 내 모든 장소의 raw_score 평균
base_score = sum(raw_scores) / len(raw_scores)

# 2. 사용자 취향과 테마 일치 보정
🍽️ 식도락 × 맛집·휴양 취향 → +5점
🌿 자연·관광 × 자연·문화 취향 → +5점
🔥 액티브 × 액티비티·쇼핑 취향 → +5점
고예산 → +2점

# 3. 클램핑
return max(60, min(99, int(final)))
```

---

## 🖥️ Step 5 — 프론트엔드 (`result/page.tsx`)

### 영업 경고 배지 표시

```tsx
{place.staleness_warning === 'danger' && (
  <span title="방문 전 영업 여부를 반드시 확인하세요.">
    🔴 영업 확인 필요
  </span>
)}
{place.staleness_warning === 'caution' && (
  <span title="정보가 6개월 이상 갱신되지 않았습니다.">
    🟡 정보 확인 권장
  </span>
)}
```

### 배리어프리 필터 (`page.tsx`)

```tsx
// 현재 상태: UI에는 표시되지만 실제 필터링 미작동
// TourAPI 연동 완료 후 백엔드 hard_filter()에서 활성화 예정
// 현재 사용자에게는 "준비중" 안내 표시
```

---

## 🔗 데이터 흐름 요약

```
[사용자 입력]
  도시, 날짜, 테마, 동행자, 예산, 이동수단, 스타일 선택
       ↓
[DBService.ensure_data_exists()]
  DB에 해당 도시 장소 없으면 → fetch_google() + fetch_kakao() 실행
       ↓
[backend.get_places(city, limit=200)]
  DB에서 장소 최대 200개 조회
  포함 필드: rating, review_count, rating_5star~1star, verified_at, sub_category
       ↓
[ScoringService.hard_filter()]
  좌표 0.0 제거 / 예산별 최소평점 미달 제거
  (Kakao rating=0 면제 / 숙소·식당 1점 완화)
       ↓
[ScoringService.calculate_score()]  ← v3 베이지안 + 분포 보너스
  ① 베이지안 기본점수: (C×3.5 + n×rating)/(C+n) × 15  max 75점
  ② 별점분포 보너스: 긍정/부정 비율                   -5~+5점
  ③ 최신성 보정: updated_at 경과일                    -5~0점
  ④ 스타일 매칭: 취향 키워드 일치                      +25점
  ⑤⑥⑦ 포토·가족·성인 보너스/패널티
  → min(100, max(0, 합계))
       ↓
[score 내림차순 정렬]
       ↓
[_categorize_places()]
  숙소 풀 분리 (HOTEL_CATEGORIES 기준 + min_hotel_rating)
  방문 후보 극 extract_top_n (일수 × 5개)
  → categorize_visits: sights / foods / cafes
       ↓
[테마 결정 _build_themes()]
  사용자 스타일·페이스·동반자 기반으로 2~4개 테마 선정
       ↓
[_generate_for_theme() × 테마 수]
  전략별 장소 배분 (sights/foods/cafes 개수 결정)
  일일 스케줄 생성 (시간 슬롯 랜덤 샘플링)
  장소 선택 (Epsilon-Greedy + Cost 최적화)
  이동시간 계산 (Kakao/Google API → MovementCache)
  staleness_warning 판단
       ↓
[_calc_theme_score()]
  raw_score 평균 + 취향-테마 일치 보정 → 60~99점
       ↓
[최종 응답 JSON]
  plans[{ theme, score, tags, days[{ day, places[...] }] }]
       ↓
[프론트엔드]
  결과 카드 + 🟡🔴 경고 배지 표시
```

---

## ⚠️ 현재 미완성 기능

| 기능 | 상태 | 이유 |
|------|------|------|
| 배리어프리 / 유모차 필터 | UI만 있음, 필터링 미작동 | TourAPI 연동 필요 |
| 지도 연동 | UI 자리만 있음 | Google Maps / Kakao Maps 연동 대기 |
| 예약 API | 더미 구현 | 실제 예약 시스템 미연결 |
| 별점 분포 집계 | 수집 중 | Google API 상위 5개 리뷰만 제공, 누적 중 |

---

## 📌 점수 설계 상수 요약 (`constants.py`)

```python
# 베이지안 점수 공식 상수
BAYESIAN_C                = 50    # 기준 리뷰 수 (이보다 적으면 글로벌 평균으로 당김)
BAYESIAN_GLOBAL_AVG       = 3.5   # 전체 장소 추정 평균 평점
BAYESIAN_SCORE_MULTIPLIER = 15    # 베이지안 평점 × 15 → 최대 75점

# 별점 분포 기준
RATING_DIST_POSITIVE_TIERS = [(0.90, +5), (0.75, +3), (0.60, +1)]
RATING_DIST_NEGATIVE_TIERS = [(0.35, -5), (0.20, -2)]

# 데이터 최신성 감점
DATA_FRESHNESS_PENALTY = [(730, -5), (365, -3), (180, -1), (0, 0)]

# 영업 경고 기준
PLACE_STALE_WARNING_DAYS   = 180  # 6개월 → 🟡 주의
PLACE_STALE_HIGH_RISK_DAYS = 365  # 1년   → 🔴 고위험
```
