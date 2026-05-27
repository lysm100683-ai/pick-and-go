"""
scripts/collect_domestic.py — 국내 도시 장소 데이터 수집 → Supabase 저장

수집 소스: Kakao Local API 전용 (Google 제외 — API 비용 절감)
  - Kakao: 무료, 한국어 장소명 정확, 평점/리뷰 미제공(0으로 저장)
  - rating=0 이어도 일정 생성(scoring_service)은 정상 동작

사용법:
    # 단일 도시
    python -X utf8 scripts/collect_domestic.py --city 서울
    python -X utf8 scripts/collect_domestic.py --city 제주 부산 강릉

    # 전체 29개 도시 (순서대로 실행)
    python -X utf8 scripts/collect_domestic.py --all

    # 미리보기 (DB 삽입 없음)
    python -X utf8 scripts/collect_domestic.py --city 서울 --dry-run

지원 도시 (KOREAN_CITIES 전체):
    서울, 부산, 제주, 인천, 대구, 대전, 광주, 울산, 수원, 강릉,
    경주, 전주, 여수, 속초, 춘천, 가평, 양평, 포항, 거제, 남해,
    통영, 군산, 목포, 순천, 안동, 청주, 충주, 천안, 세종

DB 삽입 방식:
    - backend_postgres.fetch_kakao() 재사용
    - ON CONFLICT (id) DO NOTHING → 중복 삽입 무시, 재실행 안전
"""

import sys
import os
import io
import time
import argparse

# Windows 터미널 한글 깨짐 방지
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
elif hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from travel_logic.config.settings import KOREAN_CITIES
from backend_postgres import fetch_kakao


# ──────────────────────────────────────────────────────────────
#  수집 키워드 설정
#  Kakao keyword 검색: "도시명 + 키워드" 조합으로 호출됨
#  키워드당 최대 45건 (3페이지 × 15건)
#  8개 키워드 → 도시당 최대 360건
# ──────────────────────────────────────────────────────────────
DOMESTIC_KEYWORDS = [
    "맛집",        # 음식점 (FD6) — 가장 많은 결과
    "카페",        # 카페/디저트 (CE7)
    "관광지",      # 관광명소 (AT4)
    "박물관",      # 문화시설 (CT1) — 미술관 포함
    "호텔",        # 숙박 (AD5)
    "펜션",        # 숙박 (AD5) — 펜션·게스트하우스
    "공원",        # 자연경관
    "쇼핑",        # 쇼핑·시장
]

# 도시별 OSM 수집 병행 권고 (이 스크립트는 Kakao만)
# OSM: python -X utf8 scripts/collect_overseas.py --source osm --city 서울 --limit 3000


def collect_city(city: str, dry_run: bool = False) -> dict:
    """
    단일 도시의 Kakao 장소 데이터 수집.

    Args:
        city: 수집할 도시명 (KOREAN_CITIES 내 도시)
        dry_run: True면 DB 삽입 없이 예상 건수만 출력

    Returns:
        {"city": str, "added": int, "updated": int, "error": str|None}
    """
    if city not in KOREAN_CITIES:
        print(f"  ⚠️ '{city}'는 지원 도시 목록(KOREAN_CITIES)에 없습니다. 계속 진행합니다.")

    if dry_run:
        print(f"  [DRY-RUN] '{city}' — Kakao 키워드 {len(DOMESTIC_KEYWORDS)}개 × 최대 45건 = 최대 {len(DOMESTIC_KEYWORDS)*45}건")
        return {"city": city, "added": 0, "updated": 0, "error": None}

    # 키워드에 도시명 prefix 추가 ("서울 맛집", "서울 카페" 등)
    prefixed_keywords = [f"{city} {kw}" for kw in DOMESTIC_KEYWORDS]

    result = fetch_kakao(city, prefixed_keywords)
    return {
        "city":    city,
        "added":   result.get("added_count", 0),
        "updated": result.get("updated_count", 0),
        "error":   result.get("error"),
    }


def main():
    parser = argparse.ArgumentParser(
        description="국내 도시 장소 데이터 수집 (Kakao 전용)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python -X utf8 scripts/collect_domestic.py --city 서울
  python -X utf8 scripts/collect_domestic.py --city 제주 부산 강릉
  python -X utf8 scripts/collect_domestic.py --all
  python -X utf8 scripts/collect_domestic.py --city 서울 --dry-run
        """
    )
    parser.add_argument("--city",    nargs="+",      help="수집할 도시명 (복수 입력 가능)")
    parser.add_argument("--all",     action="store_true", help="KOREAN_CITIES 29개 전체 수집")
    parser.add_argument("--dry-run", action="store_true", help="DB 삽입 없이 예상 건수만 출력")
    args = parser.parse_args()

    if not args.city and not args.all:
        parser.print_help()
        sys.exit(1)

    cities = KOREAN_CITIES if args.all else args.city

    print(f"\n{'='*55}")
    print(f"  픽앤고 국내 도시 데이터 수집 (Kakao)")
    print(f"  대상 도시: {len(cities)}개  |  키워드: {len(DOMESTIC_KEYWORDS)}개")
    if args.dry_run:
        print(f"  [DRY-RUN 모드 — DB 삽입 없음]")
    print(f"{'='*55}\n")

    total_added   = 0
    total_updated = 0
    results       = []

    for i, city in enumerate(cities, 1):
        print(f"[{i:02d}/{len(cities)}] {city} 수집 중...")
        t0 = time.time()

        r = collect_city(city, dry_run=args.dry_run)
        elapsed = time.time() - t0

        results.append(r)
        total_added   += r["added"]
        total_updated += r["updated"]

        status = "✅" if not r["error"] else "❌"
        print(f"       {status} 신규: {r['added']:,}건, 갱신: {r['updated']:,}건  ({elapsed:.1f}s)")

        if r["error"]:
            print(f"       오류: {r['error']}")

        # Kakao API rate limit 방지 (도시 간 0.5초 대기)
        if i < len(cities):
            time.sleep(0.5)

    # 최종 요약
    print(f"\n{'='*55}")
    print(f"  수집 완료 요약")
    print(f"{'='*55}")
    print(f"  총 신규: {total_added:,}건")
    print(f"  총 갱신: {total_updated:,}건")
    print(f"  도시별:")
    for r in results:
        mark = "✅" if not r["error"] else "❌"
        print(f"    {mark} {r['city']:<10} 신규 {r['added']:>4,}건")
    print(f"\n  ✔ 완료. 'python -X utf8 scripts/db_viewer.py' 로 현황 확인\n")


if __name__ == "__main__":
    main()
