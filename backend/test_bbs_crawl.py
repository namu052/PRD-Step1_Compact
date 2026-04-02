"""BBS 게시판 크롤링 단독 검증 스크립트.

사용법:
  python test_bbs_crawl.py              # 기본 쿼리("취득세 감면")로 테스트
  python test_bbs_crawl.py "재산세 비과세"  # 원하는 쿼리로 테스트
"""

import asyncio
import logging
import sys
import warnings

if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os

os.environ["PLAYWRIGHT_HEADLESS"] = "False"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("test_bbs")


async def main():
    from urllib.parse import urljoin

    from app.config import get_settings

    # lru_cache 초기화하여 env 변경 반영
    get_settings.cache_clear()
    from app.services.crawler_service import BBS_BOARDS, crawler_service

    query = sys.argv[1] if len(sys.argv) > 1 else "취득세 감면"
    settings = get_settings()

    print("=" * 60)
    print(f"BBS 크롤링 테스트")
    print(f"  쿼리      : {query}")
    print(f"  headless  : {settings.playwright_headless}")
    print(f"  게시판 수 : {len(BBS_BOARDS)}개")
    print(f"  게시판 목록: {', '.join(BBS_BOARDS[:5])} ...")
    print("=" * 60)

    # ── 1단계: 브라우저 열기 & 로그인 대기 (3분) ──
    print("\n[1/4] 브라우저 시작 - OLTA 로그인 페이지를 엽니다...")
    context = await crawler_service.ensure_browser()
    logged_in = await crawler_service.check_olta_login()

    if logged_in:
        print("  [OK] 이미 로그인 상태입니다.")
    else:
        url = await crawler_service.open_olta_for_login()
        print(f"  >> OLTA 페이지: {url}")
        print(f"  >> 브라우저에서 GPKI 로그인을 완료하세요.")
        print(f"  >> 3분(180초) 대기 시작...")
        await asyncio.sleep(180)
        print(f"  >> 3분 경과 - 로그인 상태 확인 중...")
        logged_in = await crawler_service.check_olta_login()

        if not logged_in:
            print("  [FAIL] 로그인 확인 실패. 종료합니다.")
            await crawler_service.close_browser()
            return

    # ── 2단계: 로그인 확인 후 단일 게시판 BBS 크롤링 ──
    test_board = BBS_BOARDS[0]
    print(f"\n[2/4] 로그인 확인 완료 - 단일 게시판 테스트: '{test_board}'")
    auth_ctx = await crawler_service.get_auth_context()
    if not auth_ctx:
        print("  [FAIL] 인증 컨텍스트 획득 실패. 종료합니다.")
        await crawler_service.close_browser()
        return

    single_results = await crawler_service._search_single_bbs_board(
        auth_ctx, query, test_board,
    )
    print(f"  >> 수집 건수: {len(single_results)}")
    for i, r in enumerate(single_results[:3]):
        print(f"  [{i+1}] {r.title[:50]}")
        print(f"      type={r.type}  url={r.url[:80]}...")
        print(f"      content={r.content[:100]}...")
        print()

    # ── 3단계: 전체 18개 게시판 테스트 ──
    if single_results:
        print(f"\n[3/4] 전체 {len(BBS_BOARDS)}개 게시판 검색 시작...")
        all_results = await crawler_service._search_all_bbs_boards(
            auth_ctx, [query],
        )
        print(f"  >> 전체 수집 건수: {len(all_results)}")

        board_counts = {}
        for r in all_results:
            board_counts[r.type] = board_counts.get(r.type, 0) + 1

        print(f"\n[4/4] 게시판별 수집 결과:")
        print("-" * 50)
        for board_type, count in sorted(board_counts.items(), key=lambda x: -x[1]):
            print(f"  {board_type:<30} : {count}건")
        print("-" * 50)
        print(f"  {'합계':<30} : {len(all_results)}건")
    else:
        print("\n[3/4] 단일 게시판 결과 0건 - 전체 검색 건너뜀")
        print("[4/4] 건너뜀")

    # 정리
    await crawler_service.close_browser()
    print("\n완료.")


if __name__ == "__main__":
    asyncio.run(main())
