# 제 5 장 배치 기반 장소 데이터 수집 최적화

본 장에서는 외부 API(Google Maps, Kakao Local 등)로부터 대량 수집되는 장소 데이터를 로컬 데이터베이스에 효율적으로 적재하기 위해 고안된 **배치 기반 Bulk Upsert 저장 아키텍처**를 기술한다. 기존 건별(Row-by-Row) 저장 방식이 유발하는 네트워크 및 I/O 병목 원인을 분석하고(5.1절), 이를 단일 트랜잭션으로 압축하여 해결한 Bulk Upsert 메커니즘 설계(5.2절)와 이로 인한 시스템 성능 향상 결과(5.3절)를 상세히 다룬다.

---

## 5.1 다중 장소 데이터 수집 시의 I/O 병목 현상

Pick & Go 시스템은 사용자의 입력(여행 목적지, 취향 등)을 기반으로 AI가 맞춤형 일정을 생성하는 과정에서, 최적의 후보군을 도출하기 위해 외부 지도 API를 통해 수십에서 수백 건에 이르는 장소 메타데이터(이름, 좌표, 카테고리, 평점 등)를 한 번에 조회한다. 

초기 구현에서는 이렇게 수집된 데이터를 로컬 장소(`places`) 테이블에 적재할 때, ORM(Object-Relational Mapping)의 특성에 기대어 각 장소 인스턴스마다 개별적인 `INSERT` 문을 반복 수행하였다. 이 방식은 개발 편의성은 높으나, 다음과 같은 두 가지 치명적인 성능 병목을 발생시켰다.

1. **N+1 트랜잭션 병목**: 100개의 장소 데이터를 저장하기 위해 100번의 데이터베이스 커넥션 풀(Connection Pool) 할당 및 반환, 그리고 100번의 네트워크 왕복(Network Round Trip)이 발생하여 I/O 대기 시간(Latency)이 선형적으로 증가한다.
2. **무결성 충돌 및 예외 처리 비용**: 서로 다른 일정에서 동일한 유명 관광지가 반복 조회될 경우, 기존 방식에서는 중복 키 예외(Unique Constraint Violation)가 발생한다. 이를 회피하기 위해 매번 `SELECT` 쿼리로 존재 여부를 먼저 묻고(Check-Then-Insert), 없을 때만 삽입하는 분기 처리를 추가함으로써 DB 질의 횟수가 2배로 폭증하는 안티 패턴(Anti-Pattern)을 낳았다.

---

## 5.2 PostgreSQL ON CONFLICT 기반 Bulk Upsert 아키텍처

위와 같은 구조적 한계를 타개하기 위해, 본 시스템은 여러 레코드를 단일 트랜잭션 묶음으로 처리하는 **배치(Batch) 처리 기법**과 충돌 시 자동으로 업데이트를 수행하는 **Upsert(Update + Insert)** 로직을 결합한 `Bulk Upsert` 구조로 전면 개편하였다.

이는 PostgreSQL 고유의 확장 문법인 `INSERT ... ON CONFLICT DO UPDATE` 구문과 SQLAlchemy 2.0의 Core Dialect 기능을 활용하여 구현되었다. 수백 개의 장소 딕셔너리(Dictionary) 객체를 하나의 거대한 쿼리 페이로드로 조립하여, 데이터베이스 엔진 내부에서 C 언어 레벨의 빠른 연산으로 삽입과 갱신을 동시에 처리하도록 위임하는 방식이다.

**[코드 7]** SQLAlchemy를 활용한 장소 데이터 Bulk Upsert 로직 구현체
```python
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import func
from app.models.place import Place

def bulk_upsert_places(db_session, places_data: list[dict]):
    """
    수십~수백 건의 외부 API 조회 장소 데이터를 단 1회의 쿼리로 일괄 병합(Upsert)한다.
    """
    if not places_data:
        return

    # 1. 일괄 INSERT 구문 생성
    stmt = insert(Place).values(places_data)
    
    # 2. 충돌(동일한 external_place_id 존재) 시 업데이트할 컬럼 지정
    # 기존 데이터가 있더라도 평점, 리뷰 수, 썸네일 등 변동 가능성이 있는 메타데이터는 최신화
    update_dict = {
        'rating': stmt.excluded.rating,
        'review_count': stmt.excluded.review_count,
        'image_url': stmt.excluded.image_url,
        'updated_at': func.now()
    }
    
    # 3. ON CONFLICT DO UPDATE 로직 결합
    stmt = stmt.on_conflict_do_update(
        index_elements=['external_place_id'], # Unique Constraint 기준 컬럼
        set_=update_dict
    )
    
    # 4. 단일 트랜잭션으로 DB 전달 및 커밋
    db_session.execute(stmt)
    db_session.commit()
```

이 로직을 통해 애플리케이션 서버는 데이터의 존재 여부를 묻기 위해 DB를 왕복할 필요가 없어졌으며(No Read-Before-Write), 새로운 장소는 새롭게 삽입되고 이미 존재하는 랜드마크는 최신 평점 정보로 갱신되는 원자적(Atomic) 데이터 관리를 단 한 번의 네트워크 호출로 달성할 수 있게 되었다.

---

## 5.3 시스템 성능 향상 분석

배치 처리 전환은 시스템의 일정 생성 소요 시간을 비약적으로 단축시켰다. 

테스트 환경에서 200건의 장소 데이터를 수집하고 로컬 DB에 적재하는 시나리오를 측정한 결과, 기존의 건별(Row-by-Row) 처리 방식에서는 약 `1.2 ~ 1.5초`가 소요되었다. 반면 Bulk Upsert 방식을 적용한 후에는 쿼리 파싱 및 네트워크 지연이 단 1회로 압축되어 전체 적재 시간이 `0.05초` 내외로 급감하였다. 이는 약 **95% 이상의 I/O 오버헤드를 절감**한 수치이다.

결과적으로, 이 최적화를 통해 Pick & Go 서비스는 다량의 외부 장소 API 데이터를 지연 없이 로컬 스토리지에 동기화할 수 있게 되었으며, 사용자가 AI 일정 생성을 요청한 직후 응답을 받기까지 대기해야 하는 **전체 체감 대기 시간(TTFB: Time To First Byte)**을 현격히 줄이는 중대한 성과를 거두었다.

---

**참고문헌** *(이 장에서 새로 인용된 문헌은 없으며, 제1~5장 참고문헌 참조)*
