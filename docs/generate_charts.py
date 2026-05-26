"""
Pick & Go 주간업무보고서 2026-05-W4
테스트 결과 시각화 차트 생성 스크립트

실행: python docs/generate_charts.py
출력: docs/chart1_sub_coverage.png
       docs/chart2_saga_rollback.png
       docs/chart3_srs_achievement.png
"""
import os
import matplotlib
matplotlib.use("Agg")  # 화면 없이 파일로 저장
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ── 한글 폰트 설정 (Windows 맑은 고딕) ───────────────────────────────
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgun.ttf",   # Windows 맑은 고딕
    "C:/Windows/Fonts/NanumGothic.ttf",
]
for _fp in _FONT_CANDIDATES:
    if os.path.exists(_fp):
        _prop = fm.FontProperties(fname=_fp)
        plt.rcParams["font.family"] = _prop.get_name()
        break

plt.rcParams["axes.unicode_minus"] = False  # 마이너스 기호 깨짐 방지

OUT = os.path.dirname(os.path.abspath(__file__))  # docs/ 폴더

BLUE_MAIN  = "#2563eb"
BLUE_MID   = "#60a5fa"
BLUE_LIGHT = "#93c5fd"
EDGE_COLOR = "#1e40af"


def _save(fig: plt.Figure, filename: str) -> None:
    path = os.path.join(OUT, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  저장 완료: {path}")


def _label_bars(ax, bars, fmt="{}", offset=0.08):
    """막대 위에 수치 레이블을 표시한다."""
    for bar in bars:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h + offset,
            fmt.format(h),
            ha="center", va="bottom",
            fontsize=11, fontweight="bold",
        )


def _style(ax):
    """공통 스타일: 위·오른쪽 테두리 제거, 가로 점선 그리드."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.4)


# ── 그림 1: Sub별 테스트 커버리지 ────────────────────────────────────
def chart1():
    labels = ["Sub1\n입력검증", "Sub2\n외부예약", "Sub3\n확정검증",
              "Sub4\nDB저장", "Sub5\n결과응답"]
    values = [3, 4, 3, 2, 1]

    fig, ax = plt.subplots(figsize=(8, 4.2))
    bars = ax.bar(labels, values, color=BLUE_MAIN, edgecolor=EDGE_COLOR, width=0.5)
    ax.set_title("Sub별 테스트 커버리지  (검증 TC 수 / 전체 4개)", fontsize=13, pad=12)
    ax.set_ylabel("TC 수", fontsize=11)
    ax.set_ylim(0, 5.5)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    _label_bars(ax, bars)
    _style(ax)
    fig.tight_layout()
    _save(fig, "chart1_sub_coverage.png")


# ── 그림 2: 실패 시나리오별 Saga 롤백 처리 건수 ──────────────────────
def chart2():
    labels = ["TC-02\n숙소 매진", "TC-03\nSub3 실패", "TC-04\nDB 실패"]
    values = [1, 1, 2]

    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    bars = ax.bar(labels, values, color=BLUE_MAIN, edgecolor=EDGE_COLOR, width=0.4)
    ax.set_title("실패 시나리오별 Saga 롤백 처리 건수", fontsize=13, pad=12)
    ax.set_ylabel("취소 처리 건수", fontsize=11)
    ax.set_ylim(0, 3.2)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    _label_bars(ax, bars, offset=0.06)
    _style(ax)
    fig.tight_layout()
    _save(fig, "chart2_saga_rollback.png")


# ── 그림 3: SRS 목표 사양 달성률 ─────────────────────────────────────
def chart3():
    labels = ["M-11\n일괄예약/전체취소", "M-12\n15초 이내", "M-13\n99.9% 성공률"]
    values = [100, 80, 70]
    colors = [BLUE_MAIN, BLUE_MID, BLUE_LIGHT]

    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(labels, values, color=colors, edgecolor=EDGE_COLOR, width=0.4)
    ax.set_title("SRS 목표 사양 달성률 (%)", fontsize=13, pad=12)
    ax.set_ylabel("달성률 (%)", fontsize=11)
    ax.set_ylim(0, 118)
    # 목표 기준선 100%
    ax.axhline(y=100, color="#ef4444", linestyle="--", linewidth=1.2,
               alpha=0.7, label="목표 기준선 (100%)")
    ax.legend(fontsize=9, loc="upper right")
    _label_bars(ax, bars, fmt="{}%", offset=1.5)
    _style(ax)
    fig.tight_layout()
    _save(fig, "chart3_srs_achievement.png")


if __name__ == "__main__":
    print("차트 생성 시작...")
    chart1()
    chart2()
    chart3()
    print("모든 차트 생성 완료.")
