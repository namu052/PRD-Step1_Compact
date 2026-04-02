"""
OLTA BBS DOM 덤프 스크립트
- BBS 검색 결과 페이지의 실제 HTML 구조를 덤프
- 게시판 필터 영역, 게시글 링크 패턴, 결과 행 구조 확인용
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENAI_API_KEY", "test-not-needed")

DUMP_DIR = Path(__file__).parent / "debug" / "bbs_dom_dump"


def save(filename: str, content: str):
    DUMP_DIR.mkdir(parents=True, exist_ok=True)
    path = DUMP_DIR / filename
    path.write_text(content, encoding="utf-8")
    print(f"    -> 저장: {path}")


async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "장애인 감면"
    print(f"\n{'=' * 60}")
    print(f"  OLTA BBS DOM 덤프")
    print(f"  검색어: \"{query}\"")
    print(f"  출력 디렉토리: {DUMP_DIR}")
    print(f"{'=' * 60}\n")

    from app.config import get_settings, OLTA_SELECTORS
    settings = get_settings()
    settings.playwright_headless = False

    from app.services.crawler_service import CrawlerService
    crawler = CrawlerService()

    try:
        # 1. 브라우저 + 로그인
        print("  [1] 브라우저 시작...")
        await crawler.ensure_browser()
        print("  [1] 완료\n")

        print("  [2] OLTA 로그인 확인 (3분 대기 후 10초x6회 확인)...")
        logged_in = await crawler.check_olta_login()
        if not logged_in:
            print("      OLTA에 로그인해주세요. 3분 대기합니다...")
            await crawler.bring_browser_to_front()
            await asyncio.sleep(180)
            for i in range(6):
                try:
                    logged_in = await crawler.check_olta_login()
                except Exception:
                    logged_in = False
                if logged_in:
                    break
                print(f"      확인 {i+1}/6 - 미로그인 (10초 후 재시도)")
                if i < 5:
                    await asyncio.sleep(10)

        if not logged_in:
            print("  [2] 미로그인. BBS 페이지 접근이 제한될 수 있습니다.\n")
        else:
            print("  [2] 로그인 확인 완료\n")

        # 2. BBS 검색 페이지로 이동
        context = crawler._shared_context
        page = await context.new_page()
        page.set_default_timeout(15000)

        from urllib.parse import urljoin
        bbs_url = urljoin(settings.olta_base_url, OLTA_SELECTORS["bbs"]["entry_url"])
        print(f"  [3] BBS 페이지 이동: {bbs_url}")
        await page.goto(bbs_url, wait_until="domcontentloaded")
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        print(f"      현재 URL: {page.url}\n")

        # ─── 덤프 A: 초기 페이지 (검색 전) ───
        print("  [4] 덤프 A: 초기 BBS 페이지 (검색 전)")
        save("A_initial_full_html.html", await page.content())

        # 게시판 필터 영역 덤프
        board_filter_dump = await page.evaluate("""
            () => {
                const results = {
                    select_elements: [],
                    radio_elements: [],
                    checkbox_elements: [],
                    onclick_doBrdNm: [],
                    all_forms: [],
                };

                // select 요소
                document.querySelectorAll('select').forEach((sel) => {
                    const options = [];
                    sel.querySelectorAll('option').forEach((opt) => {
                        options.push({
                            text: (opt.textContent || '').trim(),
                            value: opt.value || '',
                            selected: opt.selected,
                        });
                    });
                    results.select_elements.push({
                        name: sel.name || '',
                        id: sel.id || '',
                        className: sel.className || '',
                        parent_html: sel.parentElement?.outerHTML?.substring(0, 500) || '',
                        options: options,
                    });
                });

                // radio/checkbox
                document.querySelectorAll("input[type='radio'], input[type='checkbox']").forEach((inp) => {
                    const label = inp.id
                        ? document.querySelector('label[for="' + inp.id + '"]')
                        : null;
                    const wrappedLabel = inp.closest('label');
                    const parentHTML = inp.parentElement?.outerHTML?.substring(0, 500) || '';
                    results.radio_elements.push({
                        type: inp.type,
                        name: inp.name || '',
                        value: inp.value || '',
                        id: inp.id || '',
                        checked: inp.checked,
                        label_text: label?.textContent?.trim() || wrappedLabel?.textContent?.trim() || '',
                        parent_tag: inp.parentElement?.tagName || '',
                        parent_class: inp.parentElement?.className || '',
                        parent_html: parentHTML,
                    });
                });

                // doBrdNmCollection onclick 요소
                document.querySelectorAll("[onclick*='doBrdNmCollection']").forEach((el) => {
                    results.onclick_doBrdNm.push({
                        tag: el.tagName,
                        text: (el.textContent || '').trim(),
                        onclick: el.getAttribute('onclick') || '',
                        class: el.className || '',
                        parent_html: el.parentElement?.outerHTML?.substring(0, 300) || '',
                    });
                });

                // 폼 요소
                document.querySelectorAll('form').forEach((form) => {
                    const inputs = [];
                    form.querySelectorAll('input, select').forEach((inp) => {
                        inputs.push({
                            tag: inp.tagName,
                            name: inp.name || '',
                            type: inp.type || '',
                            value: (inp.value || '').substring(0, 100),
                        });
                    });
                    results.all_forms.push({
                        action: form.action || '',
                        method: form.method || '',
                        id: form.id || '',
                        name: form.name || '',
                        input_count: inputs.length,
                        inputs: inputs.slice(0, 30),
                    });
                });

                return results;
            }
        """)
        save("A_board_filters.json", json.dumps(board_filter_dump, ensure_ascii=False, indent=2))
        print(f"      select: {len(board_filter_dump['select_elements'])}개, "
              f"radio/checkbox: {len(board_filter_dump['radio_elements'])}개, "
              f"doBrdNmCollection: {len(board_filter_dump['onclick_doBrdNm'])}개\n")

        # ─── 덤프 B: 검색 실행 후 ───
        print(f"  [5] 검색 실행: \"{query}\"")
        await page.fill(OLTA_SELECTORS["bbs"]["search_input"], query)
        await page.evaluate(OLTA_SELECTORS["bbs"]["search_button_js"])
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        await asyncio.sleep(1)
        print(f"      검색 후 URL: {page.url}\n")

        print("  [6] 덤프 B: 검색 결과 페이지 (필터 전)")
        save("B_search_result_full.html", await page.content())

        # 검색 결과의 모든 링크 덤프
        all_links_dump = await page.evaluate("""
            () => {
                const links = [];
                document.querySelectorAll('a').forEach((a, i) => {
                    const href = a.getAttribute('href') || '';
                    const onclick = a.getAttribute('onclick') || '';
                    const target = a.getAttribute('target') || '';
                    const text = (a.textContent || '').replace(/\\s+/g, ' ').trim();
                    if (!text && !href && !onclick) return;
                    // 부모 컨테이너 정보
                    const parent = a.parentElement;
                    const grandparent = parent?.parentElement;
                    links.push({
                        index: i,
                        text: text.substring(0, 100),
                        href: href.substring(0, 200),
                        onclick: onclick.substring(0, 300),
                        target: target,
                        tag_path: [
                            grandparent?.tagName + '.' + (grandparent?.className || '').substring(0, 30),
                            parent?.tagName + '.' + (parent?.className || '').substring(0, 30),
                            'A'
                        ].join(' > '),
                        outer_html: a.outerHTML.substring(0, 400),
                    });
                });
                return links;
            }
        """)
        save("B_all_links.json", json.dumps(all_links_dump, ensure_ascii=False, indent=2))
        print(f"      전체 링크: {len(all_links_dump)}개\n")

        # 결과 행(row) 구조 덤프
        row_dump = await page.evaluate("""
            () => {
                const results = { containers: [] };
                const selectors = ['.search_list', '.result_list', '.board_list', '.contents', '#content'];
                for (const sel of selectors) {
                    const containers = document.querySelectorAll(sel);
                    containers.forEach((container, ci) => {
                        const rows = [];
                        // li 행들
                        container.querySelectorAll(':scope > ul > li, :scope > ol > li, :scope li').forEach((li, ri) => {
                            if (ri >= 5) return; // 상위 5개만
                            const links = [];
                            li.querySelectorAll('a').forEach((a) => {
                                links.push({
                                    text: (a.textContent || '').replace(/\\s+/g, ' ').trim().substring(0, 100),
                                    href: (a.getAttribute('href') || '').substring(0, 200),
                                    onclick: (a.getAttribute('onclick') || '').substring(0, 300),
                                    target: a.getAttribute('target') || '',
                                    class: a.className || '',
                                });
                            });
                            rows.push({
                                row_index: ri,
                                text: (li.textContent || '').replace(/\\s+/g, ' ').trim().substring(0, 200),
                                inner_html: li.innerHTML.substring(0, 800),
                                link_count: links.length,
                                links: links,
                            });
                        });
                        if (rows.length > 0) {
                            results.containers.push({
                                selector: sel,
                                container_index: ci,
                                class: container.className || '',
                                row_count: rows.length,
                                rows: rows,
                            });
                        }
                    });
                }
                return results;
            }
        """)
        save("B_result_rows.json", json.dumps(row_dump, ensure_ascii=False, indent=2))

        # ─── 덤프 C: 특정 BBS 게시판 필터 적용 후 ───
        test_board = "질의응답"
        print(f"  [7] 게시판 필터 적용: \"{test_board}\"")
        try:
            await page.evaluate(
                "(payload) => doBrdNmCollection(payload.value, 'bbs')",
                {"value": test_board},
            )
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            await asyncio.sleep(1)
            print(f"      필터 후 URL: {page.url}\n")
        except Exception as e:
            print(f"      필터 실패: {e}\n")

        print(f"  [8] 덤프 C: \"{test_board}\" 필터 적용 후")
        save("C_filtered_board_full.html", await page.content())

        # 필터 후 링크 덤프
        filtered_links = await page.evaluate("""
            () => {
                const links = [];
                document.querySelectorAll('a').forEach((a, i) => {
                    const href = a.getAttribute('href') || '';
                    const onclick = a.getAttribute('onclick') || '';
                    const text = (a.textContent || '').replace(/\\s+/g, ' ').trim();
                    if (!text && !href && !onclick) return;
                    const parent = a.parentElement;
                    const gp = parent?.parentElement;
                    links.push({
                        index: i,
                        text: text.substring(0, 100),
                        href: href.substring(0, 200),
                        onclick: onclick.substring(0, 300),
                        target: a.getAttribute('target') || '',
                        tag_path: [
                            gp?.tagName + '.' + (gp?.className || '').substring(0, 30),
                            parent?.tagName + '.' + (parent?.className || '').substring(0, 30),
                            'A'
                        ].join(' > '),
                        outer_html: a.outerHTML.substring(0, 400),
                    });
                });
                return links;
            }
        """)
        save("C_filtered_links.json", json.dumps(filtered_links, ensure_ascii=False, indent=2))
        print(f"      필터 후 링크: {len(filtered_links)}개\n")

        # 필터 후 결과 행 구조
        filtered_rows = await page.evaluate("""
            () => {
                const results = { containers: [] };
                const selectors = ['.search_list', '.result_list', '.board_list', '.contents', '#content'];
                for (const sel of selectors) {
                    const containers = document.querySelectorAll(sel);
                    containers.forEach((container, ci) => {
                        const rows = [];
                        container.querySelectorAll(':scope > ul > li, :scope > ol > li, :scope li').forEach((li, ri) => {
                            if (ri >= 5) return;
                            const links = [];
                            li.querySelectorAll('a').forEach((a) => {
                                links.push({
                                    text: (a.textContent || '').replace(/\\s+/g, ' ').trim().substring(0, 100),
                                    href: (a.getAttribute('href') || '').substring(0, 200),
                                    onclick: (a.getAttribute('onclick') || '').substring(0, 300),
                                    target: a.getAttribute('target') || '',
                                });
                            });
                            rows.push({
                                row_index: ri,
                                text: (li.textContent || '').replace(/\\s+/g, ' ').trim().substring(0, 200),
                                inner_html: li.innerHTML.substring(0, 800),
                                link_count: links.length,
                                links: links,
                            });
                        });
                        if (rows.length > 0) {
                            results.containers.push({
                                selector: sel,
                                container_index: ci,
                                class: container.className || '',
                                row_count: rows.length,
                                rows: rows,
                            });
                        }
                    });
                }
                return results;
            }
        """)
        save("C_filtered_rows.json", json.dumps(filtered_rows, ensure_ascii=False, indent=2))

        # ─── 덤프 D: 게시글 클릭 시도 (첫 번째 결과) ───
        print("  [9] 덤프 D: 첫 번째 결과 링크 클릭 시도")
        # bbsPopUp 또는 bbsId/nttId가 포함된 링크 찾기
        bbs_links_info = await page.evaluate("""
            () => {
                const candidates = [];
                document.querySelectorAll('a').forEach((a, i) => {
                    const href = a.getAttribute('href') || '';
                    const onclick = a.getAttribute('onclick') || '';
                    const text = (a.textContent || '').replace(/\\s+/g, ' ').trim();
                    const hasBbs = /bbsId|nttId|bbsPopUp|view\.do|selectBoard/i.test(href + onclick);
                    const isArticle = text.length >= 5 && !/^\\d+$/.test(text);
                    if (hasBbs || (isArticle && (href || onclick))) {
                        candidates.push({
                            index: i,
                            text: text.substring(0, 100),
                            href: href.substring(0, 300),
                            onclick: onclick.substring(0, 300),
                            target: a.getAttribute('target') || '',
                            has_bbs_id: hasBbs,
                            outer_html: a.outerHTML.substring(0, 500),
                        });
                    }
                });
                return candidates;
            }
        """)
        save("D_bbs_article_candidates.json", json.dumps(bbs_links_info, ensure_ascii=False, indent=2))
        print(f"      게시글 링크 후보: {len(bbs_links_info)}개")

        # BBS 식별자 있는 링크만 필터링
        bbs_identified = [l for l in bbs_links_info if l.get("has_bbs_id")]
        print(f"      bbsId/nttId 포함 링크: {len(bbs_identified)}개")
        if bbs_identified:
            for l in bbs_identified[:5]:
                print(f"        - [{l['index']}] \"{l['text'][:40]}\" onclick={l['onclick'][:80]}")

        # ─── 덤프 E: JavaScript 함수 목록 ───
        print("\n  [10] 덤프 E: 페이지 JS 함수 목록")
        js_functions = await page.evaluate("""
            () => {
                const fns = [];
                // window 레벨 함수 중 bbs/board/collection 관련
                for (const key in window) {
                    try {
                        if (typeof window[key] === 'function') {
                            const name = key.toLowerCase();
                            if (name.includes('bbs') || name.includes('board') ||
                                name.includes('collection') || name.includes('popup') ||
                                name.includes('paging') || name.includes('search') ||
                                name.includes('view') || name.includes('detail') ||
                                name.includes('ntt') || name.includes('egov')) {
                                fns.push({
                                    name: key,
                                    source_preview: window[key].toString().substring(0, 300),
                                });
                            }
                        }
                    } catch(e) {}
                }
                return fns;
            }
        """)
        save("E_js_functions.json", json.dumps(js_functions, ensure_ascii=False, indent=2))
        print(f"      BBS 관련 JS 함수: {len(js_functions)}개")
        for fn in js_functions[:10]:
            print(f"        - {fn['name']}()")

        await page.close()

        # ─── 요약 ───
        print(f"\n{'=' * 60}")
        print(f"  DOM 덤프 완료!")
        print(f"  출력 디렉토리: {DUMP_DIR}")
        print(f"  생성 파일:")
        for f in sorted(DUMP_DIR.iterdir()):
            size_kb = f.stat().st_size / 1024
            print(f"    {f.name:40} {size_kb:6.1f} KB")
        print(f"{'=' * 60}\n")

    except Exception as e:
        print(f"\n  [ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        await crawler.close_browser()


if __name__ == "__main__":
    asyncio.run(main())
