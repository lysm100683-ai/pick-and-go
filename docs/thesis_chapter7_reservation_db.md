# 제 7 장 예약 데이터베이스 스키마 설계

본 장에서는 앞선 제6장에서 제안한 Saga 패턴 기반 5단계 예약 파이프라인의 트랜잭션 상태를 안정적으로 추적하고, 부분 실패 시 보상 트랜잭션을 트리거할 수 있는 근거 데이터를 마련하기 위해 설계된 **예약부 데이터베이스 스키마(Reservation DB Schema)** 아키텍처를 기술한다.

---

## 7.1 분산 환경을 위한 스키마 설계 요구사항

외부 항공(Amadeus) 및 숙소(Booking.com) API와 연동되는 Pick & Go의 예약 시스템은 단일 로컬 DB에서 모든 정합성을 보장받을 수 없다. 따라서 데이터베이스는 파이프라인 상의 미완료 트랜잭션과 에러 내역을 추적하는 '상태 머신(State Machine)'의 역할을 겸해야 하며, 이를 위해 다음과 같은 설계 원칙을 수립하였다.

1. **글로벌 식별자(UUID) 채택**: 마이크로서비스 간의 통신과 고동시성 예약 요청 환경에서 Primary Key(PK) 충돌을 원천 차단하기 위해, 기존의 순차 증가형 정수(Integer Auto-increment) 대신 `gen_random_uuid()` 함수를 통한 **UUID v4(Universally Unique Identifier version 4, 완전 난수 기반 범용 고유 식별자)**를 전면 도입하였다.
2. **Saga 상태(Status) 추적**: 마스터 테이블과 하위 상세 테이블 모두 `pending`(대기), `confirmed`(확정), `failed`(실패), `cancelled`(보상 트랜잭션 완료) 등의 명시적 상태값을 가지며, 인덱스를 부여하여 롤백이 필요한 대상을 빠르게 식별하도록 하였다.
3. **가변적 외부 데이터 수용 (JSONB)**: 외부 API 벤더사마다 반환하는 예약 상세 스펙(항공편 터미널, 숙박 옵션 등)이 상이하므로, 유연한 확장을 위해 PostgreSQL의 고성능 `JSONB` 데이터 타입을 활용하였다.

---

## 7.2 핵심 테이블 구조 및 역할 정의 (DDL)

전체 예약 스키마는 마스터-디테일 패턴과 이벤트 소싱(Event Sourcing) 패턴을 결합하여 총 3개의 핵심 테이블로 구성되었다.

### 1. `reservations` (마스터 예약 테이블)
사용자의 단일 '여행 일정(Itinerary)'에 종속된 전체 예약의 헤더(Header) 역할을 수행한다. 
- 총 결제 금액(`total_amount`), 동행 인원(`people`), 글로벌 예약 상태(`status`)를 관리한다.
- 사용자가 "내 예약 목록"을 조회할 때 최우선적으로 참조되며, `user_id`와 `status` 컬럼에 복합 인덱스를 구성하여 조회 성능을 최적화했다.

### 2. `reservation_items` (상세 예약 항목 테이블)
마스터 예약 하위에 속하는 개별 예약 건(예: 1건의 항공권, 1건의 숙박권)을 저장하는 1:N 관계의 자식 테이블이다.
- **`item_type`**: `flight`, `hotel` 등 외부 벤더의 종류를 식별.
- **`partner_name` 및 `partner_booking_id`**: 보상 트랜잭션 발동 시 외부 API에 `CANCEL` 요청을 보내기 위해 반드시 필요한 외부 시스템 발급 예약 번호를 저장한다.
- 파이프라인의 Sub 2(병렬 예약) 단계에서 각 API 호출이 끝날 때마다 비동기적으로 상태가 업데이트된다.

### 3. `reservation_logs` (예약 처리 이력/감사 로그)
Saga 패턴에서 가장 중요한 무결성 검증 및 디버깅을 담당하는 감사 로그(Audit Log) 테이블이다.
- 파이프라인 Sub 1~5를 거치며 발생하는 모든 상태 변경(State Transition)과 외부 API의 응답 페이로드(`payload`)를 시계열로 누적 기록(`INSERT ONLY`)한다.
- 특정 예약이 중간에 실패하여 보상 트랜잭션(Sub 4 → Sub 2 역전파)이 발동할 경우, 시스템은 이 로그 테이블을 조회하여 **'어디까지 성공했는지(어떤 파트너의 예약을 취소해야 하는지)'**를 정확하게 판별한다.

---

## 7.3 마이그레이션 전략 (Alembic)

기존 단순 JSON 덤프 형태였던 구버전 스키마를 고도화된 3단계 관계형 테이블 구조로 안전하게 전환하기 위해 Python SQLAlchemy의 마이그레이션 툴인 **Alembic**을 활용하였다.

[코드 8] 예약부 데이터베이스 마이그레이션(DDL) 핵심 명세
```python
# 1. 예약 마스터 테이블
op.create_table(
    'reservations',
    sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
    sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
    sa.Column('trip_data', JSONB, nullable=False),
    # ...생략
)

# 2. 예약 상세 항목 테이블 (Foreign Key: CASCADE 설정)
op.create_table(
    'reservation_items',
    sa.Column('reservation_id', UUID(as_uuid=True), sa.ForeignKey('reservations.id', ondelete='CASCADE')),
    sa.Column('partner_booking_id', sa.String(200)),
    sa.Column('details', JSONB),
    # ...생략
)

# 3. 예약 감사 로그 (Event Sourcing)
op.create_table(
    'reservation_logs',
    sa.Column('action_type', sa.String(50), nullable=False),
    sa.Column('sub_system', sa.String(30)), # Sub1 ~ Sub5 명시
    sa.Column('payload', JSONB),
    # ...생략
)
```

이와 같이 1:N으로 정규화된 스키마 구조와, 구조화되지 않은 외부 API 응답을 `JSONB`로 유연하게 수용하는 NoSQL적 특성을 혼합한 **하이브리드 스키마 접근법**은 변경이 잦은 마이크로서비스 연동 환경에서 유지보수성과 트랜잭션 안정성을 동시에 달성하는 핵심 기반이 되었다.

---

**참고문헌** *(이 장에서 새로 인용된 문헌은 없으며, 제1~5장 참고문헌 참조)*
