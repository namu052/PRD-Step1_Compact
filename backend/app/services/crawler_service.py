import asyncio
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import BrowserContext, Page, async_playwright

from app.config import OLTA_SELECTORS, get_settings
from app.models.schemas import CrawlResult


POPUP_TYPE_MAP = {
    "legalPopUp": "법제처 유권해석",
    "authoritativePopUp": "행안부 유권해석",
    "screenPopUp": "조세심판원 결정례",
    "decisionDtlpopUp": "법원 판례",
    "evaluationPopUp": "감사원 심사결정례",
    "constitutionPopUp": "헌법재판소 결정례",
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
    def __init__(self) -> None:
        self._mock_data = None

    def _load_mock_data(self) -> dict:
        if self._mock_data is None:
            mock_path = (
                Path(__file__).resolve().parent.parent.parent / "tests" / "mocks" / "mock_olta_pages.json"
            )
            with mock_path.open("r", encoding="utf-8") as file:
                self._mock_data = json.load(file)
        return self._mock_data

    async def search(self, session, queries: list[str], categories: list[str] | None = None) -> list[CrawlResult]:
        settings = get_settings()
        if settings.use_mock_crawler:
            return self._mock_search(queries, categories)

        return await self._real_search(queries, categories)

    async def _real_search(
        self,
        queries: list[str],
        categories: list[str] | None = None,
    ) -> list[CrawlResult]:
        settings = get_settings()
        if not queries:
            return []

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=settings.playwright_headless)
            context = await browser.new_context()
            page = await context.new_page()
            page.set_default_timeout(settings.playwright_timeout)

            cards_by_id: dict[str, SearchCard] = {}
            for index, query in enumerate(queries):
                if index > 0 and len(cards_by_id) >= settings.olta_max_detail_fetch * 3:
                    break

                query_page_limit = settings.olta_max_pages_per_collection if index == 0 else max(
                    2,
                    settings.olta_max_pages_per_collection // 2,
                )
                cards = await self._collect_query_cards(page, query, categories, query_page_limit)
                for card in cards:
                    existing = cards_by_id.get(card.id)
                    if not existing or card.relevance_score > existing.relevance_score:
                        cards_by_id[card.id] = card

            ranked_cards = sorted(cards_by_id.values(), key=lambda item: item.relevance_score, reverse=True)
            limited_cards = ranked_cards[: settings.olta_max_detail_fetch]
            details = await self._collect_details(context, limited_cards)

            await context.close()
            await browser.close()

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
        await page.wait_for_timeout(1500)
        await page.wait_for_load_state("domcontentloaded")

        total_count = await self._extract_total_count(page)
        total_pages = max(1, math.ceil(total_count / 10)) if total_count else 1
        effective_page_limit = min(total_pages, page_limit or settings.olta_max_pages_per_collection)

        cards_by_id: dict[str, SearchCard] = {}
        for page_index in range(effective_page_limit):
            if page_index > 0:
                offset = page_index * 10
                await page.evaluate(f"doPaging('{offset}')")
                await page.wait_for_timeout(1200)
                await page.wait_for_load_state("domcontentloaded")

            page_cards = await self._extract_cards_from_current_page(page, query, page_index)
            for card in page_cards:
                existing = cards_by_id.get(card.id)
                if not existing or card.relevance_score > existing.relevance_score:
                    cards_by_id[card.id] = card

        return list(cards_by_id.values())

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
        if popup_name not in POPUP_URL_BUILDERS:
            return None

        args = self._parse_popup_args(match.group(2))
        if not args:
            return None

        detail_path = POPUP_URL_BUILDERS[popup_name](args)
        detail_url = urljoin(get_settings().olta_base_url, detail_path)
        type_label = POPUP_TYPE_MAP.get(popup_name, "기타")
        base_identifier = args[0] if popup_name != "decisionDtlpopUp" else args[1]
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
        semaphore = asyncio.Semaphore(3)

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

    async def _fetch_detail(self, context: BrowserContext, card: SearchCard) -> CrawlResult | None:
        page = await context.new_page()
        page.set_default_timeout(get_settings().playwright_timeout)
        try:
            await page.goto(card.detail_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1200)
            raw_body = await page.locator("body").inner_text()
            content = self._extract_meaningful_content(raw_body)
            if not content or "500 Internal Server error" in content:
                return self._fallback_result(card)

            preview = content[:180] + "..." if len(content) > 180 else content
            document_year = card.document_year or self._extract_document_year(content)
            return CrawlResult(
                id=card.id,
                title=card.title,
                type=card.type,
                content="\n".join(part for part in [card.meta, content] if part),
                preview=preview,
                url=card.detail_url,
                relevance_score=card.relevance_score,
                document_year=document_year,
                crawled_at=datetime.now(),
            )
        finally:
            await page.close()

    def _extract_meaningful_content(self, raw_body: str) -> str:
        cleaned = self._clean_text(raw_body)
        if not cleaned:
            return ""

        marker_candidates = [
            "관계법령",
            "답변요지",
            "결정요지",
            "판결요지",
            "주문",
            "이유",
            "본문정보",
        ]
        start_index = 0
        for marker in marker_candidates:
            marker_index = cleaned.find(marker)
            if marker_index != -1:
                start_index = marker_index
                break
        content = cleaned[start_index:] if start_index else cleaned
        return content[:5000]

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

    def _mock_search(self, queries: list[str], categories: list[str] | None = None) -> list[CrawlResult]:
        data = self._load_mock_data()
        results = []
        seen_ids = set()
        target_categories = categories or ["law_search", "interpret_search"]

        for query in queries:
            for category in target_categories:
                category_data = data.get(category, {})
                for keyword, items in category_data.items():
                    if query in keyword or keyword in query:
                        for item in items:
                            if item["id"] in seen_ids:
                                continue
                            seen_ids.add(item["id"])
                            results.append(
                                CrawlResult(
                                    id=item["id"],
                                    title=item["title"],
                                    type=item["type"],
                                    content=item["content"],
                                    preview=f"{item['content'][:100]}...",
                                    url=item["url"],
                                    relevance_score=0.9,
                                    document_year=self._extract_document_year(
                                        " ".join([item["title"], item["content"]])
                                    ),
                                    crawled_at=datetime.now(),
                                )
                            )
        return results

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
