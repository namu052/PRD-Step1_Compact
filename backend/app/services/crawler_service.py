import asyncio
import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

from playwright.async_api import BrowserContext, Page, async_playwright

from app.config import OLTA_SELECTORS, get_settings
from app.models.schemas import CrawlResult


BBS_BOARDS = [
    "질의응답",
    "지방세상담",
    "추진계획서",
    "실무편람",
    "자유게시판",
    "발표자료",
    "기타자료",
    "이용안내 Q&A",
    "매뉴얼",
    "공지사항",
    "시가표준액 조정기준",
    "참고자료",
    "전국단위사건 알림방",
    "FAQ",
    "시가표준액 부동산시장동향",
    "쟁송사무지원사례",
    "쟁송사무워크숍 자료",
    "지방자치단체 소통마당",
]

POPUP_TYPE_MAP = {
    "legalPopUp": "법제처 유권해석",
    "authoritativePopUp": "행안부 유권해석",
    "screenPopUp": "조세심판원 결정례",
    "decisionDtlpopUp": "법원 판례",
    "evaluationPopUp": "감사원 심사결정례",
    "constitutionPopUp": "헌법재판소 결정례",
    "bbsPopUp": "기타",
}

POPUP_URL_BUILDERS = {
    "legalPopUp": lambda args: f"/explainInfo/lawInterpretationDetail.do?num={args[0]}",
    "authoritativePopUp": lambda args: f"/explainInfo/authoInterpretationDetail.do?num={args[0]}",
    "screenPopUp": lambda args: f"/explainInfo/judgeDecisionDetail.do?num={args[0]}",
    "evaluationPopUp": lambda args: f"/explainInfo/dlbDcnDetail.do?num={args[0]}",
    "constitutionPopUp": lambda args: f"/explainInfo/constitutionDcnDetail.do?num={args[0]}",
    "decisionDtlpopUp": (
        lambda args: (
            f"/explainInfo/detailView/decisionDtlView.do?num={args[1]}"
            f"&relationshipNum={args[0]}&srchWrd={args[2]}"
        )
    ),
}

COLLECTION_TYPE_MAP = {
    "law_search": {"법제처 유권해석", "행안부 유권해석"},
    "interpret_search": {"법제처 유권해석", "행안부 유권해석", "조세심판원 결정례", "감사원 심사결정례"},
    "case_search": {"법원 판례", "헌법재판소 결정례", "조세심판원 결정례"},
}

COLLECTION_IDS = {
    "law_search": ["legal", "authoritative"],
    "interpret_search": ["legal", "authoritative", "screen", "evaluation"],
    "case_search": ["ordinance", "sentencing", "screen"],
}

DEFAULT_COLLECTION_IDS = ["ordinance", "sentencing", "screen", "evaluation", "legal", "authoritative"]


@dataclass
class SearchCard:
    id: str
    title: str
    preview: str
    type: str
    meta: str
    detail_url: str
    relevance_score: float
    document_year: int | None = None


class CrawlerService:
    _shared_browser = None
    _shared_context: BrowserContext | None = None
    _olta_logged_in: bool = False

    async def ensure_browser(self):
        """공유 브라우저와 컨텍스트를 확보한다."""
        if self._shared_browser is None or not self._shared_browser.is_connected():
            pw = await async_playwright().start()
            settings = get_settings()
            self._shared_browser = await pw.chromium.launch(headless=settings.playwright_headless)
            self._shared_context = await self._shared_browser.new_context()
            self._olta_logged_in = False
        return self._shared_context

    async def check_olta_login(self) -> bool:
        """OLTA 로그인 상태를 확인한다."""
        context = await self.ensure_browser()
        page = await context.new_page()
        try:
            settings = get_settings()
            await page.goto(
                urljoin(settings.olta_base_url, "/main.do"),
                wait_until="domcontentloaded",
                timeout=10000,
            )
            logged_in = await page.evaluate("""
                () => {
                    const body = document.body.innerText || '';
                    // 로그아웃 버튼이 있으면 로그인 상태
                    const logoutLink = document.querySelector('a[href*="logout"], a[onclick*="logout"]');
                    if (logoutLink) return true;
                    if (body.includes('로그아웃')) return true;
                    // 로그인 버튼만 있으면 미로그인
                    if (body.includes('로그인') && !body.includes('로그아웃')) return false;
                    return false;
                }
            """)
            self._olta_logged_in = logged_in
            return logged_in
        except Exception:
            logger.warning("OLTA 로그인 확인 실패", exc_info=True)
            self._olta_logged_in = False
            return False
        finally:
            await page.close()

    async def open_olta_for_login(self) -> str:
        """수동 로그인을 위해 OLTA 페이지를 브라우저에 연다. 페이지 URL을 반환."""
        context = await self.ensure_browser()
        settings = get_settings()
        page = await context.new_page()
        login_url = urljoin(settings.olta_base_url, "/main.do")
        await page.goto(login_url, wait_until="domcontentloaded")
        # 페이지를 열어둔 채로 반환 (사용자가 수동 로그인)
        return login_url

    async def get_auth_context(self) -> BrowserContext | None:
        """로그인된 브라우저 컨텍스트를 반환. 미로그인이면 None."""
        if self._olta_logged_in:
            return self._shared_context
        # 한번 더 확인
        if await self.check_olta_login():
            return self._shared_context
        return None

    async def close_browser(self) -> None:
        """공유 브라우저를 종료한다."""
        if self._shared_context:
            try:
                await self._shared_context.close()
            except Exception:
                pass
            self._shared_context = None
        if self._shared_browser:
            try:
                await self._shared_browser.close()
            except Exception:
                pass
            self._shared_browser = None
        self._olta_logged_in = False

    async def search(self, session, queries: list[str], categories: list[str] | None = None) -> list[CrawlResult]:
        try:
            context = await self.ensure_browser()
            return await self._real_search(queries, categories, context)
        except Exception:
            logger.warning("OLTA 크롤링 실패, 빈 결과 반환", exc_info=True)
            return []

    async def _real_search(
        self,
        queries: list[str],
        categories: list[str] | None = None,
        context: BrowserContext | None = None,
    ) -> list[CrawlResult]:
        settings = get_settings()
        if not queries:
            return []

        page = await context.new_page()
        page.set_default_timeout(settings.playwright_timeout)
        try:
            cards_by_id: dict[str, SearchCard] = {}
            for index, query in enumerate(queries):
                if index > 0 and len(cards_by_id) >= settings.olta_max_detail_fetch * 3:
                    break

                if settings.olta_max_pages_per_collection is None:
                    query_page_limit = None
                elif index == 0:
                    query_page_limit = settings.olta_max_pages_per_collection
                else:
                    query_page_limit = max(2, settings.olta_max_pages_per_collection // 2)
                cards = await self._collect_query_cards(page, query, categories, query_page_limit)
                for card in cards:
                    existing = cards_by_id.get(card.id)
                    if not existing or card.relevance_score > existing.relevance_score:
                        cards_by_id[card.id] = card

            ranked_cards = sorted(cards_by_id.values(), key=lambda item: item.relevance_score, reverse=True)
            limited_cards = ranked_cards[: settings.olta_max_detail_fetch]
            details = await self._collect_details(context, limited_cards)

            # 로그인 상태이면 18개 개별 BBS 게시판 검색 (링크 클릭 → 상세 수집)
            if self._olta_logged_in:
                bbs_results = await self._search_all_bbs_boards(context, queries[:2])
                detail_ids = {d.id for d in details}
                for result in bbs_results:
                    if result.id not in detail_ids:
                        details.append(result)
                        detail_ids.add(result.id)
            else:
                logger.info("인증 세션 없음 - 기타(BBS) 게시판 검색 건너뜀")
        finally:
            await page.close()

        return sorted(details, key=lambda item: item.relevance_score, reverse=True)

    async def _collect_query_cards(
        self,
        page: Page,
        query: str,
        categories: list[str] | None = None,
        page_limit: int | None = None,
    ) -> list[SearchCard]:
        all_cards = []
        for collection_id in self._resolve_collection_ids(categories):
            cards = await self._collect_collection_cards(page, query, collection_id, page_limit)
            all_cards.extend(cards)

        deduped = {}
        for card in all_cards:
            existing = deduped.get(card.id)
            if not existing or card.relevance_score > existing.relevance_score:
                deduped[card.id] = card
        return list(deduped.values())

    async def _collect_collection_cards(
        self,
        page: Page,
        query: str,
        collection_id: str,
        page_limit: int | None = None,
    ) -> list[SearchCard]:
        settings = get_settings()

        await self._go_to_query(page, query)
        await page.evaluate(f"doCollection('{collection_id}')")

        try:
            await page.wait_for_selector(
                OLTA_SELECTORS["search"]["result_title_links"],
                timeout=5000,
            )
        except Exception:
            await page.wait_for_load_state("domcontentloaded")

        total_count = await self._extract_total_count(page)
        total_pages = max(1, math.ceil(total_count / 10)) if total_count else 1
        if page_limit is None:
            effective_page_limit = total_pages
        else:
            effective_page_limit = min(total_pages, page_limit)

        cards_by_id: dict[str, SearchCard] = {}
        for page_index in range(effective_page_limit):
            if page_index > 0:
                offset = page_index * 10
                await page.evaluate(f"doPaging('{offset}')")
                try:
                    await page.wait_for_selector(
                        OLTA_SELECTORS["search"]["result_title_links"],
                        timeout=5000,
                    )
                except Exception:
                    await page.wait_for_load_state("domcontentloaded")

            page_cards = await self._extract_cards_from_current_page(page, query, page_index)
            for card in page_cards:
                existing = cards_by_id.get(card.id)
                if not existing or card.relevance_score > existing.relevance_score:
                    cards_by_id[card.id] = card

        return list(cards_by_id.values())

    async def _search_all_bbs_boards(
        self,
        auth_context: BrowserContext,
        queries: list[str],
    ) -> list[CrawlResult]:
        """18개 BBS 게시판을 개별적으로 검색하고, 링크 클릭으로 상세 자료를 수집한다."""
        settings = get_settings()
        semaphore = asyncio.Semaphore(settings.olta_bbs_concurrency)

        async def search_board(board_name: str) -> list[CrawlResult]:
            async with semaphore:
                board_results: list[CrawlResult] = []
                for query in queries:
                    results = await self._search_single_bbs_board(
                        auth_context, query, board_name,
                    )
                    board_results.extend(results)
                return board_results

        board_results = await asyncio.gather(
            *(search_board(board) for board in BBS_BOARDS),
            return_exceptions=True,
        )

        all_results: list[CrawlResult] = []
        for board_name, result in zip(BBS_BOARDS, board_results, strict=False):
            if isinstance(result, Exception):
                logger.warning("BBS 게시판 '%s' 검색 실패: %s", board_name, result)
                continue
            all_results.extend(result)

        logger.info("BBS 전체 검색 완료: %d건 (18개 게시판)", len(all_results))
        return all_results

    async def _search_single_bbs_board(
        self,
        auth_context: BrowserContext,
        query: str,
        board_name: str,
    ) -> list[CrawlResult]:
        """단일 BBS 게시판을 검색하고, 각 게시물 링크를 클릭하여 상세 자료를 수집한다."""
        settings = get_settings()
        page = await auth_context.new_page()
        page.set_default_timeout(settings.playwright_timeout)
        type_label = f"기타/{board_name}"
        results: list[CrawlResult] = []
        seen_ids: set[str] = set()

        try:
            search_url = urljoin(settings.olta_base_url, "/search/PU_0003_search.jsp")
            await page.goto(search_url, wait_until="domcontentloaded")
            await page.fill("input#queryPu", query)
            await page.evaluate("doSearchPu()")
            await page.wait_for_load_state("networkidle")

            # 게시판별 필터 적용
            logger.debug("BBS '%s' 필터 적용: doBrdNmCollection('%s','bbs')", board_name, board_name)
            await page.evaluate(f"doBrdNmCollection('{board_name}','bbs')")

            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                await page.wait_for_load_state("domcontentloaded")

            current_url = page.url
            logger.debug("BBS '%s' 필터 후 URL: %s", board_name, current_url)

            for page_index in range(settings.olta_bbs_max_pages_per_board):
                if page_index > 0:
                    offset = page_index * 10
                    try:
                        await page.evaluate(f"doPaging('{offset}')")
                        await page.wait_for_selector(
                            OLTA_SELECTORS["search"]["result_title_links"],
                            timeout=5000,
                        )
                    except Exception:
                        break

                links = page.locator(OLTA_SELECTORS["search"]["result_title_links"])
                count = await links.count()
                logger.debug("BBS '%s' 페이지%d 링크 수: %d", board_name, page_index, count)
                if count == 0:
                    # 셀렉터가 맞지 않을 수 있으므로 페이지 내 모든 링크도 확인
                    all_links = await page.locator("a[onclick]").count()
                    logger.debug("BBS '%s' 페이지%d 전체 onclick 링크 수: %d", board_name, page_index, all_links)
                    break

                # 클릭 전에 제목·메타 정보를 먼저 추출 (클릭하면 DOM이 바뀔 수 있으므로)
                link_info = await links.evaluate_all(
                    """(links) => links.map((link) => {
                        const wrapper = link.closest('li');
                        const meta = wrapper?.querySelector('p:not(.tt):not(.txt)')?.textContent || '';
                        const preview = wrapper?.querySelector('p.txt')?.textContent || '';
                        return {
                            title: (link.textContent || '').trim(),
                            meta: meta.trim(),
                            preview: preview.trim(),
                        };
                    })"""
                )

                # 각 게시물 링크를 클릭하여 상세 페이지 진입 → 자료 수집
                for i in range(count):
                    try:
                        result = await self._click_and_collect_bbs_item(
                            page, links, i, link_info,
                            type_label, board_name, page_index, seen_ids,
                        )
                        if result:
                            results.append(result)
                    except Exception:
                        logger.debug(
                            "BBS '%s' 게시물 %d 클릭 수집 실패",
                            board_name, i, exc_info=True,
                        )

            if results:
                logger.info("BBS '%s' 검색: %d건 (쿼리: %s)", board_name, len(results), query)
            return results
        except Exception:
            logger.warning("BBS '%s' 검색 실패 (쿼리: %s)", board_name, query, exc_info=True)
            return []
        finally:
            await page.close()

    async def _click_and_collect_bbs_item(
        self,
        page: Page,
        links,
        index: int,
        link_info: list[dict],
        type_label: str,
        board_name: str,
        page_index: int,
        seen_ids: set[str],
    ) -> CrawlResult | None:
        """검색 결과의 개별 링크를 클릭하여 팝업/상세 페이지에서 자료를 수집한다."""
        detail_page: Page | None = None
        try:
            # 링크 클릭 시 팝업(window.open)이 열리는 것을 기대
            async with page.expect_popup(timeout=5000) as popup_info:
                await links.nth(index).click()
            detail_page = await popup_info.value
        except Exception:
            # 팝업이 아닌 경우: 같은 페이지 내 네비게이션 시도
            try:
                await links.nth(index).click()
                await page.wait_for_load_state("domcontentloaded")
                detail_page = None  # 현재 page 자체가 상세 페이지
            except Exception:
                return None

        # 상세 페이지에서 콘텐츠 수집
        target = detail_page if detail_page else page
        try:
            await target.wait_for_load_state("domcontentloaded")
            try:
                await target.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass

            detail_url = target.url
            raw_body = await target.locator("body").inner_text()
            content = self._extract_meaningful_content(raw_body)

            if not content or "500 Internal Server error" in content:
                return None

            comments = await self._extract_comments(target)

            # ID 생성
            ntt_match = re.search(r"nttId=(\d+)", detail_url)
            bbs_id_match = re.search(r"bbsId=([^&]+)", detail_url)
            if ntt_match:
                base_id = ntt_match.group(1)
                card_id = (
                    f"olta_bbs_{bbs_id_match.group(1)}_{base_id}"
                    if bbs_id_match
                    else f"olta_bbs_{base_id}"
                )
            else:
                card_id = f"olta_bbs_{board_name}_{page_index}_{index}"

            if card_id in seen_ids:
                return None
            seen_ids.add(card_id)

            info = link_info[index] if index < len(link_info) else {}
            title = self._clean_text(info.get("title", f"{board_name} 게시물 {index + 1}"))
            meta = self._clean_text(info.get("meta", ""))

            full_content = "\n".join(part for part in [meta, content] if part)
            if comments:
                full_content += f"\n\n[댓글/답변]\n{comments}"

            preview_text = content[:180] + "..." if len(content) > 180 else content
            score = max(0.1, 0.85 - (index * 0.04) - (page_index * 0.03))

            return CrawlResult(
                id=card_id,
                title=title,
                type=type_label,
                content=full_content,
                preview=preview_text,
                url=detail_url,
                relevance_score=score,
                document_year=self._extract_document_year(content),
                comments=comments,
                crawled_at=datetime.now(),
            )
        finally:
            # 팝업인 경우 닫고, 같은 페이지 네비게이션인 경우 뒤로 가기
            if detail_page:
                await detail_page.close()
            else:
                await page.go_back(wait_until="domcontentloaded")

    async def _go_to_query(self, page: Page, query: str) -> None:
        settings = get_settings()
        entry_url = urljoin(settings.olta_base_url, OLTA_SELECTORS["search"]["entry_url"])
        await page.goto(entry_url, wait_until="domcontentloaded")
        await page.fill(OLTA_SELECTORS["search"]["search_input"], query)
        await page.click(OLTA_SELECTORS["search"]["search_button"])
        await page.wait_for_load_state("networkidle")

    async def _search_query(self, page: Page, query: str) -> list[SearchCard]:
        await self._go_to_query(page, query)
        return await self._extract_cards_from_current_page(page, query, 0)

    async def _extract_cards_from_current_page(
        self,
        page: Page,
        query: str,
        page_index: int,
    ) -> list[SearchCard]:
        raw_cards = await page.locator(OLTA_SELECTORS["search"]["result_title_links"]).evaluate_all(
            """(links) => links.map((link) => {
                const wrapper = link.closest('li');
                const meta = wrapper?.querySelector('p:not(.tt):not(.txt)')?.textContent || '';
                const preview = wrapper?.querySelector('p.txt')?.textContent || '';
                return {
                    title: (link.textContent || '').trim(),
                    onclick: link.getAttribute('onclick') || '',
                    meta: meta.trim(),
                    preview: preview.trim(),
                };
            })"""
        )
        cards = []
        seen = set()
        for position, raw_card in enumerate(raw_cards, start=1):
            card = self._build_search_card(raw_card, query, position, page_index)
            if not card or card.id in seen:
                continue
            seen.add(card.id)
            cards.append(card)
        return cards

    def _build_search_card(
        self,
        raw_card: dict,
        query: str,
        position: int,
        page_index: int,
    ) -> SearchCard | None:
        onclick = raw_card.get("onclick", "")
        match = re.search(r"javascript:(\w+)\((.*?)\)", onclick)
        if not match:
            return None

        popup_name = match.group(1)

        if popup_name == "bbsPopUp":
            url_match = re.search(r"https?://[^\s'\"\\]+", match.group(2))
            if not url_match:
                return None
            detail_url = url_match.group(0)
            ntt_match = re.search(r"nttId=(\d+)", detail_url)
            bbs_id_match = re.search(r"bbsId=([^&]+)", detail_url)
            base_identifier = ntt_match.group(1) if ntt_match else detail_url
            # bbsId로 게시판 식별 (개별 검색에서 type이 덮어씌워질 수 있음)
            bbs_id = bbs_id_match.group(1) if bbs_id_match else None
            if bbs_id:
                base_identifier = f"{bbs_id}_{base_identifier}"
        elif popup_name in POPUP_URL_BUILDERS:
            args = self._parse_popup_args(match.group(2))
            if not args:
                return None
            detail_path = POPUP_URL_BUILDERS[popup_name](args)
            detail_url = urljoin(get_settings().olta_base_url, detail_path)
            base_identifier = args[0] if popup_name != "decisionDtlpopUp" else args[1]
        else:
            return None

        type_label = POPUP_TYPE_MAP.get(popup_name, "기타")
        score = max(0.1, 1.0 - ((position - 1) * 0.04) - (page_index * 0.03))
        document_year = self._extract_document_year(
            " ".join(
                [
                    raw_card.get("title", ""),
                    raw_card.get("meta", ""),
                    raw_card.get("preview", ""),
                ]
            )
        )

        return SearchCard(
            id=f"olta_{popup_name}_{base_identifier}",
            title=self._clean_text(raw_card.get("title", "")),
            preview=self._clean_text(raw_card.get("preview", "")),
            type=type_label,
            meta=self._clean_text(raw_card.get("meta", "")),
            detail_url=detail_url,
            relevance_score=score,
            document_year=document_year,
        )

    def _parse_popup_args(self, raw_args: str) -> list[str]:
        values = []
        for part in raw_args.split(","):
            token = part.strip().strip("'").strip('"')
            values.append("null" if token in {"", "null", "None"} else token)
        return values

    async def _collect_details(
        self,
        context: BrowserContext,
        cards: list[SearchCard],
    ) -> list[CrawlResult]:
        semaphore = asyncio.Semaphore(5)

        async def worker(card: SearchCard) -> CrawlResult | None:
            async with semaphore:
                return await self._fetch_detail(context, card)

        details = await asyncio.gather(*(worker(card) for card in cards), return_exceptions=True)
        results = []
        for item, card in zip(details, cards, strict=False):
            if isinstance(item, Exception):
                results.append(self._fallback_result(card))
                continue
            if item is not None:
                results.append(item)
        return results

    async def _extract_comments(self, page: Page) -> str:
        """게시글 댓글/답변을 추출한다."""
        comment_selectors = [
            ".comment_area",
            ".reply_area",
            ".cmt_list",
            "#comment",
            ".board_comment",
            ".answer_area",
            "[class*='comment']",
            "[class*='reply']",
            "[class*='answer']",
        ]
        for selector in comment_selectors:
            try:
                elements = page.locator(selector)
                count = await elements.count()
                if count > 0:
                    parts = []
                    for i in range(count):
                        text = await elements.nth(i).inner_text()
                        cleaned = self._clean_text(text)
                        if cleaned and len(cleaned) > 10:
                            parts.append(cleaned)
                    if parts:
                        return "\n".join(parts)
            except Exception:
                continue
        return ""

    async def _fetch_detail(self, context: BrowserContext, card: SearchCard) -> CrawlResult | None:
        page = await context.new_page()
        page.set_default_timeout(get_settings().playwright_timeout)
        try:
            await page.goto(card.detail_url, wait_until="domcontentloaded")
            try:
                await page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass
            raw_body = await page.locator("body").inner_text()
            content = self._extract_meaningful_content(raw_body)
            if not content or "500 Internal Server error" in content:
                return self._fallback_result(card)

            comments = await self._extract_comments(page)

            full_content = "\n".join(part for part in [card.meta, content] if part)
            if comments:
                full_content += f"\n\n[댓글/답변]\n{comments}"

            preview = content[:180] + "..." if len(content) > 180 else content
            document_year = card.document_year or self._extract_document_year(content)
            return CrawlResult(
                id=card.id,
                title=card.title,
                type=card.type,
                content=full_content,
                preview=preview,
                url=card.detail_url,
                relevance_score=card.relevance_score,
                document_year=document_year,
                comments=comments,
                crawled_at=datetime.now(),
            )
        finally:
            await page.close()

    def _extract_meaningful_content(self, raw_body: str) -> str:
        settings = get_settings()
        cleaned = self._clean_text(raw_body)
        if not cleaned:
            return ""

        marker_candidates = [
            "질의요지",
            "회신",
            "답변요지",
            "결정요지",
            "판결요지",
            "관계법령",
            "주문",
            "이유",
            "본문정보",
            "사건번호",
            "처분내용",
            "청구취지",
            "참조조문",
        ]
        start_index = 0
        for marker in marker_candidates:
            marker_index = cleaned.find(marker)
            if marker_index != -1:
                start_index = marker_index
                break
        content = cleaned[start_index:] if start_index else cleaned
        noise_patterns = [
            r"Copyright.*$",
            r"개인정보.*처리방침",
            r"이용약관",
            r"상단으로\s*이동",
            r"관련\s*사이트",
            r"고객센터.*\d{3,4}",
        ]
        for pattern in noise_patterns:
            content = re.sub(pattern, "", content, flags=re.MULTILINE)
        content = re.sub(r"\s+", " ", content).strip()
        if settings.crawler_content_limit is None:
            return content
        return content[: settings.crawler_content_limit]

    def _fallback_result(self, card: SearchCard) -> CrawlResult:
        summary = card.preview or card.meta or card.title
        return CrawlResult(
            id=card.id,
            title=card.title,
            type=card.type,
            content="\n".join(part for part in [card.meta, summary] if part),
            preview=summary[:180] + "..." if len(summary) > 180 else summary,
            url=card.detail_url,
            relevance_score=card.relevance_score,
            document_year=card.document_year or self._extract_document_year(summary),
            crawled_at=datetime.now(),
        )

    def _filter_cards(self, cards: list[SearchCard], categories: list[str] | None) -> list[SearchCard]:
        if not categories:
            return cards
        allowed_types = set()
        for category in categories:
            allowed_types.update(COLLECTION_TYPE_MAP.get(category, set()))
        if not allowed_types:
            return cards
        return [card for card in cards if card.type in allowed_types]

    def _resolve_collection_ids(self, categories: list[str] | None) -> list[str]:
        if not categories:
            return DEFAULT_COLLECTION_IDS

        collection_ids = []
        for category in categories:
            collection_ids.extend(COLLECTION_IDS.get(category, []))
        return list(dict.fromkeys(collection_ids)) or DEFAULT_COLLECTION_IDS

    async def _extract_total_count(self, page: Page) -> int:
        body = await page.locator("body").inner_text()
        match = re.search(r"\(총\s*([\d,]+)건\)", body)
        if not match:
            return 0
        return int(match.group(1).replace(",", ""))

    def _extract_document_year(self, text: str) -> int | None:
        years = re.findall(r"(?<!\d)((?:19|20)\d{2})(?:년)?(?!\d)", text or "")
        if not years:
            return None

        numeric_years = [int(year) for year in years]
        current_year = datetime.now().year
        valid_years = [year for year in numeric_years if 1900 <= year <= current_year + 1]
        if not valid_years:
            return None
        return max(valid_years)

    def _clean_text(self, value: str) -> str:
        without_tags = re.sub(r"<[^>]+>", " ", value or "")
        normalized = without_tags.replace("\xa0", " ")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()


crawler_service = CrawlerService()
