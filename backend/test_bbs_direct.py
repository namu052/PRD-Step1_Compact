"""OLTA BBS 직접 검색 진단 - 브라우저 열어서 수동 로그인 후 BBS 검색 테스트"""
import asyncio
import sys
import time
import warnings

if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

sys.stdout.reconfigure(encoding="utf-8")

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

from app.services.crawler_service import BBS_BOARDS, crawler_service


async def main():
    print("=" * 70)
    print("BBS 직접 검색 진단")
    print("=" * 70)

    # 1. 브라우저 시작 + OLTA 로그인 대기
    print("\n[1] 브라우저 초기화 (headless=false)")
    ctx = await crawler_service.ensure_browser()

    logged_in = await crawler_service.check_olta_login()
    if not logged_in:
        print("  OLTA 미로그인 - 브라우저 창에서 로그인해 주세요")
        await crawler_service.open_olta_for_login()
        for i in range(60):
            await asyncio.sleep(5)
            logged_in = await crawler_service.check_olta_login()
            print(f"  대기 중... ({(i+1)*5}초) 로그인={logged_in}")
            if logged_in:
                break
        if not logged_in:
            print("  로그인 실패. 종료합니다.")
            await crawler_service.close_browser()
            return

    print(f"  OLTA 로그인 확인: {logged_in}")

    # 2. 단일 게시판 BBS 검색 진단 (상세 로그 포함)
    print(f"\n[2] 단일 게시판 검색 진단")
    query = "취득세 감면"
    test_boards = ["질의응답", "지방세상담", "FAQ"]

    for board_name in test_boards:
        print(f"\n  ── {board_name} ──")
        start = time.time()
        try:
            cards = await crawler_service._search_single_bbs_board(ctx, query, board_name)
            elapsed = round(time.time() - start, 1)
            print(f"  결과: {len(cards)}건 ({elapsed}초)")
            for card in cards[:3]:
                print(f"    [{card.type}] {card.title[:60]}")
                print(f"      ID: {card.id}")
                print(f"      URL: {card.detail_url[:80]}")
        except Exception as e:
            elapsed = round(time.time() - start, 1)
            print(f"  오류: {e} ({elapsed}초)")

    # 3. doBrdNmCollection 호출 진단
    print(f"\n[3] doBrdNmCollection JS 함수 진단")
    page = await ctx.new_page()
    try:
        from urllib.parse import urljoin
        from app.config import get_settings, OLTA_SELECTORS
        settings = get_settings()

        search_url = urljoin(settings.olta_base_url, "/search/PU_0003_search.jsp")
        await page.goto(search_url, wait_until="domcontentloaded")
        await page.fill("input#queryPu", query)
        await page.evaluate("doSearchPu()")
        await page.wait_for_load_state("networkidle")

        # doBrdNmCollection 함수 존재 여부 확인
        fn_exists = await page.evaluate("typeof doBrdNmCollection === 'function'")
        print(f"  doBrdNmCollection 존재: {fn_exists}")

        # 사용 가능한 collection 값 확인
        collections = await page.evaluate("""
            () => {
                const radios = document.querySelectorAll('input[name=rd_detail_search_type]');
                return Array.from(radios).map(r => ({value: r.value, id: r.id, checked: r.checked}));
            }
        """)
        print(f"  사용 가능한 collection 라디오:")
        for c in collections:
            print(f"    value={c['value']}, id={c['id']}, checked={c['checked']}")

        # BBS 관련 폼 필드 확인
        form_fields = await page.evaluate("""
            () => {
                const f = document.search || document.forms[0];
                if (!f) return {error: 'form not found'};
                return {
                    hasCollection: !!f.collection,
                    collectionValue: f.collection?.value || '',
                    hasBbsNm: !!f.bbsNm,
                    bbsNmValue: f.bbsNm?.value || '',
                    hasDetailSearch: !!f.detailSearchIsOnOff,
                    detailSearchValue: f.detailSearchIsOnOff?.value || '',
                    formName: f.name || f.id || 'unknown',
                };
            }
        """)
        print(f"  폼 필드 정보: {form_fields}")

        # doBrdNmCollection 호출 전 상태 캡처
        if fn_exists:
            # 먼저 빈 문자열로 BBS 전체 검색
            print(f"\n  doBrdNmCollection('','bbs') 호출 테스트:")
            await page.evaluate("doBrdNmCollection('','bbs')")
            try:
                await page.wait_for_selector(
                    OLTA_SELECTORS["search"]["result_title_links"],
                    timeout=8000,
                )
                bbs_all_count = await page.locator(
                    OLTA_SELECTORS["search"]["result_title_links"]
                ).count()
                print(f"    BBS 전체 결과: {bbs_all_count}건")
            except Exception as e:
                print(f"    BBS 전체 결과: 셀렉터 대기 실패 - {e}")
                # 페이지 내용 확인
                body = await page.locator("body").inner_text()
                print(f"    페이지 내용(앞200자): {body[:200]}")

            # 게시판별 검색 테스트
            for board_name in ["질의응답", "지방세상담"]:
                print(f"\n  doBrdNmCollection('{board_name}','bbs') 호출:")
                # 새로 검색 페이지로 이동
                await page.goto(search_url, wait_until="domcontentloaded")
                await page.fill("input#queryPu", query)
                await page.evaluate("doSearchPu()")
                await page.wait_for_load_state("networkidle")

                try:
                    await page.evaluate(f"doBrdNmCollection('{board_name}','bbs')")
                    await page.wait_for_selector(
                        OLTA_SELECTORS["search"]["result_title_links"],
                        timeout=8000,
                    )
                    count = await page.locator(
                        OLTA_SELECTORS["search"]["result_title_links"]
                    ).count()
                    print(f"    결과: {count}건")

                    if count > 0:
                        # 첫 번째 결과 상세 확인
                        first = await page.locator(
                            OLTA_SELECTORS["search"]["result_title_links"]
                        ).first.evaluate("""
                            (link) => ({
                                title: link.textContent?.trim(),
                                onclick: link.getAttribute('onclick'),
                            })
                        """)
                        print(f"    첫 결과: {first['title'][:60]}")
                        print(f"    onclick: {first['onclick'][:100]}")
                except Exception as e:
                    print(f"    오류: {e}")
                    body = await page.locator("body").inner_text()
                    # "검색결과가 없습니다" 등의 메시지 확인
                    if "검색결과" in body or "없습니다" in body:
                        print(f"    → 검색 결과 없음 메시지 확인")
                    else:
                        print(f"    페이지 내용(앞200자): {body[:200]}")
        else:
            print("  doBrdNmCollection 함수가 없습니다! 대안 탐색 필요.")
            # 페이지에서 BBS 관련 JS 함수 찾기
            bbs_functions = await page.evaluate("""
                () => {
                    const fns = [];
                    for (const key of Object.keys(window)) {
                        if (typeof window[key] === 'function' &&
                            (key.toLowerCase().includes('bbs') ||
                             key.toLowerCase().includes('brd') ||
                             key.toLowerCase().includes('board') ||
                             key.toLowerCase().includes('collection'))) {
                            fns.push(key);
                        }
                    }
                    return fns;
                }
            """)
            print(f"  BBS/Board 관련 JS 함수: {bbs_functions}")

    finally:
        await page.close()

    # 4. 전체 18개 게시판 검색 (로그인 상태)
    print(f"\n[4] 전체 18개 게시판 검색")
    start = time.time()
    all_cards = await crawler_service._search_all_bbs_boards(ctx, [query])
    total = round(time.time() - start, 1)

    print(f"  총 결과: {len(all_cards)}건 ({total}초)")

    board_counts = {}
    for card in all_cards:
        board_counts[card.type] = board_counts.get(card.type, 0) + 1

    if board_counts:
        print(f"\n  게시판별 결과:")
        for btype, count in sorted(board_counts.items()):
            print(f"    {btype}: {count}건")
    else:
        print(f"  결과 없음 - BBS 검색이 작동하지 않고 있습니다")

    # 5. 상세 + 댓글 수집 테스트
    if all_cards:
        print(f"\n[5] 상세 페이지 + 댓글 수집 (상위 3건)")
        test_cards = all_cards[:3]
        details = await crawler_service._collect_details(ctx, test_cards)
        for d in details:
            print(f"  [{d.type}] {d.title[:50]}")
            print(f"    내용: {len(d.content)}자")
            print(f"    댓글: {'있음 - ' + d.comments[:100] if d.comments else '없음'}")

    await crawler_service.close_browser()
    print(f"\n{'=' * 70}")
    print("진단 완료")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(main())
