# app/reservation/sub_metrics.py
"""
SRS M-13 — 예약 성공률 통계 측정 체계
목표: 예약 성공률 ≥ 99.9%

측정 방식:
  - 시도(attempt) : Sub1 검증 통과 시점에 기록
  - 성공(success) : Sub4 DB 저장 완료 시점에 기록 (기존)
  - 실패(failure) : Sub2/Sub3/Sub4 실패 시 main.py에서 호출
  성공률 = success / (success + failure) * 100

저장소: reservation_logs 테이블 (action_type, sub_system, result, payload)

환경변수:
  METRICS_PERIOD_DAYS  집계 기간 (기본 7일)
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from db.connection import get_db_session
from db.models import ReservationLog


# ── 내부 동기 함수 (asyncio.to_thread 용) ─────────────────────────

def _log_attempt_sync(user_id: str, itinerary_id: str, dest_city: str) -> None:
    """예약 시도 로그 기록 (Sub1 완료 직후)"""
    try:
        with get_db_session() as session:
            session.add(ReservationLog(
                reservation_id = None,           # 아직 예약 ID 없음
                action_type    = "attempt",
                sub_system     = "sub1",
                result         = "ok",
                payload        = {
                    "user_id":       user_id,
                    "itinerary_id":  itinerary_id,
                    "dest_city":     dest_city,
                },
            ))
            session.commit()
    except Exception as exc:
        # 측정 실패가 예약 흐름에 영향 주면 안 됨 → 무음 처리
        print(f"[Metrics] attempt 로그 저장 실패 (무시): {exc}")


def _log_pipeline_failure_sync(
    error_code: str,
    failed_sub: str,
    user_id: str,
    dest_city: str,
) -> None:
    """Sub2·Sub3 실패 시 실패 로그 기록 (main.py에서 호출)"""
    try:
        with get_db_session() as session:
            session.add(ReservationLog(
                reservation_id = None,
                action_type    = "failure",
                sub_system     = failed_sub,
                result         = "error",
                payload        = {
                    "error_code": error_code,
                    "user_id":    user_id,
                    "dest_city":  dest_city,
                },
            ))
            session.commit()
    except Exception as exc:
        print(f"[Metrics] failure 로그 저장 실패 (무시): {exc}")


def _get_stats_sync(period_days: int = 7) -> dict:
    """
    지난 N일간 reservation_logs 집계.
    반환:
      {
        "period_days":   7,
        "attempt_count": 10,
        "success_count": 9,
        "failure_count": 1,
        "success_rate":  90.0,   # %
        "meets_srs_m13": False,  # ≥ 99.9% 달성 여부
        "measured_at":   "2026-05-26T...",
      }
    """
    since = datetime.now(timezone.utc) - timedelta(days=period_days)
    try:
        with get_db_session() as session:
            rows = (
                session.query(
                    ReservationLog.action_type,
                    ReservationLog.result,
                )
                .filter(ReservationLog.created_at >= since)
                .all()
            )
    except Exception as exc:
        return {"error": str(exc)}

    attempt_count = sum(1 for r in rows if r.action_type == "attempt")
    success_count = sum(1 for r in rows if r.action_type == "success" and r.result == "ok")
    failure_count = sum(1 for r in rows if r.action_type == "failure" and r.result == "error")

    denominator = success_count + failure_count
    success_rate = (success_count / denominator * 100) if denominator > 0 else None

    return {
        "period_days":   period_days,
        "attempt_count": attempt_count,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate":  round(success_rate, 2) if success_rate is not None else None,
        "meets_srs_m13": (success_rate is not None and success_rate >= 99.9),
        "measured_at":   datetime.now(timezone.utc).isoformat(),
    }


# ── 공개 비동기 인터페이스 ──────────────────────────────────────────

async def log_attempt(user_id: str, itinerary_id: str, dest_city: str) -> None:
    """Sub1 완료 후 예약 시도 로그 기록 (best-effort — 실패해도 예약 흐름 유지)"""
    await asyncio.to_thread(_log_attempt_sync, user_id, itinerary_id, dest_city)


async def log_pipeline_failure(
    error_code: str,
    failed_sub: str,
    user_id: str = "",
    dest_city: str = "",
) -> None:
    """Sub2·Sub3 실패 시 실패 로그 기록 (main.py rollback 직후 호출)"""
    await asyncio.to_thread(
        _log_pipeline_failure_sync, error_code, failed_sub, user_id, dest_city
    )


async def get_stats_summary(period_days: int = 7) -> dict:
    """
    SRS M-13 성공률 통계 반환.

    Args:
        period_days: 집계 기간 (기본 7일)
    Returns:
        dict: attempt/success/failure 카운트, 성공률, M-13 달성 여부
    """
    stats = await asyncio.to_thread(_get_stats_sync, period_days)
    _print_stats(stats)
    return stats


def _print_stats(stats: dict) -> None:
    if "error" in stats:
        print(f"[Metrics] 통계 조회 실패: {stats['error']}")
        return

    rate = stats.get("success_rate")
    rate_str = f"{rate:.2f}%" if rate is not None else "측정 불가 (데이터 없음)"
    meets = stats.get("meets_srs_m13")
    mark  = "[PASS]" if meets else ("[N/A]" if rate is None else "[FAIL]")

    print(
        f"[Metrics/M-13] {mark} "
        f"최근 {stats['period_days']}일 | "
        f"시도:{stats['attempt_count']} "
        f"성공:{stats['success_count']} "
        f"실패:{stats['failure_count']} | "
        f"성공률:{rate_str} (목표: ≥99.9%)"
    )
