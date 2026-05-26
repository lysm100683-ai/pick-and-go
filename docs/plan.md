# 🗺️ Pick&Go — 5-Phase 파이프라인 구현 계획서

> 📌 **이 문서의 목적**
> 현재 Pick&Go 알고리즘의 문제점을 분석하고, 설계 문서(처리부 설계.pdf)에 기반한
> 새로운 5단계 파이프라인으로 업그레이드하기 위한 **상세 구현 계획서**입니다.
>
> ⚠️ **구현은 이 계획서 검토 및 승인 후 진행합니다. 현재는 계획 단계입니다.**

---

## 0. 왜 바꿔야 하는가? (현재 vs 목표)

> 💡 **비개발자를 위한 설명**
> 현재 알고리즘은 마치 여행 처음 가는 사람이 지도도 없이
> "근처에서 가장 맛있어 보이는 곳"만 골라서 이동하는 방식입니다.
> 결과적으로 하루 동선이 지그재그가 되거나, 비슷한 날이 반복될 수 있습니다.
>
> 새 알고리즘은 전문 여행 플래너처럼 **하루치 지역을 먼저 묶고,
> 그 안에서 가장 효율적인 순서**를 계산합니다.

| 항목 | 현재 방식 (문제) | 목표 방식 (개선) |
|------|-----------------|-----------------|
| **장소 선별** | 좌표·평점 없는 곳만 제거 | 예산·배리어프리 등 필수 조건 먼저 걸러냄 |
| **일자별 배분** | 전체 장소 풀에서 무작위 추출 | 지리적으로 가까운 곳끼리 같은 날로 묶음 (K-Means) |
| **방문 순서** | 현재 위치에서 가장 가까운 곳만 선택 | 하루 전체 동선의 총 이동시간이 최소가 되도록 계산 (TSP) |
| **숙소 결정** | 사용자가 고른 숙소 수만큼 무작위 배정 | 이동시간 90분 초과 시, 중심점 근처로 자동 숙소 변경 |
| **시간표 생성** | 고정된 시간 슬롯에 랜덤 배치 | 이동시간+체류시간 누적 시뮬레이션 후 강도별 Cut-off, 밤11시 전 숙소 도착 또는 대중교통 이용 시 대중교통 막차 시간 고려하여 시간 설정하기 |
| **동행자 반영** | 어린이 동반만 부분 반영 | 부모님 동반 시 체류시간 ×1.2배, 경사 없는 장소 우대 |
| **공항 위치** | 제주공항으로 하드코딩 ❌ | 목적지 도시에 맞게 동적으로 조회 |
| **DB 업데이트** | 데이터 수집 함수가 없어서 미작동 ❌ | `fetch_google/kakao` 함수 완성 |

---

## 1. 새로운 5단계 파이프라인 전체 흐름

> 💡 **비개발자를 위한 설명**
> 사용자가 "일정 만들기"를 누르면, 서버 내부에서 아래 5단계가 순서대로 실행됩니다.
> 각 단계의 결과물이 다음 단계의 재료가 됩니다.
> 마치 공장의 컨베이어벨트처럼, 원재료(장소 데이터)가 5단계를 거쳐 완제품(일정)이 됩니다.

```
사용자 입력 (조건 데이터)
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ Phase 1: 필터링 & 점수화                                  │
│  "수백 개 장소 중 이 여행에 맞는 N개만 추립니다"            │
│  → 예산/배리어프리 조건 미충족 즉시 탈락                    │
│  → 취향 매칭 점수로 줄 세워서 상위 N개(여행일수×5) 추출     │
└──────────────────────┬──────────────────────────────────┘
                       │ 후보 장소 N개
                       ▼
┌─────────────────────────────────────────────────────────┐
│ Phase 2: 공간 클러스터링 (K-Means)                        │
│  "지리적으로 가까운 장소끼리 같은 날짜로 묶습니다"          │
│  → K = 여행 일수 (3박 4일이면 K=4)                        │
│  → 각 그룹의 지리적 중심점(Centroid)도 계산               │
└──────────────────────┬──────────────────────────────────┘
                       │ 일자별 장소 그룹 + 중심점
                       ▼
┌─────────────────────────────────────────────────────────┐
│ Phase 3: 1차 경로 최적화 (임시 TSP)                       │
│  "기존 숙소를 출발점으로, 각 날짜의 최적 방문 순서를 찾습니다"│
│  → 결과: 각 날짜의 '마지막 방문 장소' → Phase 4로 전달     │
└──────────────────────┬──────────────────────────────────┘
                       │ 일별 이동시간 + 마지막 장소
                       ▼
┌─────────────────────────────────────────────────────────┐
│ Phase 4: 숙소 앵커링 (숙소 위치 확정)                      │
│  "이동이 너무 오래 걸리는 날은 숙소를 그 근처로 이동합니다"  │
│  → 90분 초과 이동 발견 시: 해당 날 클러스터 중심 근처로 변경 │
│  → 모든 날 비슷하면: 여행 중간 날짜 마지막 장소 근처로 변경  │
└──────────────────────┬──────────────────────────────────┘
                       │ 확정된 일자별 숙소
                       ▼
┌─────────────────────────────────────────────────────────┐
│ Phase 5: 최종 경로 + 타임박싱                              │
│  "확정 숙소 기준으로 최종 경로 계산 + 시간표 생성"          │
│  → 체류시간+이동시간 누적 시뮬레이션                        │
│  → 강도별 방문 수 제한 (여유: 2곳, 보통: 2~3곳, 알차게: 3~4곳) │
│  → 부모님 동반: 체류시간 ×1.2 (더 천천히)                    │  
│  → 밤11시 전 숙소 도착 또는 대중교통 이용 시 대중교통 막차 시간 고려하여 시간 설정하기 
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
              최종 일정 JSON 반환
              (테마별 탭, 날짜별 시간표)
```

---

## 2. 새로 만들 파일 (3개)

---

### 📄 [NEW] `travel_logic/services/clustering_service.py`

> 💡 **이 파일이 하는 일 (비개발자 설명)**
> "제주도에 가볼 만한 20곳이 있다. 3박 4일 여행이니 하루치씩 4그룹으로 나눠라."
> 이 업무를 담당합니다. 지리적으로 가까운 장소들이 같은 날 배치되어
> 하루 이동 동선이 효율적으로 됩니다.
>
> **사용 알고리즘: K-Means 클러스터링**
> 지도 위에 점들(장소)을 K(=여행일수)개의 구역으로 나누는 수학적 방법.
> 예를 들어 제주도를 동쪽/서쪽/중앙으로 3구역으로 나누고,
> 각 구역에 있는 장소들이 같은 날짜에 배치됩니다.

```python
# clustering_service.py 핵심 구조

from sklearn.cluster import KMeans   # K-Means 알고리즘 라이브러리
import numpy as np

class ClusteringService:

    @staticmethod
    def cluster_by_day(places, num_days):
        """
        [입력] places: 후보 장소 리스트 (위도/경도 포함)
               num_days: 여행 일수 (= 만들 그룹 수 K)

        [처리] 각 장소의 위도/경도 좌표를 기준으로
               K-Means 알고리즘으로 num_days개 그룹으로 분류

        [출력] clusters: [[1일차 장소들], [2일차 장소들], ...]
               centroids: [(1일차 중심 위도, 경도), (2일차 중심 위도, 경도), ...]
               → centroids는 Phase 4 숙소 앵커링에서 "이 날 어디가 중심인가?" 에 사용
        """
        coords = np.array([[p['lat'], p['lng']] for p in places])
        km = KMeans(n_clusters=num_days, random_state=42, n_init=10)
        labels = km.fit_predict(coords)

        clusters = [[] for _ in range(num_days)]
        for place, label in zip(places, labels):
            clusters[label].append(place)

        centroids = [(km.cluster_centers_[i][0], km.cluster_centers_[i][1])
                     for i in range(num_days)]

        return clusters, centroids
```

**고려사항 & 트레이드오프:**

| 항목 | 내용 |
|------|------|
| 장점 | 지리적으로 가까운 장소끼리 묶여 하루 이동효율 극대화 |
| 단점 | 클러스터별 장소 수가 불균형할 수 있음 (한 날은 1개, 다른 날은 8개) |
| 대응 | 빈 클러스터 발생 시 가장 큰 클러스터에서 장소를 가져오는 보정 로직 포함 |
| 의존성 | `scikit-learn` 라이브러리 추가 필요 (`requirements.txt`에 추가) |
| 한계 | 위경도에 유클리드 거리 사용 → 국내 소규모 여행(200km 이내)에서는 오차 미미 |
* 이 부분 단점 보완 필요 -> 각 날짜별 장소가 최대한 균등하게 되어야 함(오차 1개~2개 범위 내)
---

### 📄 [NEW] `travel_logic/services/tsp_service.py`

> 💡 **이 파일이 하는 일 (비개발자 설명)**
> "오늘 방문할 장소 5곳이 있다. 어떤 순서로 다녀야 총 이동시간이 가장 짧을까?"
> 이 문제를 "외판원 순회 문제(TSP)"라고 합니다.
>
> **사용 방법: Nearest Neighbor 휴리스틱**
> 완벽한 최단 경로를 찾으려면 모든 경우의 수를 계산해야 하는데,
> 장소가 10개만 돼도 10! = 3,628,800가지라 너무 오래 걸립니다.
> 대신 "현재 위치에서 가장 가까운 곳으로 이동"을 반복하는
> 빠르고 실용적인 근사 방법을 씁니다. (최적 대비 최대 25% 오차)

```python
# tsp_service.py 핵심 구조

class TSPService:

    def __init__(self, distance_service):
        """
        [의존성 주입] DistanceService를 외부에서 받아 저장
        → TSPService는 이동시간 계산 방법을 직접 알 필요 없음
          DistanceService에게 묻기만 하면 됨 (책임 분리)

        [사용 방법] ItineraryGenerator.__init__에서:
            self.distance_service = DistanceService()
            self.tsp_service = TSPService(self.distance_service)  # ← 주입
        """
        self.distance_service = distance_service

    def solve(self, places, start_hotel, is_korea, travel_mode):
        """
        [입력] places: 오늘 방문할 장소 리스트
               start_hotel: 오늘의 출발/복귀 숙소
               is_korea: 국내여행 여부 (카카오API vs 구글API 선택)
               travel_mode: 'driving'(차량) or 'transit'(대중교통)

        [처리] Nearest Neighbor 알고리즘:
               1. 숙소에서 출발
               2. 아직 안 간 장소 중 이동시간 가장 짧은 곳으로 이동
               3. 방문 완료 표시
               4. 2-3 반복, 모든 장소 방문 완료
               5. 숙소로 복귀

        [출력] ordered_places: 방문 순서대로 정렬된 장소 리스트
               travel_times: 각 이동 구간의 소요시간(초) 리스트
               → [숙소→1번 장소, 1번→2번 장소, ..., 마지막→숙소]
        """
        unvisited = places[:]
        route = []
        travel_times = []
        current = start_hotel

        while unvisited:
            # 현재 위치에서 각 미방문 장소까지의 실제 이동시간 조회 (API or 캐시)
            times = self.distance_service.get_travel_times_bulk(
                current['lat'], current['lng'], unvisited, is_korea, travel_mode
            )
            # 이동시간이 가장 짧은 장소 선택
            times.sort(key=lambda x: x[0])
            best_time, best_place = times[0]

            route.append(best_place)
            travel_times.append(best_time)
            unvisited.remove(best_place)
            current = best_place

        return route, travel_times
```

**고려사항 & 트레이드오프:**

| 항목 | 내용 |
|------|------|
| 장점 | 현재 Epsilon-Greedy 대비 전체 동선 이동시간 줄어듦 |
| 정확도 | 최적 해 대비 최대 25% 오차 (실용적으로는 충분) |
| API 비용 | 장소 N개 시 각 단계마다 미방문 장소 개수만큼 API 호출 |
| 캐시 효과 | 이미 계산한 이동시간은 DB에 저장되어 재사용 → 반복 호출 시 비용 없음 |
| 확장 가능 | 향후 2-Opt 후처리로 추가 5~15% 개선 가능 |

---

### 📄 [NEW] `travel_logic/services/hotel_anchor_service.py`

> 💡 **이 파일이 하는 일 (비개발자 설명)**
> "3박 4일 여행인데, 3일차에 이동이 90분 넘게 걸리는 구간이 있다.
> 그러면 3일차 숙소를 그날 방문할 장소들의 중심 근처로 옮겨라."
> 이 판단과 새 숙소 탐색을 담당합니다.
>
> **두 가지 상황:**
> - 상황 A: 특정 날에 이동시간 90분 초과 구간 발견 → 그 날 기준으로 숙소 변경
> - 상황 B: 모든 날 이동시간이 비슷함 → 여행 중간 날짜 기준으로 숙소 변경

```python
# hotel_anchor_service.py 핵심 구조

TRAVEL_TIME_THRESHOLD = 90 * 60  # 90분 = 5400초 (임계치 상수)

class HotelAnchorService:

    @staticmethod
    def determine_hotels(num_hotels, base_hotel, num_days,
                         daily_travel_times, centroids,
                         last_places_per_day, hotel_candidates, user_data):
        """
        [입력]
          num_hotels: 사용자가 원하는 숙소 수 (1이면 고정)
          base_hotel: 기본 숙소 (사용자가 처음 정한 곳)
          daily_travel_times: [[1일차 각 구간 이동시간], [2일차...], ...]
          centroids: 각 날짜 방문 지역의 지리적 중심점
          last_places_per_day: Phase 3에서 각 날의 마지막 방문 장소

        [처리 분기]
          num_hotels == 1 → 기존 숙소 유지, 모든 박 동일 숙소
          num_hotels > 1 → 이동시간 분석 후 숙소 위치 최적화

        [출력] night_hotels: [1박 숙소, 2박 숙소, ..., (num_days-1)박 숙소]
        """
        # 변경 안 하는 경우
        if num_hotels <= 1:
            return [base_hotel] * (num_days - 1)

        # 90분 초과 날짜 탐색
        over_threshold_days = [
            i for i, times in enumerate(daily_travel_times)
            if any(t >= TRAVEL_TIME_THRESHOLD for t in times)
        ]

        night_hotels = [base_hotel] * (num_days - 1)

        if over_threshold_days:
            # 상황 A: 초과 날짜의 클러스터 중심 근처로 숙소 변경
            for day_idx in over_threshold_days:
                new_hotel = HotelAnchorService._find_nearest_hotel(
                    centroids[day_idx][0], centroids[day_idx][1],
                    hotel_candidates, user_data
                )
                if new_hotel and day_idx < num_days - 1:
                    night_hotels[day_idx] = new_hotel
        else:
            # 상황 B: 중간 날짜 마지막 장소 근처로 숙소 변경
            mid_idx = (num_days - 1) // 2
            last_place = last_places_per_day[mid_idx]
            if last_place:
                new_hotel = HotelAnchorService._find_nearest_hotel(
                    last_place['lat'], last_place['lng'],
                    hotel_candidates, user_data
                )
                if new_hotel:
                    for i in range(mid_idx, num_days - 1):
                        night_hotels[i] = new_hotel

        return night_hotels
```

**고려사항 & 트레이드오프:**

| 항목 | 내용 |
|------|------|
| 90분 기준 근거 | 설계 문서 기준. `HOTEL_ANCHOR_TIME_THRESHOLD` 상수로 분리되어 쉽게 변경 가능 |
| 숙소 없을 때 | PostGIS 반경 검색 → 폴백: 후보 풀 중 Haversine 거리 최소 → 최최종 폴백: 기존 숙소 유지 |
| 별점 조건 | 사용자 `star_rating` 조건 반영하여 필터링 |

---

## 3. 수정할 기존 파일 (5개)

---

### ✏️ [MODIFY] `travel_logic/services/scoring_service.py`

> 💡 **왜 수정하는가?**
> 현재는 좌표·평점이 없는 장소만 걸러냅니다.
> 새 버전에서는 **"예산 조건"과 "배리어프리 조건"을 먼저 엄격하게 걸러낸 뒤**
> 소프트 점수로 순위를 매깁니다.

**추가할 메서드 2개:**

```python
@staticmethod
def hard_filter(places, user_data):
    """
    [역할] 필수 조건 미충족 장소는 즉시 제거 (하드 필터)

    [필터 조건 1] 예산 수준별 최소 평점
      - 예산 "저" → 평점 2.0 미만 제거
      - 예산 "중" → 평점 3.0 미만 제거
      - 예산 "고" → 평점 4.0 미만 제거

    [필터 조건 2] 배리어프리 (stroller=True or barrier_free=True 시)
      - 카테고리/설명에 배리어프리 관련 태그가 없는 관광지 제거
      - 단, 식당·숙소는 통과 (음식을 먹고 자는 곳은 무조건 포함)

    ※ 현재 한계: DB에 배리어프리 태그 데이터가 없어서 필터 효과 제한적
                  TourAPI 데이터 수집 후 실효성 높아짐
    """
    ...

@staticmethod
def extract_top_n(places, num_days):
    """
    [역할] 상위 N개 장소만 후보로 확정
    [기준] N = 여행 일수 × 5
           (하루 평균 5곳 방문 가정 — 식사 2회, 카페 1회, 관광 2회)
    [예시] 3박 4일 → N = 20개 장소만 후보 사용
    """
    n = num_days * 5
    return places[:n]  # 이미 점수 내림차순 정렬된 상태
```

---

### ✏️ [MODIFY] `travel_logic/itinerary_generator.py`

> 💡 **왜 수정하는가? (가장 중요한 변경)**
> 현재의 "랜덤 셔플 + Greedy 선택" 방식을 버리고,
> **5-Phase 파이프라인으로 완전히 재작성**합니다.
> 마치 수동 계산기를 과학 계산기로 교체하는 것과 같습니다.

**새로운 `generate()` 함수 구조:**

```python
def generate(self, user_data, duration):
    """
    [전체 파이프라인 조율 함수]
    각 Phase 서비스를 순서대로 호출하고 결과를 다음 Phase로 전달.
    """

    # ── Phase 1: 필터링 & 점수화 ──────────────────────
    # "이 여행에 맞는 장소 N개를 골라서 점수 매기기"
    raw_places = backend.get_places(city)
    hard_filtered = self.scoring_service.hard_filter(raw_places, user_data)

    # ★ 숙소는 star_rating 조건만 적용, top_N 제한 없이 별도 풀로 관리
    #    이유: top_N(예: 20개) 안에 숙소가 0개일 수 있어 앵커링 불가 방지
    hotels = [
        p for p in hard_filtered
        if p['category'] in HOTEL_CATEGORIES
        and float(p.get('rating', 0)) >= user_data.get('star_rating', 3)
    ]

    # ★ 방문 장소(관광·식당·카페)만 점수 매기고 top_N 추출
    non_hotels = [p for p in hard_filtered if p not in hotels]
    scored = self._score_and_sort(non_hotels, user_data)
    candidate_pool = self.scoring_service.extract_top_n(scored, duration)
    sights, foods, cafes = self._categorize_visits(candidate_pool, user_data)

    base_hotel = hotels[0] if hotels else self._get_airport_place(user_data)
    visit_candidates = sights + foods + cafes  # 방문할 장소들

    # ── Phase 2: 공간 클러스터링 ──────────────────────
    # "지리적으로 가까운 것끼리 날짜별로 묶기"
    clusters, centroids = self.clustering_service.cluster_by_day(
        visit_candidates, duration
    )

    # ── Phase 3: 임시 TSP (1차 경로, 마지막 장소 추출) ──
    # "기존 숙소 기준의 임시 최적 경로 → 각 날의 마지막 장소 파악"
    daily_travel_times = []
    last_places_per_day = []
    for day_places in clusters:
        ordered, times = self.tsp_service.solve(
            day_places, base_hotel, is_korea, travel_mode
        )
        daily_travel_times.append(times)
        last_places_per_day.append(ordered[-1] if ordered else None)

    # ── Phase 4: 숙소 앵커링 ───────────────────────────
    # "이동시간 분석해서 숙소 위치 최적화"
    night_hotels = self.hotel_anchor_service.determine_hotels(
        num_hotels=user_data.get('num_hotels', 1),
        base_hotel=base_hotel,
        num_days=duration,
        daily_travel_times=daily_travel_times,
        centroids=centroids,
        last_places_per_day=last_places_per_day,
        hotel_candidates=hotels,
        user_data=user_data
    )

    # ── Phase 5: 최종 TSP + 타임박싱 ────────────────────
    # "확정된 숙소 기준으로 최종 경로 + 실제 시간표 생성"
    themes = self._build_themes(user_data, city)
    final_plans = []
    for theme in themes:
        days = self._phase5_timebox(
            clusters, night_hotels, base_hotel,
            is_korea, travel_mode, user_data, duration
        )
        final_plans.append({...})

    return final_plans
```

**Phase 5 타임박싱 핵심 로직:**

```python
def _phase5_timebox(self, clusters, night_hotels, base_hotel, ...):
    """
    [역할] 확정 숙소 기준 최종 TSP → 하루 시간표 생성

    [일정 강도별 하루 최대 방문 수]
    - "여유롭게" → 최대 2곳
    - "보통"     → 최대 2~3곳
    - "알차게"   → 최대 3~4곳

    [동행자별 체류시간 배율]
    - 부모님 동반 → 모든 장소 체류시간 × 1.2배 (더 편안하게)
    - 아이 동반   → × 1.3배
    - 기본        → × 1.0배

    [시간 누적 시뮬레이션]
    09:00 숙소 출발
    09:00 + 이동시간 = 첫 번째 장소 도착
    도착시간 + 체류시간 = 첫 번째 장소 출발
    출발시간 + 이동시간 = 두 번째 장소 도착
    ... 반복
    마지막 장소 출발 + 이동시간 = 숙소 복귀
    """
    PACE_CUT_OFF = {
        '여유':     2,
        '여유롭게': 2,
        '보통':     (2, 3),   # (min, max) 튜플 — 시뮬레이션 중 상황에 따라 2 또는 3곳
        '알차게':   (3, 4),   # (min, max) 튜플 — 시뮬레이션 중 상황에 따라 3 또는 4곳
        '빡빡':     (3, 4),
    }
    COMPANION_MULTIPLIER = {'부모님 동반': 1.2, '아이 동반': 1.3}
    ...
```

---

### ✏️ [MODIFY] `backend_postgres.py` — 데이터 수집 함수 이식

> 💡 **왜 수정하는가?**
> 현재 이 파일에는 "장소 조회/저장" 함수는 있지만
> "Google/Kakao에서 새 장소를 수집하는" 함수가 없습니다.
> 파일 하단에 `# TODO: 이식 필요`라는 주석만 남아있는 상태입니다.
> 이를 완성해야 "DB 업데이트" 기능이 동작합니다.

```python
# backend_postgres.py 하단에 추가할 함수들

def fetch_google(city, keywords):
    """
    [역할] Google Places API로 특정 도시의 장소를 검색하고 DB에 저장
    [입력] city: 도시명 ("제주"), keywords: 검색 키워드 리스트 (["카페", "관광지"])
    [처리] 키워드마다 Google Places API 호출 → 결과를 save_place()로 DB 저장
    [API 없을 때] 경고 로그만 출력하고 종료 (에러 없이 graceful 처리)
    """
    ...

def fetch_kakao(city, keywords):
    """
    [역할] 카카오 키워드 검색 API로 국내 장소 수집 → DB 저장
    [국내 전용] 카카오 API는 한국 장소만 잘 검색됨
    """
    ...

def fetch_all_data(city, keywords, is_domestic=True):
    """
    [역할] Google + Kakao를 동시에(병렬로) 실행하여 최대한 많은 장소 수집
    [병렬 처리] ThreadPoolExecutor로 동시 실행 → 순차 대비 수집 속도 향상
    [출력] {"added_count": 새로 추가된 장소 수, "final_count": 전체 장소 수}
    """
    ...
```

---

### ✏️ [MODIFY] `travel_logic/config/constants.py`

> 💡 **왜 수정하는가?**
> 새 파이프라인에서 사용하는 숫자값들(90분 임계치, Cut-off 수 등)을
> 코드 안에 직접 쓰면 나중에 찾아서 바꾸기 어렵습니다.
> 모든 "마법 숫자"를 상수 파일에 모아두어 한 곳에서 관리합니다.

```python
# constants.py에 추가할 상수들

# ─── Phase 4: 숙소 앵커링 판단 기준 ───────────────────
HOTEL_ANCHOR_TIME_THRESHOLD = 90 * 60
# "하루 중 이동시간이 이 값(90분=5400초)을 넘는 구간이 있으면
#  숙소를 그날 방문지 근처로 이동시킨다"

# ─── Phase 5: 일정 강도별 하루 최대 방문 장소 수 ────────
# 값이 정수: 그 수가 하루 최대 방문 수
# 값이 튜플 (min, max): 타임박싱 시뮬레이션 결과에 따라 min~max 사이에서 결정
PACE_MAX_PLACES = {
    "여유":     2,        # 편안한 여행, 하루 최대 2곳
    "여유롭게": 2,
    "보통":     (2, 3),   # 일반적인 여행, 시간 여유에 따라 2 또는 3곳
    "알차게":   (3, 4),   # 빡빡한 여행, 시간 여유에 따라 3 또는 4곳
    "빡빡":     (3, 4),
}

# 사용 예시 (타임박싱 로직 안에서):
#   limit = PACE_MAX_PLACES[pace]
#   max_places = limit if isinstance(limit, int) else limit[1]  # 튜플이면 상한값 사용

# ─── Phase 5: 동행자별 체류시간 배율 ────────────────────
COMPANION_STAY_MULTIPLIER = {
    "부모님 동반": 1.2,  # 부모님과 함께면 20% 더 여유있게
    "아이 동반":   1.3,  # 아이와 함께면 30% 더 여유있게
    "default":    1.0,
}

# ─── Phase 1: 후보 장소 추출 비율 ───────────────────────
CANDIDATE_POOL_RATIO = 5
# "하루에 평균 5곳 방문" 가정 → N = 여행일수 × 5
# extract_top_n()에서 이 상수를 반드시 참조할 것 (하드코딩 금지)

# ─── Phase 1: 숙소 카테고리 목록 ─────────────────────────
# generate()에서 숙소를 별도 풀로 분리할 때 이 목록으로 판단
# Phase 4 hotel_anchor_service로 전달되는 후보 풀의 기준이 됨
HOTEL_CATEGORIES = {
    "숙소", "호텔", "펜션", "리조트", "게스트하우스", "모텔",
    "lodging", "hotel", "resort", "guesthouse",
}
# 사용 예시:
#   hotels = [p for p in hard_filtered if p['category'] in HOTEL_CATEGORIES
#             and float(p.get('rating', 0)) >= user_data.get('star_rating', 3)]

# ─── Step 10: 공항 좌표 딕셔너리 ────────────────────────
# 목적: 제주공항 하드코딩 제거 → 도시별 공항 자동 조회
# 방식: 딕셔너리 조회 (API 실시간 호출 금지 — 비용 발생)
# 확장: 새 도시 추가 시 이 딕셔너리에만 항목 추가하면 됨
# 미등록 도시: None 반환 → _get_airport_place()에서 None 처리
AIRPORT_COORDS = {
    # ── 국내 ──────────────────────────────────────────────
    "제주":   {"lat": 33.5113, "lng": 126.4930, "name": "제주국제공항"},
    "제주도": {"lat": 33.5113, "lng": 126.4930, "name": "제주국제공항"},
    "서울":   {"lat": 37.5598, "lng": 126.7906, "name": "김포국제공항"},
    "인천":   {"lat": 37.4602, "lng": 126.4407, "name": "인천국제공항"},
    "부산":   {"lat": 35.1796, "lng": 128.9387, "name": "김해국제공항"},
    "대구":   {"lat": 35.8953, "lng": 128.6558, "name": "대구국제공항"},
    "광주":   {"lat": 35.1236, "lng": 126.8089, "name": "광주공항"},
    "청주":   {"lat": 36.7172, "lng": 127.4994, "name": "청주국제공항"},
    "여수":   {"lat": 34.8423, "lng": 127.6168, "name": "여수공항"},
    "양양":   {"lat": 38.0612, "lng": 128.6692, "name": "양양국제공항"},
    # ── 해외 (향후 추가 예시) ────────────────────────────
    # "오사카": {"lat": 34.7855, "lng": 135.4382, "name": "간사이국제공항"},
    # "도쿄":   {"lat": 35.7647, "lng": 140.3864, "name": "나리타국제공항"},
}
```

---

### ✏️ [MODIFY] `requirements.txt`

```diff
+ scikit-learn>=1.3.0    # Phase 2 K-Means 클러스터링용 (새로 추가)
```

---

## 4. 수정하지 않는 파일

> 💡 **아래 파일들은 이번 업그레이드에서 건드리지 않습니다.**
> API 계약(엔드포인트), DB 스키마, 화면 코드는 그대로 유지됩니다.

| 파일 | 이유 |
|------|------|
| `app/main.py` | API 엔드포인트 구조 동일 (화면과의 계약 유지) |
| `app/models.py` | 요청/응답 데이터 형식 동일 |
| `db/connection.py`, `db/models.py` | DB 테이블 구조 변경 없음 |
| `config.py` | 환경변수 로드 방식 변경 없음 |
| `travel_logic/__init__.py` | 외부 공개 인터페이스 동일 |
| `travel_logic/domain/` | 데이터 모델·검증 함수 변경 없음 |
| `frontend/` | 화면 코드 별도 Task로 관리 |

---

## 5. 구현 순서 (권장)

> 💡 **왜 이 순서인가?**
> 아래 장의 단계들은 이전 단계가 완성되어야 다음 단계를 테스트할 수 있습니다.
> 예를 들어 TSPService가 없으면 itinerary_generator.py를 테스트할 수 없습니다.

```
Step 1. requirements.txt에 scikit-learn 추가
Step 2. constants.py에 새 상수 추가
         → PACE_MAX_PLACES, COMPANION_STAY_MULTIPLIER, HOTEL_ANCHOR_TIME_THRESHOLD,
            CANDIDATE_POOL_RATIO, HOTEL_CATEGORIES (숙소 카테고리 목록), AIRPORT_COORDS
Step 3. clustering_service.py 신규 생성 (Phase 2)
Step 4. tsp_service.py 신규 생성 (Phase 3·5)
         → __init__(self, distance_service): 생성자 주입 방식 필수 구현
Step 5. hotel_anchor_service.py 신규 생성 (Phase 4)
Step 6. scoring_service.py에 hard_filter(), extract_top_n() 추가 (Phase 1)
         → extract_top_n()은 CANDIDATE_POOL_RATIO 상수를 반드시 참조할 것
            (하드코딩 숫자 사용 금지)
Step 7. backend_postgres.py에 fetch_google, fetch_kakao, fetch_all_data 이식
Step 8. itinerary_generator.py 전면 재작성 (5-Phase 파이프라인 통합)
         ※ 필수 제거: _generate_for_theme() 내 check_place_status() 호출 3줄 삭제
            (현재 itinerary_generator.py L243~245)
            폐업 장소 필터는 Phase 1 hard_filter()의 평점 조건으로 대체됨
         ※ 필수 추가: __init__에 TSPService(self.distance_service) 주입 구문
         ※ 필수 변경: 숙소는 별도 풀(_categorize_visits 분리 방식)로 관리
Step 9. services/__init__.py에 신규 서비스 export 추가
Step 10. 공항 동적 조회 구현
          → constants.py의 AIRPORT_COORDS 딕셔너리 방식 사용
             (Google Places API 실시간 조회 금지 — 불필요한 API 비용 발생)
             미등록 도시는 None 반환 → airport_place = None 처리
Step 11. 통합 테스트
```

---

## 6. 주요 트레이드오프 요약

> 💡 **트레이드오프란?**
> "A를 얻으면 B를 잃는다"처럼 모든 설계 결정에는 장단점이 있습니다.
> 아래는 이번 계획에서 선택한 방식의 장단점입니다.

| 결정 사항 | 선택한 방식 | 장점 | 단점 및 대응 |
|-----------|-------------|------|-------------|
| 클러스터링 알고리즘 | K-Means | 구현 쉬움, 속도 빠름 | 클러스터 크기 불균형 → 보정 로직으로 대응 |
| 경로 최적화 알고리즘 | Nearest Neighbor TSP | 이해 쉽고 구현 간단 | 최적 대비 최대 25% 오차 → 실용 여행에는 충분 |
| 숙소 앵커링 임계치 | 90분 (설계 문서 기준) | 명확한 기준 | 사용자마다 다를 수 있음 → 상수로 분리해 조정 쉽게 |
| `check_place_status()` | 단기적으로 비활성화 | API 비용 절감, 속도 향상 | 폐업 장소가 포함될 수 있음 → 낮은 평점으로 자연 필터링 |
| 배리어프리 필터 | 구현하되 효과 제한적 | 코드 준비 완료 | DB에 태그 데이터 없음 → TourAPI 수집 후 활성화 |

---

## 7. 구현 전 확인 필요 사항

> [!IMPORTANT]
> 아래 4가지는 구현 방향에 영향을 주므로 **확인 후 구현을 시작합니다.**

1. **`num_hotels` 값 처리 방식**
   - Next.js 폼에서 `1`, `2`, `3` 중 선택
   - `1` → 숙소 고정, `2` 이상 → 앵커링 로직 실행으로 처리 예정
   - 이 방식으로 진행해도 괜찮으신지? yes

2. **배리어프리 필터 처리 방식**
   - DB에 태그 없어서 지금은 실효성 없음
   - 로직은 추가하되, 실질 필터링은 나중에 TourAPI 연동 후로 미루는 방향 OK? yes

3. **`check_place_status()` 비활성화 여부**
   - 현재: 모든 장소마다 Google API 2회 호출 (느리고 비쌈)
   - 제안: 이번 버전에서 해당 호출 제거 (폐업 장소는 낮은 평점으로 자연 필터)
   - 이 방향으로 진행할까요? yes

4. **테마 다양성 확보 방식**
   - 지금 "핵심 코스"와 "식도락" 테마가 같은 장소 풀을 사용 → 결과 유사할 수 있음
   - 테마별로 scoring 가중치를 달리해서 선택되는 장소를 달리 할지? yes
   - 사용자가 선택한 테마에 맞춰서 코스 테마의 이름을 만들고 그 테마에 맞는 코스를 만들어줘
