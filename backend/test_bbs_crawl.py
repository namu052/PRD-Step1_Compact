"""Standalone live test for OLTA BBS crawling.

Usage:
  python test_bbs_crawl.py
  python test_bbs_crawl.py "장애인감면"
"""

import asyncio
import logging
import os
import sys
import warnings

if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

os.environ["PLAYWRIGHT_HEADLESS"] = "False"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("test_bbs")


async def main():
    from app.config import get_settings

    get_settings.cache_clear()
    from app.services.crawler_service import BBS_BOARDS, crawler_service

    query = sys.argv[1] if len(sys.argv) > 1 else "장애인감면"
    settings = get_settings()

    print("=" * 60)
    print("BBS crawl smoke test")
    print(f"  query      : {query}")
    print(f"  headless   : {settings.playwright_headless}")
    print(f"  board cnt  : {len(BBS_BOARDS)}")
    print("  sample     : omitted (console-safe output)")
    print("=" * 60)

    print("\n[1/4] Reusing shared OLTA page")
    await crawler_service.ensure_browser()
    shared_page = await crawler_service.ensure_shared_page()
    logged_in = await crawler_service.check_olta_login()

    if not logged_in:
        url = await crawler_service.open_olta_for_login()
        print(f"  open page   : {url}")
        print("  action      : complete OLTA GPKI login in the existing shared page")
        print("  wait        : 180 seconds for manual login")
        await asyncio.sleep(180)
        logged_in = await crawler_service.check_olta_login()

        if not logged_in:
            print("  [FAIL] login was not confirmed")
            await crawler_service.close_browser()
            return

    print("  [OK] login confirmed on shared page")

    print("\n[2/4] Single board test using the shared page")
    auth_ctx = await crawler_service.get_auth_context()
    if not auth_ctx:
        print("  [FAIL] authenticated browser context is unavailable")
        await crawler_service.close_browser()
        return

    test_board = BBS_BOARDS[0]
    single_results = await crawler_service._search_single_bbs_board(
        auth_ctx,
        query,
        test_board,
        page=shared_page,
    )
    print("  board       : first board in registry")
    print(f"  results     : {len(single_results)}")
    for index, result in enumerate(single_results[:3], start=1):
        print(f"  [{index}] {result.title[:60]}")
        print(f"      type={result.type}")
        print(f"      url={result.url[:120]}")

    print("\n[3/4] Full 18-board test using the same shared page")
    all_results = await crawler_service._search_all_bbs_boards(
        auth_ctx,
        [query],
        page=shared_page,
    )
    print(f"  total results: {len(all_results)}")

    print("\n[4/4] Results per board")
    board_counts: dict[str, int] = {}
    for result in all_results:
        board_counts[result.type] = board_counts.get(result.type, 0) + 1

    if not board_counts:
        print("  no BBS data was collected")
    else:
        for board_type, count in sorted(board_counts.items(), key=lambda item: (-item[1], item[0])):
            safe_label = board_type.encode("cp949", errors="replace").decode("cp949", errors="replace")
            print(f"  {safe_label:<40} {count}")

    print("\nDone.")
    await crawler_service.close_browser()


if __name__ == "__main__":
    asyncio.run(main())
