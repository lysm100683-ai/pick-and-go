# 제 3 장 이동시간 캐시 데이터베이스 설계

본 장에서는 여행 일정 생성에 필요한 장소 간 이동 소요 시간을 효율적으로 관리하기 위해 설계한 이동시간 캐시(Movement Time Cache) 데이터베이스 구조를 기술한다. 테이블 스키마 설계(3.1절), TTL 정책(3.2절), 중복 저장 방지 구조(3.3절) 순으로 설명한다.

---

## 3.1 테이블 스키마 설계

### 설계 배경: SQLite → PostgreSQL + PostGIS 전환

초기에는 SQLite 기반으로 출발지·목적지 좌표를 `REAL` 타입으로 저장하고 수치 차이를 직접 비교하는 방식을 사용하였다. 그러나 데이터 규모가 증가하면서 두 가지 문제가 발생하였다.

- **정확도 문제**: 경도 1도의 실제 거리는 위도에 따라 달라지므로, 단순 수치 비교로는 지구 표면 거리를 정확히 판정할 수 없다.
- **성능 문제**: 전체 레코드를 순차 비교하는 풀 스캔(O(N))이 발생하여 데이터 증가에 따라 응답 시간이 급격히 늘어난다.

이를 해결하기 위해 PostgreSQL + PostGIS로 전환하고 `movement_cache` 테이블을 새롭게 설계하였다.

### movement_cache 테이블 컬럼 구성

**[표 7]** `movement_cache` 테이블 컬럼 구성 및 역할

| 컬럼명 | 타입 | 역할 |
|---|---|---|
| `id` | SERIAL PRIMARY KEY | 레코드 고유 식별자 |
| `origin` | geography(POINT, 4326) | 출발지 좌표 (WGS84 구면 좌표계) |
| `destination` | geography(POINT, 4326) | 목적지 좌표 (WGS84 구면 좌표계) |
| `mode` | VARCHAR(20) | 이동 수단 (`driving` / `transit` / `walking`) |
| `duration_seconds` | INTEGER | 이동 소요 시간 (초 단위) |
| `is_korea` | BOOLEAN | 국내 여행 여부 (API 선택 기준) |
| `created_at` | TIMESTAMP | 저장 시각 (TTL 만료 기준) |

본 시스템에서 이동시간은 단순히 출발지와 목적지 간의 직선거리가 아니라, 선택한 **이동 수단(`mode`)**과 **해당 지역(`is_korea`)**의 실제 교통 상황 및 지형을 반영한 실질 소요 시간이다. 예를 들어, 동일한 두 지점이라도 도보(`walking`)와 차량(`driving`)의 소요 시간은 크게 다르며, 국내의 경우 Kakao 모빌리티 API를, 해외의 경우 Google Maps API를 사용하므로 산출 로직이 분기된다. 이러한 제반 조건을 모두 포괄하기 위해 위와 같이 7개의 컬럼을 구성하였다.

특히 핵심이 되는 `origin`과 `destination` 컬럼에는 PostGIS의 `geography(POINT, 4326)` 타입을 적용하였다. 이는 평면 투영 기반의 Geometry 타입과 달리 WGS84(EPSG:4326) 구면 타원체 기준을 사용하여, 지구 곡률에 의한 고위도/저위도 간의 거리 왜곡 없이 전 세계 어디서나 정확한 미터 단위의 최단 거리(대권 거리) 연산을 지원한다.[3]

[코드 1] movement_cache 테이블 DDL 및 GiST 인덱스 생성
```sql
CREATE TABLE IF NOT EXISTS movement_cache (
    id               SERIAL PRIMARY KEY,
    origin           geography(POINT, 4326) NOT NULL,
    destination      geography(POINT, 4326) NOT NULL,
    mode             VARCHAR(20)  NOT NULL,
    duration_seconds INTEGER      NOT NULL,
    is_korea         BOOLEAN      DEFAULT TRUE,
    created_at       TIMESTAMP    DEFAULT now()
);

CREATE INDEX idx_movement_cache_origin
    ON movement_cache USING gist (origin);
CREATE INDEX idx_movement_cache_destination
    ON movement_cache USING gist (destination);
```

이와 더불어 테이블에 데이터가 누적됨에 따라 발생하는 탐색 성능 저하를 방지하기 위해, 두 공간 컬럼 각각에 GiST(Generalized Search Tree) 인덱스를 생성하였다.[1] 일반적인 B-Tree 인덱스가 1차원 데이터의 대소 비교에 특화된 반면, GiST 인덱스는 다차원 공간 객체를 경계 상자(Bounding Box) 형태의 트리 구조로 분할한다. 이를 통해 특정 반경 내의 좌표를 검색할 때, 반경과 겹치지 않는 거대한 노드 트리들을 탐색 초기 단계에서 통째로 잘라내어(Pruning) 전체 O(N)의 풀 스캔 탐색 비용을 O(log N) 수준으로 단축시킨다.

[그림 6]은 `movement_cache` 테이블의 `origin`과 `destination` 컬럼에 적용된 GiST 인덱스의 계층 구조를 나타낸 도식이다.

> **[그림 6]** `movement_cache` 테이블 공간 컬럼(`origin`, `destination`)에 적용된 GiST 인덱스의 내부 트리 구조
> *(각 컬럼에 USING gist로 연결된 인덱스가 Root Bounding Box → Child Bounding Box → Leaf POINT 구조로 트리를 형성)*

---

## 3.2 TTL(Time-To-Live) 정책 설계

캐시 시스템은 외부 API 호출 비용과 응답 지연을 획기적으로 줄여주는 반면, 저장된 데이터가 시간이 흐름에 따라 실제 현실과 괴리되는 **데이터 오염(Data Staleness)** 문제를 동반한다. 신규 도로 개통, 대중교통 노선 개편, 혹은 일방통행 지정 등의 교통 환경 변화로 인해 과거의 이동시간 기록은 현재 시점의 실제 소요 시간과 달라질 수 있다. 

이러한 문제를 방지하고 데이터의 신뢰성을 유지하기 위해 본 시스템은 **180일(약 6개월) 단위의 TTL 정책**을 적용하였다. 180일이라는 기준은 통상적인 항공사 스케줄 변경 주기(하계/동계) 및 국내 주요 교통망 데이터의 업데이트 주기를 종합적으로 고려하여 도출한 임계값이다. TTL 정책은 애플리케이션 레벨의 논리적 필터링과 DB 레벨의 물리적 삭제라는 두 단계로 엄격하게 관리된다.

**[표 8]** TTL 정책 구현 단계 및 기대 효과

| 단계 | 구현 방식 | 적용 시점 | 기대 효과 |
|---|---|---|---|
| **1단계: 조회 필터** | 쿼리에 `created_at >= NOW() - INTERVAL '180 days'` 조건 포함 | 캐시 탐색 시 매번 | 만료된 데이터의 사용자 노출 즉각 차단 (논리적 만료) |
| **2단계: 자동 청소** | `cleanup_old_movement_cache()` 호출로 180일 초과 레코드 DELETE | 신규 캐시 저장 직후 | 무한정 쌓이는 캐시 데이터 방지 및 디스크 공간 확보 |

1단계 조회 필터는 캐시를 읽어오는 쿼리 자체에 날짜 조건을 강제함으로써, 설령 DB 내에 오래된 레코드가 남아있더라도 애플리케이션 계층에서는 절대 사용되지 않도록 보장한다. 2단계 자동 청소는 백그라운드 스케줄러(Cron)를 별도로 구축하는 대신, 새로운 캐시 데이터가 생성되는 트랜잭션의 후행 작업으로 동작하게 하여 시스템 아키텍처의 복잡도를 낮추면서도 스토리지의 비대화를 방지하도록 설계되었다.

[코드 2] SQLAlchemy를 이용한 TTL 만료 레코드 자동 청소 함수
```python
def cleanup_old_movement_cache(days: int = 180):
    """180일 초과 이동시간 캐시 레코드를 삭제하는 함수"""
    limit_date = datetime.now() - timedelta(days=days)
    with get_db_session() as session:
        session.query(MovementCache).filter(
            MovementCache.created_at < limit_date
        ).delete()
        session.commit()
```

---

## 3.3 중복 저장 방지 구조

여행 일정 생성 과정에서 사용자들이 주로 선호하는 유명 관광지나 숙소의 조합은 높은 빈도로 겹치게 된다. 따라서 동일한 출발지-목적지 경로에 대한 조회가 다발적으로 일어날 수 있다. 이때 데이터베이스에 동일 경로의 데이터가 중복으로 삽입되면 스토리지 낭비가 발생할 뿐만 아니라, 이후 캐시를 탐색할 때 옵티마이저의 인덱스 스캔 효율을 떨어뜨리는 원인이 된다. 

이를 근본적으로 차단하기 위해 본 시스템은 데이터베이스 삽입 전 항상 캐시 히트 여부를 검사하는 **조회 선행(Check-Then-Insert)** 패턴을 구현하였다.

1. **캐시 히트(Cache Hit)**: `get_movement_cache` 함수를 통해 유효한(TTL 이내의 반경 오차 허용) 캐시가 조회되면, 해당 데이터를 즉시 반환하며 외부 API 호출 및 DB 저장을 모두 생략한다.
2. **캐시 미스(Cache Miss)**: 캐시가 존재하지 않을 때에만 외부 지도 API(Google Maps/Kakao)를 호출하여 실제 이동 시간을 산출하고, 반환된 결과를 DB에 새롭게 삽입(`INSERT`)한다.

이 구조는 가장 비용이 많이 드는 네트워크 구간의 외부 API 호출을 최소화하는 핵심 로직으로 작용한다.

[코드 3] Check-Then-Insert 패턴 기반의 캐시 중복 방지 저장 로직
```python
# SQLAlchemy ORM 기반 캐시 저장 전 중복 확인
existing = get_movement_cache(origin, destination, mode, session)
if existing:
    return existing          # 기존 캐시 반환 (저장 생략)

new_cache = MovementCache(   # 신규 레코드 삽입
    origin=origin_point,
    destination=dest_point,
    mode=mode,
    duration_seconds=duration,
    is_korea=is_korea,
)
session.add(new_cache)
session.commit()
```

위 로직에서 ORM 모델 `MovementCache`는 SQLAlchemy[7]를 통해 Python 클래스로 매핑되며, `get_db_session()`은 커넥션 풀(Connection Pool) 기반으로 트랜잭션 세션을 안전하게 할당 및 회수하는 컨텍스트 매니저 역할을 수행한다. 이와 같은 방어적 설계는 다수의 사용자가 동시에 일정을 생성하는 환경에서도 시스템의 안정성과 응답성을 높은 수준으로 유지하는 기반이 된다.

---

**참고문헌** *(이 장에서 새로 인용된 문헌; [1]–[6]은 제1·2장 참고문헌 참조)*

[7] SQLAlchemy Authors, "SQLAlchemy 2.0 Documentation — ORM Querying Guide",
    SQLAlchemy Project, 2023.
    https://docs.sqlalchemy.org/en/20/orm/queryguide/
