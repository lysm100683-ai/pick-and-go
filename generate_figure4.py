"""
[그림 4] ST_Distance vs ST_DWithin 응답 시간 비교 그래프 생성 스크립트
- 실측 데이터: 1,533건 기준 벤치마크 결과 사용
- ST_Distance: O(N) 선형 증가 추정
- ST_DWithin + GiST: O(log N) 로그적 수렴 추정
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import os

# ── 실측 데이터 (benchmark_cache.py 실행 결과) ──────────────────────────
MEASURED_COUNT     = 1_533      # 측정 시 데이터 건수
ST_DISTANCE_REAL   = 0.08297    # 실측 응답 시간 (초)
ST_DWITHIN_REAL    = 0.06281    # 실측 응답 시간 (초)

# ── x축: 데이터 건수 범위 ─────────────────────────────────────────────
counts = np.array([1_000, 5_000, 10_000, 50_000,
                   100_000, 500_000, 1_000_000])

# ── ST_Distance 추정: O(N) 선형 비례 ─────────────────────────────────
st_distance_times = ST_DISTANCE_REAL * (counts / MEASURED_COUNT)

# ── ST_DWithin 추정: O(log N) 로그 수렴 ──────────────────────────────
#    실측값에서 역산: base + k * log(N) = 0.063  at N=1533
#    base ≈ 0.01 (인덱스 고정 오버헤드), k 를 실측값으로 맞춤
BASE   = 0.01
K      = (ST_DWITHIN_REAL - BASE) / np.log(MEASURED_COUNT)
st_dwithin_times = BASE + K * np.log(counts)

# ── 그래프 설정 ──────────────────────────────────────────────────────
plt.rcParams.update({
    'font.family'     : 'Malgun Gothic',   # 한글 폰트
    'axes.unicode_minus': False,
    'figure.dpi'      : 150,
})

fig, ax = plt.subplots(figsize=(10, 6))

# ST_Distance 선 (빨강 실선)
ax.plot(counts, st_distance_times,
        color='#E74C3C', linewidth=2.5, marker='o', markersize=6,
        label='ST_Distance (풀 스캔, O(N))')

# ST_DWithin 선 (파랑 실선)
ax.plot(counts, st_dwithin_times,
        color='#2E86C1', linewidth=2.5, marker='s', markersize=6,
        label='ST_DWithin + GiST (인덱스 탐색, O(log N))')

# ── 실측 데이터 포인트 강조 ───────────────────────────────────────────
ax.scatter([MEASURED_COUNT], [ST_DISTANCE_REAL],
           color='#E74C3C', s=120, zorder=6)
ax.scatter([MEASURED_COUNT], [ST_DWITHIN_REAL],
           color='#2E86C1', s=120, zorder=6)

# 실측값 어노테이션
ax.annotate(f'실측: {ST_DISTANCE_REAL:.3f}초 (1,533건)',
            xy=(MEASURED_COUNT, ST_DISTANCE_REAL),
            xytext=(8_000, ST_DISTANCE_REAL + 8),
            fontsize=9, color='#E74C3C',
            arrowprops=dict(arrowstyle='->', color='#E74C3C', lw=1.2))

ax.annotate(f'실측: {ST_DWITHIN_REAL:.3f}초 (1,533건)',
            xy=(MEASURED_COUNT, ST_DWITHIN_REAL),
            xytext=(8_000, ST_DWITHIN_REAL - 8),
            fontsize=9, color='#2E86C1',
            arrowprops=dict(arrowstyle='->', color='#2E86C1', lw=1.2))

# 100만 건 추산값 표시
val_dist_1m  = ST_DISTANCE_REAL * (1_000_000 / MEASURED_COUNT)
val_dwith_1m = BASE + K * np.log(1_000_000)
ax.annotate(f'추산: {val_dist_1m:.0f}초',
            xy=(1_000_000, val_dist_1m),
            xytext=(400_000, val_dist_1m - 8),
            fontsize=9, color='#E74C3C',
            arrowprops=dict(arrowstyle='->', color='#E74C3C', lw=1.2))
ax.annotate(f'추산: {val_dwith_1m:.3f}초',
            xy=(1_000_000, val_dwith_1m),
            xytext=(300_000, val_dwith_1m + 6),
            fontsize=9, color='#2E86C1',
            arrowprops=dict(arrowstyle='->', color='#2E86C1', lw=1.2))

# ── 축 설정 ──────────────────────────────────────────────────────────
ax.set_xscale('log')
ax.set_xlabel('데이터 건수 (건)', fontsize=12)
ax.set_ylabel('1회 평균 응답 시간 (초)', fontsize=12)
ax.set_title('ST_Distance vs ST_DWithin + GiST 탐색 성능 비교', fontsize=14, fontweight='bold')

# x축 레이블 (건수 단위 표시)
ax.set_xticks([1_000, 5_000, 10_000, 50_000, 100_000, 500_000, 1_000_000])
ax.set_xticklabels(['1천', '5천', '1만', '5만', '10만', '50만', '100만'], fontsize=10)

ax.legend(fontsize=11, loc='upper left')
ax.grid(True, which='both', alpha=0.3, linestyle='--')
ax.set_ylim(bottom=-2)

# 배경 강조 (차이가 벌어지는 구간)
ax.axvspan(100_000, 1_000_000, alpha=0.04, color='#E74C3C',
           label='_nolegend_')

plt.tight_layout()

# ── 저장 ─────────────────────────────────────────────────────────────
out_path = os.path.join('docs', 'figure4_performance_graph.png')
plt.savefig(out_path, dpi=150, bbox_inches='tight')
print(f"[완료] 그래프 저장: {out_path}")
print(f"  ST_Distance  100만건 추산: {val_dist_1m:.1f}초")
print(f"  ST_DWithin   100만건 추산: {val_dwith_1m:.4f}초")
plt.close()
