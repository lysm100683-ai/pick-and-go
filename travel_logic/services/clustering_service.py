# travel_logic/services/clustering_service.py
"""
Phase 2: 공간 클러스터링 (Haversine K-Means)

역할: 후보 장소들을 지리적으로 가까운 것끼리 묶어 날짜별 그룹으로 분류
알고리즘: 커스텀 Haversine K-Means (k = 여행 일수)

입력: places (후보 장소 리스트, 위도/경도 포함), num_days (여행 일수)
      anchor_points (숙소·공항 좌표 리스트, 선택)
출력: clusters (일자별 장소 그룹), centroids (일자별 지리적 중심점)

[개선 이력]
  v1: 유클리드 K-Means + 맹목적 pop() 리밸런싱
  v2: Haversine 리밸런싱 + Time-Box 검증
      - _rebalance: pop() → Haversine 최근접 centroid 기반 양도 (텔레포트 방지)
      - _timebox_check: 하루 체류 시간 10시간 초과 시 최저 점수 장소 제거
  v3: 완전한 Haversine K-Means + 앵커 시딩 (B·D 개선)
      - _haversine_kmeans: sklearn Euclidean 대체 — 구면 거리 기반 반복 군집화
      - _kmeans_plus_plus_init: K-Means++ 초기화 + 숙소/공항 좌표 강제 시드
      - cluster_by_day: anchor_points 파라미터 추가 (Seeded K-Means)
"""

import math
import numpy as np
from typing import List, Dict, Any, Tuple, Optional


# ── 모듈 상수 ────────────────────────────────────────────────────
_MAX_DAILY_HOURS    = 10           # 하루 최대 체류 시간 (순수 관람, 이동 제외)
_SIGHT_VISIT_SEC    = 2.5 * 3600  # 관광지 기본 체류 시간 (초) — 2시간 30분
_CAFE_VISIT_SEC     = 1.0 * 3600  # 카페 기본 체류 시간 (초)  — 1시간
_FOOD_VISIT_SEC     = 1.5 * 3600  # 식사 기본 체류 시간 (초)  — 1시간 30분

# type_key별 체류 시간 매핑 (VISIT_TIMES import 없이 독립 동작)
_VISIT_MAP: Dict[str, float] = {
    "관광":    _SIGHT_VISIT_SEC,
    "식사":    _FOOD_VISIT_SEC,
    "카페":    _CAFE_VISIT_SEC,
    "숙소":    0.5 * 3600,
    "default": _SIGHT_VISIT_SEC,  # 미분류 장소는 관광지 기준 적용
}


class ClusteringService:
    """
    지리 좌표 기반 K-Means 클러스터링으로 장소를 날짜별로 그룹화.

    plan.md 설계 원칙:
      - K = 여행 일수 (num_days)
      - K-Means 초기화: 유클리드 거리 (국내 반경 내 오차 허용)
      - 사후 보정: Haversine 거리 기반 스마트 리밸런싱 (v2)
      - Time-Box 검증: 하루 체류 시간 10시간 초과 시 최저 점수 장소 제거 (v2)
    """

    @staticmethod
    def cluster_by_day(
        places: List[Dict[str, Any]],
        num_days: int,
        anchor_points: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[List[Dict[str, Any]]], List[Tuple[float, float]]]:
        """
        장소 리스트를 num_days개의 지리적 클러스터로 분류한다.

        [v3 변경]
          - anchor_points: 숙소·공항 좌표를 K-Means 초기 중심점으로 강제 시딩 (개선점 D)
          - 내부 알고리즘: sklearn Euclidean → 커스텀 Haversine K-Means (개선점 B)

        Args:
            places:        후보 장소 리스트 (각 항목에 'lat', 'lng' 키 필수)
            num_days:      여행 일수 (= K-Means의 K값)
            anchor_points: 숙소·공항 정보 리스트 (선택). 제공 시 해당 좌표가
                           K-Means 초기 중심점으로 우선 사용됨.

        Returns:
            clusters:  [[1일차 장소들], [2일차 장소들], ...]
            centroids: [(1일차 중심 위도, 경도), (2일차 중심 위도, 경도), ...]
        """
        # ── 예외 처리: 장소 수 부족 ──────────────────────────────
        if not places:
            return [[] for _ in range(num_days)], [(0.0, 0.0)] * num_days

        if len(places) <= num_days:
            clusters = [[p] for p in places]
            clusters += [[] for _ in range(num_days - len(places))]
            centroids = [
                (p['lat'], p['lng']) for p in places
            ] + [(0.0, 0.0)] * (num_days - len(places))
            return clusters, centroids

        # ── [개선점 B+D] 커스텀 Haversine K-Means ────────────────
        # sklearn KMeans(Euclidean) 완전 대체:
        #   - 구면 거리(Haversine) 기반 반복 군집화로 지형 왜곡 제거
        #   - anchor_points로 숙소/공항 위치를 초기 중심점으로 강제 지정
        labels, raw_centroids = ClusteringService._haversine_kmeans(
            places, num_days, anchor_points=anchor_points
        )

        # ── 클러스터 구성 ────────────────────────────────────────
        clusters: List[List[Dict[str, Any]]] = [[] for _ in range(num_days)]
        for place, label in zip(places, labels):
            clusters[label].append(place)

        # ── 사후 보정: 스마트 리밸런싱 + Time-Box (v2 로직 유지) ─
        clusters, centroids = ClusteringService._rebalance(clusters, raw_centroids)

        return clusters, centroids

    # ─────────────────────────────────────────────────────────────
    #  내부 헬퍼 메서드
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _haversine_dist(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Haversine 공식 기반 두 좌표 간 구면 거리 계산 (km). 변경 없음(v2)."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlng / 2) ** 2
        )
        return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    @staticmethod
    def _kmeans_plus_plus_init(
        coords: List[Tuple[float, float]],
        k: int,
        anchor_coords: Optional[List[Tuple[float, float]]] = None,
    ) -> List[Tuple[float, float]]:
        """
        [개선점 D] K-Means++ 방식 초기 중심점 선택 + 앵커 시딩.

        anchor_coords가 있으면 해당 좌표를 우선 중심점으로 확보하고,
        나머지 슬롯은 K-Means++ 방식(거리 비례 확률)으로 채운다.

        [v1/v2 대비]
          기존: sklearn이 내부적으로 random_state=42 K-Means++ 수행 (앵커 시딩 불가)
          v3:  숙소/공항 좌표 → 강제 초기 중심점 → K-Means++ 보충
        """
        import random as _rnd
        _rnd.seed(42)

        centroids: List[Tuple[float, float]] = []

        # ① 앵커 포인트 우선 적재
        if anchor_coords:
            for ac in anchor_coords[:k]:
                centroids.append(ac)

        # ② 나머지 슬롯: K-Means++ (거리 비례 확률 샘플링)
        while len(centroids) < k:
            if not centroids:
                centroids.append(_rnd.choice(coords))
                continue

            # 각 좌표의 가장 가까운 기존 중심점까지의 거리
            dist_sq = [
                min(
                    ClusteringService._haversine_dist(lat, lng, c[0], c[1]) ** 2
                    for c in centroids
                )
                for lat, lng in coords
            ]
            total = sum(dist_sq)
            if total == 0:
                centroids.append(_rnd.choice(coords))
                continue

            # 거리 제곱 비례 확률로 다음 중심점 선택
            r = _rnd.random() * total
            cumulative = 0.0
            chosen = coords[-1]
            for i, d in enumerate(dist_sq):
                cumulative += d
                if cumulative >= r:
                    chosen = coords[i]
                    break
            centroids.append(chosen)

        return centroids

    @staticmethod
    def _haversine_kmeans(
        places: List[Dict[str, Any]],
        num_days: int,
        anchor_points: Optional[List[Dict[str, Any]]] = None,
        max_iter: int = 100,
    ) -> Tuple[List[int], List[Tuple[float, float]]]:
        """
        [개선점 B] 커스텀 Haversine K-Means 알고리즘.

        sklearn KMeans는 Euclidean 거리만 지원하므로 완전 대체.
        위도/경도 기반 구면 거리(Haversine)를 사용하여 지형 왜곡을 제거한다.

        [v1/v2 대비]
          v1/v2: coords = np.array([[lat, lng]]) → sklearn KMeans.fit_predict()
                  → Euclidean 거리: 위도 1도≒111km, 경도 1도≒92km(제주 기준)
                    두 값의 단위 차이로 인해 경도 방향 거리가 과소평가됨
          v3:    Haversine(km) 기반 반복 수렴 → 실제 지구 구면 거리 기준 군집

        Args:
            places:       후보 장소 리스트
            num_days:     클러스터 수 (K)
            anchor_points: 숙소/공항 좌표 리스트 (초기 중심점으로 사용)
            max_iter:     최대 반복 횟수

        Returns:
            labels:    각 장소가 속한 클러스터 인덱스 리스트
            centroids: 클러스터별 최종 중심점 (lat, lng) 리스트
        """
        coords: List[Tuple[float, float]] = [
            (float(p['lat']), float(p['lng'])) for p in places
        ]

        # 앵커 포인트 변환
        anchor_coords: Optional[List[Tuple[float, float]]] = None
        if anchor_points:
            anchor_coords = [
                (float(a['lat']), float(a['lng']))
                for a in anchor_points
                if a.get('lat') and a.get('lng')
            ] or None

        # 초기 중심점: K-Means++ + 앵커 시딩
        centroids = ClusteringService._kmeans_plus_plus_init(
            coords, num_days, anchor_coords
        )

        prev_labels: Optional[List[int]] = None

        for _ in range(max_iter):
            # 각 장소를 가장 가까운 중심점에 배정
            labels: List[int] = []
            for lat, lng in coords:
                dists = [
                    ClusteringService._haversine_dist(lat, lng, c[0], c[1])
                    for c in centroids
                ]
                labels.append(int(np.argmin(dists)))

            # 수렴 확인
            if labels == prev_labels:
                break
            prev_labels = labels

            # 중심점 업데이트: 클러스터 내 장소 좌표 평균
            new_centroids: List[Tuple[float, float]] = []
            for k in range(num_days):
                cluster_coords = [coords[i] for i, lbl in enumerate(labels) if lbl == k]
                if cluster_coords:
                    avg_lat = sum(c[0] for c in cluster_coords) / len(cluster_coords)
                    avg_lng = sum(c[1] for c in cluster_coords) / len(cluster_coords)
                    new_centroids.append((avg_lat, avg_lng))
                else:
                    new_centroids.append(centroids[k])  # 빈 클러스터: 중심점 유지
            centroids = new_centroids

        return labels if prev_labels is not None else [0] * len(places), centroids

    @staticmethod
    def _rebalance(
        clusters: List[List[Dict[str, Any]]],
        centroids: List[Tuple[float, float]]
    ) -> Tuple[List[List[Dict[str, Any]]], List[Tuple[float, float]]]:
        """
        클러스터 균등화 보정 (v2 — Haversine 기반 스마트 리밸런싱).

        [v1 → v2 핵심 변경]
          v1: clusters[max].pop() → 리스트 끝 장소 무조건 이동 (지리적 맥락 무시)
          v2: 이동 받을 min 클러스터의 현재 centroid를 계산하고,
              max 클러스터에서 그 centroid와 Haversine 거리가 가장 가까운
              장소를 골라서 이동 → 지리적 응집도 유지, 텔레포트 방지

        처리 순서:
          ① 빈 클러스터: 가장 큰 클러스터의 절반을 이동
          ② 크기 불균형(≥3): Haversine 최근접 장소 양도 (최대 10회)
          ③ Time-Box: 하루 체류 시간 _MAX_DAILY_HOURS 초과 시 최저 점수 장소 제거
          ④ centroid 재계산: 실제 장소 좌표 평균

        Args:
            clusters:  클러스터별 장소 리스트
            centroids: K-Means centroid 좌표 리스트

        Returns:
            보정된 (clusters, centroids)
        """
        num_days = len(clusters)

        # ① 빈 클러스터: 가장 큰 클러스터에서 절반 이동
        # [C-3 fix] len(src) >= 2 조건이면 최대 클러스터가 1개일 때 이전 불가 → 빈 날 발생.
        # len(src) >= 1 로 완화하여 최소 1개라도 이전.
        for i in range(num_days):
            if not clusters[i]:
                largest_idx = max(range(num_days), key=lambda j: len(clusters[j]))
                src = clusters[largest_idx]
                if len(src) >= 2:
                    half = len(src) // 2
                    clusters[i] = src[half:]
                    clusters[largest_idx] = src[:half]
                elif len(src) == 1:
                    # 최대 클러스터도 1개뿐이면 그것만 이전 (빈 날 방지 우선)
                    clusters[i] = src[:]
                    clusters[largest_idx] = []

        # ② 크기 균등화: Haversine 거리 기반 스마트 양도 (최대 10회 순환)
        #
        #   [v1 코드]:  clusters[min_idx].append(clusters[max_idx].pop())
        #   → pop()은 Python 리스트의 마지막 원소를 꺼냄.
        #     K-Means가 장소를 처리한 "임의의 순서"에 따른 마지막 장소로,
        #     지리적 위치와 무관. 강남 클러스터의 끝 장소가 강북 클러스터로
        #     편입되는 텔레포트 현상 발생.
        #
        #   [v2 코드]:  best_place = min(max_cluster, key=haversine_to_min_centroid)
        #   → min 클러스터의 현재 중심점과 가장 가까운 장소를 선택하므로
        #     지리적 경계 위치의 장소가 자연스럽게 이동.
        for _ in range(10):
            sizes = [len(c) for c in clusters]
            max_idx = sizes.index(max(sizes))
            min_idx = sizes.index(min(sizes))

            if sizes[max_idx] - sizes[min_idx] < 3:
                break  # 균등화 완료

            # min 클러스터의 현재 centroid 계산 (실제 장소 좌표 평균 우선)
            if clusters[min_idx]:
                min_lat = sum(p['lat'] for p in clusters[min_idx]) / len(clusters[min_idx])
                min_lng = sum(p['lng'] for p in clusters[min_idx]) / len(clusters[min_idx])
            else:
                # 빈 클러스터면 K-Means 원본 centroid 사용
                min_lat, min_lng = centroids[min_idx]

            # max 클러스터에서 min centroid와 Haversine 거리가 가장 가까운 장소 선택
            best_place = min(
                clusters[max_idx],
                key=lambda p: ClusteringService._haversine_dist(
                    p['lat'], p['lng'], min_lat, min_lng
                )
            )
            clusters[max_idx].remove(best_place)
            clusters[min_idx].append(best_place)

        # ③ Time-Box 검증: 하루 체류 시간 초과 클러스터 보정
        clusters = ClusteringService._timebox_check(clusters)

        # ④ centroid 재계산: 실제 장소 좌표 평균
        # [M-4] 빈 클러스터는 (0.0, 0.0) 대신 인접 유효 클러스터 centroid 사용
        #       → TSP start_point가 (0,0)이 되어 Haversine greedy 폴백되는 문제 방지
        recomputed_centroids: List[Tuple[float, float]] = []
        for i, group in enumerate(clusters):
            if group:
                avg_lat = sum(p['lat'] for p in group) / len(group)
                avg_lng = sum(p['lng'] for p in group) / len(group)
                recomputed_centroids.append((avg_lat, avg_lng))
            elif centroids[i] != (0.0, 0.0):
                recomputed_centroids.append(centroids[i])
            else:
                # (0,0) centroid이거나 원본도 없으면 유효한 다른 centroid 중 첫 번째 사용
                fallback = next(
                    (c for j, c in enumerate(centroids) if j != i and c != (0.0, 0.0)),
                    centroids[i]
                )
                recomputed_centroids.append(fallback)

        return clusters, recomputed_centroids

    @staticmethod
    def _timebox_check(
        clusters: List[List[Dict[str, Any]]],
        max_hours: float = _MAX_DAILY_HOURS,
    ) -> List[List[Dict[str, Any]]]:
        """
        하루 총 체류 시간 초과 클러스터 보정 (Time-Box 검증).

        [배경]
          v1 ClusteringService는 장소 '개수'만 균등화하여, 어느 날은
          테마파크+박물관+아쿠아리움이 몰려 14시간짜리 불가능한 일정이,
          다른 날은 카페 2개로 3시간만에 끝나는 불균형이 발생할 수 있었음.

        [동작 원리]
          각 클러스터의 총 예상 체류 시간이 max_hours를 초과하면
          score가 가장 낮은 장소를 하나씩 제거한다.
          - 최소 1개 장소는 반드시 보존 (완전 빈 클러스터 방지)
          - type_key가 있으면 _VISIT_MAP 참조, 없으면 관광지 기준(_SIGHT_VISIT_SEC)

        Args:
            clusters:  클러스터별 장소 리스트
            max_hours: 하루 최대 허용 체류 시간 (기본 10시간)

        Returns:
            보정된 clusters (초과 장소가 제거될 수 있음)
        """
        max_seconds = max_hours * 3600

        for cluster in clusters:
            while len(cluster) > 1:
                # 클러스터 내 모든 장소의 예상 체류 시간 합산
                total_seconds = sum(
                    _VISIT_MAP.get(p.get('type_key', 'default'), _SIGHT_VISIT_SEC)
                    for p in cluster
                )
                if total_seconds <= max_seconds:
                    break  # 시간 초과 없음 → 보정 불필요
                # 점수가 가장 낮은 장소를 제거 (우선순위 기반 드롭)
                worst = min(cluster, key=lambda p: p.get('score', 0))
                cluster.remove(worst)

        return clusters

    @staticmethod
    def _fallback_split(
        places: List[Dict[str, Any]],
        num_days: int
    ) -> Tuple[List[List[Dict[str, Any]]], List[Tuple[float, float]]]:
        """
        scikit-learn 미설치 시 폴백: 순번 기준 균등 분배.

        성능은 K-Means보다 낮지만, 의존성 없이 동작 보장.
        """
        clusters: List[List[Dict[str, Any]]] = [[] for _ in range(num_days)]
        for idx, place in enumerate(places):
            clusters[idx % num_days].append(place)

        centroids: List[Tuple[float, float]] = []
        for group in clusters:
            if group:
                avg_lat = sum(p['lat'] for p in group) / len(group)
                avg_lng = sum(p['lng'] for p in group) / len(group)
                centroids.append((avg_lat, avg_lng))
            else:
                centroids.append((0.0, 0.0))

        return clusters, centroids
