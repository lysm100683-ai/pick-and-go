"""
scripts/db_viewer.py — DB 저장 데이터 간단 조회 스크립트

사용법:
    python scripts/db_viewer.py              # 전체 요약
    python scripts/db_viewer.py --city 제주  # 특정 도시 장소 목록
    python scripts/db_viewer.py --category 숙소  # 카테고리 필터
    python scripts/db_viewer.py --reservations   # 예약 내역 조회
"""
import sys
import os
import io
import argparse

# Windows 터미널 한글 깨짐 방지
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
elif hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_db_session
from db.models import Place, Reservation, ReservationLog


def summary():
    """전체 DB 현황 요약"""
    with get_db_session() as session:
        total = session.query(Place).count()
        print(f"\n{'='*55}")
        print(f"  Pick & Go DB 현황 요약")
        print(f"{'='*55}")
        print(f"  총 저장 장소: {total:,}개")

        # 도시별 집계
        from sqlalchemy import func
        city_counts = (
            session.query(Place.city, func.count(Place.id))
            .group_by(Place.city)
            .order_by(func.count(Place.id).desc())
            .all()
        )
        print(f"\n  [도시별 장소 수]")
        for city, cnt in city_counts:
            print(f"    {city:<15} {cnt:>6,}개")

        # 카테고리별 집계
        cat_counts = (
            session.query(Place.category, func.count(Place.id))
            .group_by(Place.category)
            .order_by(func.count(Place.id).desc())
            .limit(10)
            .all()
        )
        print(f"\n  [카테고리별 장소 수 (상위 10)]")
        for cat, cnt in cat_counts:
            print(f"    {(cat or '미분류'):<20} {cnt:>6,}개")

        # 소스별 집계
        src_counts = (
            session.query(Place.source, func.count(Place.id))
            .group_by(Place.source)
            .all()
        )
        print(f"\n  [데이터 소스]")
        for src, cnt in src_counts:
            print(f"    {src:<15} {cnt:>6,}개")

        # 예약 현황
        try:
            res_count = session.query(Reservation).count()
            log_count = session.query(ReservationLog).count()
            print(f"\n  [예약 현황]")
            print(f"    예약 건수: {res_count:,}건")
            print(f"    처리 로그: {log_count:,}건")
        except Exception as e:
            print(f"\n  [예약 현황] 조회 실패: {e}")

        print(f"{'='*55}\n")


def list_places(city=None, category=None, limit=30):
    """장소 목록 조회"""
    with get_db_session() as session:
        q = session.query(Place)
        if city:
            q = q.filter(Place.city.ilike(f"%{city}%"))
        if category:
            q = q.filter(Place.category.ilike(f"%{category}%"))
        q = q.order_by(Place.rating.desc()).limit(limit)
        places = q.all()

        filter_desc = []
        if city:
            filter_desc.append(f"도시={city}")
        if category:
            filter_desc.append(f"카테고리={category}")
        filter_str = ", ".join(filter_desc) if filter_desc else "전체"

        print(f"\n{'='*80}")
        print(f"  장소 목록 ({filter_str}, 상위 {limit}개 - 평점순)")
        print(f"{'='*80}")
        print(f"  {'이름':<22} {'도시':<8} {'카테고리':<14} {'평점':>5} {'소스':<8} {'리뷰수':>6}")
        print(f"  {'-'*75}")
        for p in places:
            name = (p.name or '')[:20]
            city_s = (p.city or '')[:7]
            cat = (p.category or '미분류')[:12]
            rating = f"{float(p.rating):.1f}" if p.rating else "  -"
            src = (p.source or '')[:7]
            rev = p.review_count or 0
            print(f"  {name:<22} {city_s:<8} {cat:<14} {rating:>5} {src:<8} {rev:>6,}")
        print(f"  총 {len(places)}개 표시\n")


def list_reservations(limit=20):
    """예약 내역 조회"""
    with get_db_session() as session:
        reservations = (
            session.query(Reservation)
            .order_by(Reservation.created_at.desc())
            .limit(limit)
            .all()
        )
        print(f"\n{'='*80}")
        print(f"  예약 내역 (최근 {limit}건)")
        print(f"{'='*80}")
        if not reservations:
            print("  저장된 예약 없음\n")
            return
        print(f"  {'예약ID':<10} {'사용자ID':<15} {'상태':<10} {'금액':>10} {'생성일'}")
        print(f"  {'-'*75}")
        for r in reservations:
            rid = str(r.id)[:8]
            uid = (r.user_id or '')[:14]
            status = r.status or '-'
            amount = f"{float(r.total_amount):,.0f}원" if r.total_amount else "-"
            created = r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "-"
            print(f"  {rid:<10} {uid:<15} {status:<10} {amount:>10} {created}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pick & Go DB 조회 도구")
    parser.add_argument("--city",         type=str,  help="도시 필터 (예: 제주)")
    parser.add_argument("--category",     type=str,  help="카테고리 필터 (예: 숙소)")
    parser.add_argument("--limit",        type=int,  default=30, help="조회 개수 (기본 30)")
    parser.add_argument("--reservations", action="store_true", help="예약 내역 조회")
    args = parser.parse_args()

    if args.reservations:
        list_reservations(args.limit)
    elif args.city or args.category:
        list_places(city=args.city, category=args.category, limit=args.limit)
    else:
        summary()
        list_places(limit=20)
