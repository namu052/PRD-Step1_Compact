"""BBS 게시판 개별 수집 기능 검증 스크립트"""
import asyncio
import sys
import warnings

if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

sys.stdout.reconfigure(encoding="utf-8")

from app.services.crawler_service import BBS_BOARDS, crawler_service


async def wait_for_olta_login(max_wait=120):
    """OLTA 로그인을 폴링으로 대기한다."""
    url = await crawler_service.open_olta_for_login()
    print(f"  브라우저 창이 열렸습니다. OLTA에 수동 로그인해 주세요.")
    print(f"  최대 {max_wait}초 대기합니다...")

    for elapsed in range(0, max_wait, 5):
        await asyncio.sleep(5)
        logged_in = await crawler_service.check_olta_login()
        if logged_in:
            print(f"  로그인 확인! ({elapsed + 5}초 경과)")
            return True
        print(f"  대기 중... ({elapsed + 5}초/{max_wait}초)")
    return False


async def main():
    print("=" * 60)
    print("BBS 게시판 개별 수집 기능 검증")
    print("=" * 60)

    print(f"\n[1] BBS_BOARDS 목록 ({len(BBS_BOARDS)}개)")
    for i, board in enumerate(BBS_BOARDS, 1):
        print(f"  {i:2d}. {board}")

    print("\n[2] 브라우저 초기화")
    ctx = await crawler_service.ensure_browser()
    print("  브라우저 OK")

    print("\n[3] OLTA 로그인 확인")
    logged_in = await crawler_service.check_olta_login()
    print(f"  로그인 상태: {logged_in}")

    if not logged_in:
        print("\n  OLTA 미로그인 - 수동 로그인 대기")
        logged_in = await wait_for_olta_login(120)

    if not logged_in:
        print("\n[SKIP] OLTA 미로그인 - BBS 검색 건너뛰기 동작 확인")
        results = await crawler_service.search(None, ["취득세 감면"], None)
        print(f"  일반 검색 결과: {len(results)}건")
        for r in results[:3]:
            print(f"    - [{r.type}] {r.title[:50]}")
        await crawler_service.close_browser()
        return

    print("\n[4] BBS 게시판 개별 검색 테스트")
    query = "취득세 감면"
    print(f"  검색어: {query}")

    bbs_cards = await crawler_service._search_all_bbs_boards(ctx, [query])
    print(f"\n  총 BBS 검색 결과: {len(bbs_cards)}건")

    # 게시판별 통계
    board_counts = {}
    for card in bbs_cards:
        board_counts[card.type] = board_counts.get(card.type, 0) + 1

    print(f"\n  게시판별 결과:")
    for board_type, count in sorted(board_counts.items()):
        print(f"    {board_type}: {count}건")

    # 결과 없는 게시판
    found_boards = {t.replace("기타/", "") for t in board_counts}
    missing_boards = set(BBS_BOARDS) - found_boards
    if missing_boards:
        print(f"\n  결과 없는 게시판 ({len(missing_boards)}개):")
        for board in sorted(missing_boards):
            print(f"    - {board}")

    # 샘플 결과 출력
    if bbs_cards:
        print(f"\n  샘플 결과 (상위 5건):")
        for card in bbs_cards[:5]:
            print(f"    [{card.type}] {card.title[:60]}")
            print(f"      URL: {card.detail_url[:80]}")

    print("\n[5] 전체 파이프라인 검색 (BBS 포함)")
    results = await crawler_service.search(None, [query], None)
    print(f"  전체 검색 결과: {len(results)}건")

    type_counts = {}
    for r in results:
        type_counts[r.type] = type_counts.get(r.type, 0) + 1

    print(f"\n  유형별 결과:")
    for rtype, count in sorted(type_counts.items()):
        print(f"    {rtype}: {count}건")

    # 댓글 수집 확인
    bbs_results = [r for r in results if r.type.startswith("기타/")]
    bbs_with_comments = [r for r in bbs_results if r.comments]
    print(f"\n  BBS 결과: {len(bbs_results)}건")
    print(f"  BBS 댓글 있는 결과: {len(bbs_with_comments)}건")
    for r in bbs_with_comments[:3]:
        print(f"    [{r.type}] {r.title[:40]}")
        print(f"      댓글: {r.comments[:100]}...")

    # BBS 결과 상세 샘플
    if bbs_results:
        print(f"\n  BBS 상세 결과 샘플 (상위 3건):")
        for r in bbs_results[:3]:
            print(f"    [{r.type}] {r.title[:60]}")
            print(f"      내용(앞100자): {r.content[:100]}...")
            print(f"      댓글: {'있음' if r.comments else '없음'}")

    await crawler_service.close_browser()
    print("\n" + "=" * 60)
    print("검증 완료!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
