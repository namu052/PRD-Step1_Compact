"""OLTA 메인 게시판 세목별 서브 탭 DOM 탐색 스크립트.

doCollection() 호출 후 나타나는 서브 탭 UI 구조를 덤프하여
Part A (세목별 서브 게시판 구현)에 필요한 셀렉터/JS 함수명을 확인한다.

Usage:
  python explore_olta_sub_boards.py
  python explore_olta_sub_boards.py "취득세 감면"
"""

import asyncio
import json
import logging
import os
import sys
import warnings
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

os.environ["PLAYWRIGHT_HEADLESS"] = "False"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("explore_sub_boards")

COLLECTION_IDS = ["ordinance", "sentencing", "screen", "evaluation", "legal", "authoritative"]

DUMP_DIR = Path("debug/sub_boards")


async def dump_sub_board_dom(page, collection_id: str, dump_dir: Path) -> dict:
    """doCollection() 호출 후 서브 탭 영역의 DOM을 덤프한다."""

    # doCollection 호출
    try:
        await page.evaluate(f"doCollection('{collection_id}')")
        await asyncio.sleep(1.5)
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception as e:
        logger.warning("doCollection('%s') failed: %s", collection_id, e)
        return {"collection_id": collection_id, "error": str(e)}

    # JS로 DOM 구조 탐색
    dom_info = await page.evaluate("""
        () => {
            const result = {
                url: location.href,
                all_tabs: [],
                all_clickable: [],
                count_elements: [],
                tab_containers: [],
            };

            // 1. 탭 컨테이너 후보 탐색
            const tabContainerSelectors = [
                '.tab_area', '.sub_tab', '.category_tab',
                '.search_tab', '.result_tab', '[class*="tab"]',
                '.tax_type', '.sub_menu', '.depth2',
            ];
            for (const sel of tabContainerSelectors) {
                const els = document.querySelectorAll(sel);
                for (const el of els) {
                    result.tab_containers.push({
                        selector: sel,
                        tag: el.tagName,
                        className: el.className,
                        id: el.id,
                        childCount: el.children.length,
                        innerText: (el.innerText || '').substring(0, 500),
                        outerHTML: el.outerHTML.substring(0, 1000),
                    });
                }
            }

            // 2. 클릭 가능한 요소들 (onclick 있는 것)
            const clickables = document.querySelectorAll('a[onclick], button[onclick], li[onclick], [onclick]');
            for (const el of clickables) {
                const onclick = el.getAttribute('onclick') || '';
                const text = (el.textContent || '').trim();
                if (text.length > 0 && text.length < 50) {
                    result.all_clickable.push({
                        tag: el.tagName,
                        text: text,
                        onclick: onclick,
                        href: el.getAttribute('href') || '',
                        className: el.className,
                    });
                }
            }

            // 3. 숫자가 포함된 요소들 (합계 카운트 후보)
            const countSelectors = ['.count', '.num', '.total', 'span', 'em', '.badge'];
            for (const sel of countSelectors) {
                const els = document.querySelectorAll(sel);
                for (const el of els) {
                    const text = (el.textContent || '').trim();
                    if (/^\d+$/.test(text) || /\(\d+\)/.test(text) || /총\s*\d+/.test(text)) {
                        result.count_elements.push({
                            selector: sel,
                            text: text,
                            parentText: (el.parentElement?.textContent || '').trim().substring(0, 100),
                            tag: el.tagName,
                            className: el.className,
                        });
                    }
                }
            }

            // 4. 알려진 세목 라벨 탐색
            const knownLabels = ['취득', '등면', '등록면허', '주민', '지소', '지방소득', '재산', '자동', '자동차', '기타'];
            const allText = document.body.innerText || '';
            result.found_labels = {};
            for (const label of knownLabels) {
                const idx = allText.indexOf(label);
                if (idx !== -1) {
                    result.found_labels[label] = allText.substring(Math.max(0, idx - 20), idx + 30);
                }
            }

            // 5. 전체 검색 결과 영역 HTML (첫 2000자)
            const contentArea = document.querySelector('#content') || document.querySelector('.contents') || document.body;
            result.content_html_snippet = contentArea.innerHTML.substring(0, 3000);

            return result;
        }
    """)

    dom_info["collection_id"] = collection_id

    # 파일로 저장
    dump_file = dump_dir / f"{collection_id}.json"
    with open(dump_file, "w", encoding="utf-8") as f:
        json.dump(dom_info, f, ensure_ascii=False, indent=2)
    logger.info("DOM dump saved: %s (%d clickables, %d tab containers)",
                dump_file, len(dom_info.get("all_clickable", [])),
                len(dom_info.get("tab_containers", [])))

    return dom_info


async def main():
    from app.config import get_settings
    get_settings.cache_clear()
    from app.services.crawler_service import crawler_service

    query = sys.argv[1] if len(sys.argv) > 1 else "장애인 감면"
    settings = get_settings()

    DUMP_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("OLTA Sub-Board DOM Explorer")
    print(f"  query      : {query}")
    print(f"  headless   : {settings.playwright_headless}")
    print(f"  dump dir   : {DUMP_DIR}")
    print("=" * 60)

    # 1. 브라우저 열기 + 로그인
    print("\n[1/3] 브라우저 열기 + 로그인 대기")
    await crawler_service.ensure_browser()
    await crawler_service.ensure_shared_page()
    logged_in = await crawler_service.check_olta_login()

    if not logged_in:
        url = await crawler_service.open_olta_for_login()
        print(f"  OLTA 페이지: {url}")
        print("  GPKI 로그인을 완료해주세요 (180초 대기)")
        await asyncio.sleep(180)
        logged_in = await crawler_service.check_olta_login()
        if not logged_in:
            print("  [FAIL] 로그인 실패")
            await crawler_service.close_browser()
            return

    print("  [OK] 로그인 확인됨")

    # 2. 통합검색 실행
    print(f"\n[2/3] 통합검색: '{query}'")
    page = await crawler_service.ensure_shared_page()
    search_url = f"{settings.olta_base_url}/main.do"
    await page.goto(search_url, wait_until="domcontentloaded")
    await asyncio.sleep(1)

    # 검색어 입력 + 검색 실행
    search_input = page.locator("input#query")
    await search_input.fill(query)
    await page.locator("a.search_icon").click()
    await asyncio.sleep(2)
    await page.wait_for_load_state("domcontentloaded", timeout=10000)
    print(f"  검색 결과 페이지: {page.url}")

    # 3. 각 collection별 DOM 덤프
    print(f"\n[3/3] collection별 서브 탭 DOM 탐색")
    summary = {}
    for cid in COLLECTION_IDS:
        print(f"\n  --- {cid} ---")
        info = await dump_sub_board_dom(page, cid, DUMP_DIR)

        found = info.get("found_labels", {})
        tabs = info.get("tab_containers", [])
        clickables = info.get("all_clickable", [])
        counts = info.get("count_elements", [])

        print(f"  tab containers: {len(tabs)}")
        print(f"  clickable elements: {len(clickables)}")
        print(f"  count elements: {len(counts)}")
        print(f"  found tax labels: {list(found.keys())}")

        summary[cid] = {
            "tab_containers": len(tabs),
            "clickables": len(clickables),
            "count_elements": len(counts),
            "found_labels": list(found.keys()),
        }

    # Summary 저장
    summary_file = DUMP_DIR / "_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"탐색 완료. 결과: {DUMP_DIR}/")
    print(f"요약: {summary_file}")
    print(f"{'=' * 60}")

    await crawler_service.close_browser()


if __name__ == "__main__":
    asyncio.run(main())
