import asyncio
import json
import logging
import math
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

from playwright.async_api import BrowserContext, Locator, Page, async_playwright

from app.config import OLTA_SELECTORS, get_settings
from app.models.schemas import BoardCollectionStat, CrawlResult


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
    "쟁송사무지원 사례",
    "쟁송사무위크숍 자료",
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

COLLECTION_POPUP_MAP = {
    "legal": "legalPopUp",
    "authoritative": "authoritativePopUp",
    "screen": "screenPopUp",
    "evaluation": "evaluationPopUp",
    "ordinance": "constitutionPopUp",
    "sentencing": "decisionDtlpopUp",
}

ProgressCallback = Callable[[BoardCollectionStat], Awaitable[None]] | None


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


@dataclass
class BBSBoardDefinition:
    label: str
    value: str
    normalized_key: str
    type_label: str
    enabled: bool = True


@dataclass
class BBSResultCard:
    title: str
    meta: str
    preview: str
    onclick: str
    href: str
    detail_url: str | None
    canonical_id: str | None
    target_attr: str = ""
    link_html: str = ""
    data_bbs_id: str = ""
    data_ntt_id: str = ""
    row_html: str = ""
    row_selector: str = ""
    row_index: int = 0


@dataclass
class BBSOpenTarget:
    mode: str
    detail_url: str | None
    popup_function: str | None = None
    popup_args: list[str] | None = None
    canonical_id: str | None = None
    requires_click: bool = False
    reason: str | None = None


class CrawlerService:
    _shared_playwright = None
    _shared_browser = None
    _shared_context: BrowserContext | None = None
    _shared_page: Page | None = None
    _olta_logged_in: bool = False

    async def _is_context_alive(self) -> bool:
        """shared context가 아직 살아있는지 확인한다."""
        if self._shared_context is None:
            return False
        try:
            # context.pages 접근으로 liveness 확인
            _ = self._shared_context.pages
            return True
        except Exception:
            return False

    async def ensure_browser(self):
        """공유 브라우저 컨텍스트를 준비한다. 죽었으면 재생성."""
        if self._shared_context is not None and not await self._is_context_alive():
            # 죽은 컨텍스트 정리
            logger.info("Playwright context died — recreating")
            if self._shared_playwright:
                try:
                    await self._shared_playwright.stop()
                except Exception:
                    pass
            self._shared_playwright = None
            self._shared_context = None
            self._shared_browser = None
            self._shared_page = None

        if self._shared_context is None:
            pw = await async_playwright().start()
            settings = get_settings()
            user_data_dir = Path(settings.olta_shared_user_data_dir)
            user_data_dir.mkdir(parents=True, exist_ok=True)
            self._shared_playwright = pw
            self._shared_context = await pw.chromium.launch_persistent_context(
                str(user_data_dir),
                headless=settings.playwright_headless,
                args=["--disable-popup-blocking"],
            )
            self._shared_browser = self._shared_context.browser
            self._shared_page = None
            for page in self._shared_context.pages:
                if not page.is_closed():
                    self._shared_page = page
                    break
            self._olta_logged_in = False
        return self._shared_context

    async def ensure_shared_page(self) -> Page:
        context = await self.ensure_browser()
        settings = get_settings()
        if self._shared_page is None or self._shared_page.is_closed():
            # 열려있는 기존 페이지 찾기
            for page in context.pages:
                if not page.is_closed():
                    self._shared_page = page
                    break
            if self._shared_page is None or self._shared_page.is_closed():
                try:
                    self._shared_page = await context.new_page()
                except Exception:
                    # context가 죽었으면 재생성 후 재시도
                    logger.warning("Failed to create page, recreating browser context")
                    self._shared_context = None
                    context = await self.ensure_browser()
                    self._shared_page = await context.new_page()
            self._shared_page.set_default_timeout(settings.playwright_timeout)
        return self._shared_page

    async def _detect_olta_login_on_page(self, page: Page) -> bool:
        """OLTA 페이지에서 로그인 상태를 감지한다.

        판별 방법 (우선순위):
        1) URL에 'Login' 또는 'login'이 포함 → 미로그인 (로그인 페이지)
        2) URL에 'main.do'이고 로그인 페이지가 아님 → 메인에서 DOM 확인
        3) DOM에서 logout 관련 href/onclick 존재 → 로그인됨
        """
        current_url = page.url or ""

        # URL 기반 빠른 판별: 로그인 페이지에 있으면 미로그인
        if "login" in current_url.lower() or "Login" in current_url:
            self._olta_logged_in = False
            return False

        # DOM 기반 판별 (href/onclick 속성은 인코딩 문제 없음)
        logged_in = await page.evaluate("""
            () => {
                const candidates = Array.from(document.querySelectorAll('a, button, input'));

                for (const node of candidates) {
                    const href = (node.getAttribute('href') || '').toLowerCase();
                    const onclick = (node.getAttribute('onclick') || '').toLowerCase();
                    const value = (node.value || '').toLowerCase();
                    const attrs = `${href} ${onclick} ${value}`;

                    // logout 관련 속성이 있으면 로그인된 상태
                    if (/logout|logoutaction|fn_logout/i.test(attrs)) {
                        return true;
                    }
                }

                // HTML 소스에서 logout 키워드 검색 (인코딩 무관)
                const html = document.body?.innerHTML || '';
                if (/logout|Logout|fn_logout/i.test(html)) {
                    return true;
                }

                return false;
            }
        """)
        self._olta_logged_in = logged_in
        return logged_in

    async def bring_browser_to_front(self) -> None:
        """Playwright 브라우저 창을 앞으로 가져온다."""
        try:
            page = await self.ensure_shared_page()
            await page.bring_to_front()
            # Windows에서 bring_to_front만으로 활성화가 안 될 수 있으므로
            # 새 빈 팝업을 열었다 닫아 포커스를 강제로 가져온다
            await page.evaluate("""
                () => {
                    const w = window.open('', '_blank', 'width=1,height=1');
                    if (w) { w.close(); }
                    window.focus();
                }
            """)
        except Exception:
            logger.warning("bring_to_front failed", exc_info=True)

    async def check_olta_login(self, navigate: bool = True) -> bool:
        """OLTA login state check.  Also opens the OLTA page on first call so
        the user can log in via the Playwright browser window."""
        page = await self.ensure_shared_page()
        try:
            if navigate:
                current_url = page.url or ""
                settings = get_settings()
                main_url = urljoin(settings.olta_base_url, "/main.do")
                if "olta.re.kr" not in current_url:
                    # 최초: OLTA 메인으로 이동
                    await page.goto(
                        main_url,
                        wait_until="domcontentloaded",
                        timeout=15000,
                    )
                elif "login" in current_url.lower():
                    # 로그인 페이지 → 사용자가 로그인 후 리다이렉트됐을 수 있으므로
                    # 메인으로 이동하여 확인
                    await page.goto(
                        main_url,
                        wait_until="domcontentloaded",
                        timeout=15000,
                    )
                else:
                    # 이미 OLTA 비-로그인 페이지 — reload하여 최신 DOM 확보
                    await page.reload(wait_until="domcontentloaded", timeout=15000)
            return await self._detect_olta_login_on_page(page)
        except Exception:
            logger.warning("OLTA login check failed", exc_info=True)
            self._olta_logged_in = False
            return False

    async def open_olta_for_login(self) -> str:
        """수동 로그인을 위해 OLTA 페이지를 Playwright 브라우저에서 연다."""
        await self.ensure_browser()
        settings = get_settings()
        page = await self.ensure_shared_page()
        login_url = urljoin(settings.olta_base_url, "/main.do")
        current_url = page.url or ""
        if "olta.re.kr" not in current_url:
            await page.goto(login_url, wait_until="domcontentloaded", timeout=15000)
        await page.bring_to_front()
        return login_url

    async def get_auth_context(self) -> BrowserContext | None:
        """로그인된 브라우저 컨텍스트를 반환. 미로그인이면 None."""
        if self._olta_logged_in:
            return self._shared_context
        # ?쒕쾲 ???뺤씤
        if await self.check_olta_login():
            return self._shared_context
        return None

    async def close_browser(self) -> None:
        """공유 브라우저를 종료한다."""
        if self._shared_page:
            try:
                await self._shared_page.close()
            except Exception:
                pass
            self._shared_page = None
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
        if self._shared_playwright:
            try:
                await self._shared_playwright.stop()
            except Exception:
                pass
            self._shared_playwright = None
        self._olta_logged_in = False

    def _normalize_bbs_label(self, value: str) -> str:
        normalized = re.sub(r"[\s\-_/:()\[\].,]+", "", value or "")
        return normalized.casefold()

    def _is_bbs_board_candidate(self, label: str, value: str) -> bool:
        normalized_key = self._normalize_bbs_label(label or value)
        blocked_keys = {
            "",
            self._normalize_bbs_label("전체"),
            self._normalize_bbs_label("선택"),
            self._normalize_bbs_label("검색"),
            self._normalize_bbs_label("전체"),
            self._normalize_bbs_label("선택"),
            self._normalize_bbs_label("검색"),
            "all",
            "bbs",
            "board",
        }
        if normalized_key in blocked_keys:
            return False
        return len(normalized_key) >= 2

    def _get_bbs_fallback_definitions(self) -> list[BBSBoardDefinition]:
        return [
            BBSBoardDefinition(
                label=label,
                value=label,
                normalized_key=self._normalize_bbs_label(label),
                type_label=f"기타/{label}",
            )
            for label in BBS_BOARDS
        ]

    def _merge_bbs_board_records(self, records: list[dict]) -> list[BBSBoardDefinition]:
        fallback_definitions = self._get_bbs_fallback_definitions()
        discovered_by_key: dict[str, dict] = {}

        for record in records:
            label = self._clean_text(record.get("label", ""))
            value = self._clean_text(record.get("value", ""))
            if not self._is_bbs_board_candidate(label, value):
                continue
            normalized_key = self._normalize_bbs_label(label or value)
            if not normalized_key:
                continue

            existing = discovered_by_key.get(normalized_key)
            candidate = {
                "label": label or value,
                "value": value or label,
                "source": record.get("source", ""),
            }

            if not existing or len(candidate["label"]) > len(existing.get("label", "")):
                discovered_by_key[normalized_key] = candidate

        merged: list[BBSBoardDefinition] = []
        used_keys: set[str] = set()

        for fallback in fallback_definitions:
            discovered = discovered_by_key.get(fallback.normalized_key)
            if discovered:
                label = discovered["label"] or fallback.label
                value = discovered["value"] or label
                merged.append(
                    BBSBoardDefinition(
                        label=label,
                        value=value,
                        normalized_key=fallback.normalized_key,
                        type_label=f"기타/{label}",
                    )
                )
            else:
                merged.append(fallback)
            used_keys.add(fallback.normalized_key)

        for normalized_key, discovered in discovered_by_key.items():
            if normalized_key in used_keys:
                continue
            label = discovered["label"] or discovered["value"]
            if not label:
                continue
            merged.append(
                BBSBoardDefinition(
                    label=label,
                    value=discovered["value"] or label,
                    normalized_key=normalized_key,
                    type_label=f"기타/{label}",
                )
            )

        return merged

    def _debug_dump_text(self, name: str, content: str) -> None:
        settings = get_settings()
        if not settings.olta_bbs_debug:
            return

        dump_dir = Path(settings.olta_bbs_dump_dir)
        dump_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
        (dump_dir / safe_name).write_text(content, encoding="utf-8")

    async def _extract_bbs_board_records(self, page: Page) -> list[dict]:
        records = await page.evaluate(
            """
            () => {
              const items = []
              const push = (label, value, source, onclick = '') => {
                const normalizedLabel = (label || '').replace(/\\s+/g, ' ').trim()
                const normalizedValue = (value || '').replace(/\\s+/g, ' ').trim()
                if (!normalizedLabel && !normalizedValue) return
                items.push({
                  label: normalizedLabel,
                  value: normalizedValue,
                  source,
                  onclick: onclick || '',
                })
              }

              document.querySelectorAll('select option').forEach((option) => {
                push(option.textContent || '', option.value || '', 'option')
              })

              document.querySelectorAll("input[type='radio'], input[type='checkbox']").forEach((input) => {
                const explicit = input.id
                  ? document.querySelector(`label[for="${input.id}"]`)
                  : null
                const wrapped = input.closest('label')
                push(
                  explicit?.textContent || wrapped?.textContent || input.value || '',
                  input.value || '',
                  'input'
                )
              })

              document.querySelectorAll("[onclick*='doBrdNmCollection']").forEach((element) => {
                const onclick = element.getAttribute('onclick') || ''
                const match = onclick.match(/doBrdNmCollection\\((['"])(.*?)\\1/)
                const extracted = match ? match[2] : ''
                push(
                  element.textContent || extracted,
                  extracted || element.getAttribute('data-value') || element.textContent || '',
                  'onclick',
                  onclick
                )
              })

              return items
            }
            """
        )

        if records:
            self._debug_dump_text(
                "bbs_board_records.json",
                json.dumps(records, ensure_ascii=False, indent=2),
            )
        return records

    async def _discover_bbs_boards(self, page: Page) -> list[BBSBoardDefinition]:
        settings = get_settings()
        fallback_definitions = self._get_bbs_fallback_definitions()

        if settings.olta_bbs_mode != "discovery":
            return fallback_definitions

        try:
            records = await self._extract_bbs_board_records(page)
        except Exception:
            logger.warning("BBS board discovery failed, using fallback registry", exc_info=True)
            return fallback_definitions

        if not records:
            logger.info("BBS discovery returned no records, using fallback registry")
            return fallback_definitions

        boards = self._merge_bbs_board_records(records)
        logger.info("BBS board discovery complete: %d boards", len(boards))
        return boards

    async def _wait_for_bbs_refresh(self, page: Page) -> None:
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
            return
        except Exception:
            pass

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass

    async def _apply_bbs_board_filter(self, page: Page, board: BBSBoardDefinition) -> str:
        methods_tried: list[str] = []

        for filter_value, method_name in (
            (board.value, "js:value"),
            (board.label, "js:label"),
        ):
            if not filter_value:
                continue
            try:
                await page.evaluate(
                    "(payload) => doBrdNmCollection(payload.value, 'bbs')",
                    {"value": filter_value},
                )
                methods_tried.append(method_name)
                await self._wait_for_bbs_refresh(page)
                return method_name
            except Exception:
                methods_tried.append(f"{method_name}:failed")

        for selector in OLTA_SELECTORS["bbs"]["board_trigger_selectors"]:
            try:
                locator = page.locator(selector).first
                if await locator.count() == 0:
                    continue
                tag_name = await locator.evaluate("(node) => node.tagName.toLowerCase()")
                if tag_name == "select":
                    try:
                        await locator.select_option(value=board.value)
                    except Exception:
                        await locator.select_option(label=board.label)
                    await self._wait_for_bbs_refresh(page)
                    return f"dom:{selector}"
            except Exception:
                continue

        for candidate in (board.label, board.value):
            if not candidate:
                continue
            for selector in ("button", "a", "label", "span", "li"):
                locator = page.locator(selector).filter(has_text=candidate).first
                try:
                    if await locator.count() == 0:
                        continue
                    await locator.click()
                    await self._wait_for_bbs_refresh(page)
                    return f"text:{selector}"
                except Exception:
                    continue

        logger.debug("BBS 게시판필터 fallback 사용: %s (%s)", board.label, ", ".join(methods_tried))
        return "unfiltered"

    async def _find_bbs_result_container(self, page: Page) -> Locator | None:
        container_selectors = OLTA_SELECTORS["bbs"].get("result_container_selectors", [])
        row_selectors = OLTA_SELECTORS["bbs"]["result_row_selectors"]

        for container_selector in container_selectors:
            containers = page.locator(container_selector)
            try:
                container_count = await containers.count()
            except Exception:
                continue

            for index in range(min(container_count, 5)):
                container = containers.nth(index)
                try:
                    for row_selector in row_selectors:
                        if await container.locator(row_selector).count() > 0:
                            return container
                except Exception:
                    continue

        body = page.locator("body").first
        try:
            if await body.count() > 0:
                return body
        except Exception:
            pass
        return None

    async def _find_bbs_result_rows(self, container: Locator) -> tuple[str | None, Locator | None]:
        for selector in OLTA_SELECTORS["bbs"]["result_row_selectors"]:
            rows = container.locator(selector)
            try:
                if await rows.count() > 0:
                    return selector, rows
            except Exception:
                continue
        return None, None

    _BBS_LINK_IDENTIFIERS = re.compile(
        r"bbsId|nttId|bbsPopUp|view\.do|board/view", re.IGNORECASE,
    )
    _BBS_LINK_DEAD_HREFS = {"", "#", "javascript:void(0);", "javascript:void(0)", "javascript:;"}
    _BBS_LINK_PAGING_RE = re.compile(r"^[\d\s]*$")
    _BBS_LINK_NAV_RE = re.compile(
        r"menuNo=|upperMenuId=|/main\.do|importantList|login|logout|sitemap"
        r"|doCollection\(|doSearchPu\(|doPaging\(|authoritativePopUp\(|legalPopUp\("
        r"|screenPopUp\(|evaluationPopUp\(|constitutionPopUp\(|decisionDtlpopUp\(",
        re.IGNORECASE,
    )

    def _is_bbs_article_link(self, title: str, href: str, onclick: str) -> bool:
        """Return True when the link looks like a BBS article (not navigation/paging/menu)."""
        if self._BBS_LINK_PAGING_RE.match(title):
            return False
        if len(title) < 3 and not onclick:
            return False
        if href in self._BBS_LINK_DEAD_HREFS and not onclick:
            return False
        if href and self._BBS_LINK_NAV_RE.search(href):
            return False
        if onclick and self._BBS_LINK_NAV_RE.search(onclick):
            return False
        return True

    def _has_bbs_identifier(self, href: str, onclick: str) -> bool:
        return bool(
            self._BBS_LINK_IDENTIFIERS.search(href)
            or self._BBS_LINK_IDENTIFIERS.search(onclick)
        )

    async def _find_bbs_title_link(self, row: Locator) -> tuple[str | None, Locator | None]:
        # Pass 1: prefer links with BBS identifiers (bbsId, nttId, etc.)
        best_fallback: tuple[str | None, Locator | None] = (None, None)
        for selector in OLTA_SELECTORS["bbs"].get("result_title_link_selectors", []):
            links = row.locator(selector)
            try:
                count = await links.count()
            except Exception:
                continue

            for index in range(count):
                link = links.nth(index)
                try:
                    title = self._clean_text(await link.inner_text())
                    href = await link.get_attribute("href") or ""
                    onclick = await link.get_attribute("onclick") or ""
                except Exception:
                    continue

                if not self._is_bbs_article_link(title, href, onclick):
                    continue

                if self._has_bbs_identifier(href, onclick):
                    return selector, link

                # Pass 2 candidate: text long enough to be an article title
                if best_fallback[1] is None and len(title) >= 5:
                    best_fallback = (selector, link)

        return best_fallback

    async def _get_bbs_result_link_selector(self, page: Page) -> str | None:
        container = await self._find_bbs_result_container(page)
        if container is not None:
            _, rows = await self._find_bbs_result_rows(container)
            if rows is not None:
                try:
                    row_count = await rows.count()
                except Exception:
                    row_count = 0

                for row_index in range(min(row_count, 5)):
                    selector, link = await self._find_bbs_title_link(rows.nth(row_index))
                    if selector and link is not None:
                        return selector

        for selector in OLTA_SELECTORS["bbs"]["result_link_selectors"]:
            locator = page.locator(selector)
            try:
                if await locator.count() > 0:
                    return selector
            except Exception:
                continue
        return None

    def _extract_url_candidates(self, raw_text: str, current_url: str) -> list[str]:
        if not raw_text:
            return []

        candidates: list[str] = []
        for match in re.findall(r"https?://[^\s'\"\\)]+", raw_text):
            candidates.append(match)

        for match in re.findall(r"(/[^'\"\\)\s]*(?:bbsId|nttId)[^'\"\\)\s]*)", raw_text):
            candidates.append(urljoin(current_url, match))

        if raw_text and raw_text not in {"#", "javascript:void(0);", "javascript:void(0)"}:
            if raw_text.startswith("/"):
                candidates.append(urljoin(current_url, raw_text))

        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            normalized = candidate.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _parse_js_call(self, raw: str) -> dict | None:
        expression = (raw or "").strip().rstrip(";")
        if not expression:
            return None

        if expression.startswith("javascript:"):
            expression = expression[len("javascript:"):].strip()

        href_match = re.search(
            r"(?:document\.location(?:\.href)?|location(?:\.href)?)\s*=\s*['\"]([^'\"]+)['\"]",
            expression,
        )
        if href_match:
            return {
                "function_name": "location.href",
                "args": [href_match.group(1)],
                "raw": raw,
            }

        match = re.search(r"((?:window\.)?\w+)\((.*)\)$", expression)
        if not match:
            return None

        return {
            "function_name": match.group(1),
            "args": self._parse_popup_args(match.group(2)),
            "raw": raw,
        }

    def _extract_bbs_identifiers(self, *values: str) -> tuple[str | None, str | None]:
        bbs_id: str | None = None
        ntt_id: str | None = None

        for value in values:
            if not value:
                continue
            if not bbs_id:
                bbs_match = re.search(r"bbsId=([^&'\"\\]+)", value)
                if bbs_match:
                    bbs_id = bbs_match.group(1)
            if not ntt_id:
                ntt_match = re.search(r"nttId=(\d+)", value)
                if ntt_match:
                    ntt_id = ntt_match.group(1)
            if bbs_id and ntt_id:
                break

        return bbs_id, ntt_id

    def _build_bbs_detail_url_from_identifiers(
        self,
        bbs_id: str | None,
        ntt_id: str | None,
        current_url: str,
    ) -> str | None:
        if not bbs_id or not ntt_id:
            return None
        return urljoin(current_url, f"/board/view.do?bbsId={bbs_id}&nttId={ntt_id}")

    def _resolve_bbs_detail_url(self, onclick: str, href: str, current_url: str) -> str | None:
        for candidate in (href or "", onclick or ""):
            urls = self._extract_url_candidates(candidate, current_url)
            if urls:
                return urls[0]
        return None

    def _build_bbs_canonical_id(
        self,
        detail_url: str | None,
        board: BBSBoardDefinition,
        index: int,
    ) -> str | None:
        if detail_url:
            ntt_match = re.search(r"nttId=(\d+)", detail_url)
            bbs_id_match = re.search(r"bbsId=([^&]+)", detail_url)
            if ntt_match:
                base_id = ntt_match.group(1)
                if bbs_id_match:
                    return f"olta_bbs_{bbs_id_match.group(1)}_{base_id}"
                return f"olta_bbs_{base_id}"

        if board.normalized_key:
            return f"olta_bbs_{board.normalized_key}_{index}"
        return None

    def _build_bbs_canonical_id_from_parts(
        self,
        board: BBSBoardDefinition,
        index: int,
        detail_url: str | None = None,
        bbs_id: str | None = None,
        ntt_id: str | None = None,
    ) -> str | None:
        if detail_url:
            canonical_id = self._build_bbs_canonical_id(detail_url, board, index)
            if canonical_id:
                return canonical_id
        if bbs_id and ntt_id:
            return f"olta_bbs_{bbs_id}_{ntt_id}"
        if board.normalized_key:
            return f"olta_bbs_{board.normalized_key}_{index}"
        return None

    def _build_bbs_open_target(
        self,
        result_card: BBSResultCard,
        current_url: str,
        board: BBSBoardDefinition,
    ) -> BBSOpenTarget:
        detail_url = result_card.detail_url
        js_call = self._parse_js_call(result_card.onclick)

        if not detail_url:
            for candidate in (result_card.href, result_card.onclick):
                urls = self._extract_url_candidates(candidate, current_url)
                if urls:
                    detail_url = urls[0]
                    break

        bbs_id, ntt_id = self._extract_bbs_identifiers(
            detail_url or "",
            result_card.href,
            result_card.onclick,
        )

        if not bbs_id and result_card.data_bbs_id:
            bbs_id = result_card.data_bbs_id
        if not ntt_id and result_card.data_ntt_id:
            ntt_id = result_card.data_ntt_id

        if not detail_url:
            detail_url = self._build_bbs_detail_url_from_identifiers(bbs_id, ntt_id, current_url)

        canonical_id = result_card.canonical_id or self._build_bbs_canonical_id_from_parts(
            board=board,
            index=result_card.row_index,
            detail_url=detail_url,
            bbs_id=bbs_id,
            ntt_id=ntt_id,
        )

        function_name = (js_call or {}).get("function_name", "")
        popup_args = (js_call or {}).get("args", [])

        if detail_url:
            return BBSOpenTarget(
                mode="direct_url",
                detail_url=detail_url,
                popup_function=function_name or None,
                popup_args=popup_args,
                canonical_id=canonical_id,
                requires_click=False,
            )

        normalized_function = function_name.casefold() if function_name else ""
        if result_card.target_attr == "_blank" or normalized_function in {"window.open", "open", "bbspopup"}:
            return BBSOpenTarget(
                mode="popup_click",
                detail_url=None,
                popup_function=function_name or None,
                popup_args=popup_args,
                canonical_id=canonical_id,
                requires_click=True,
                reason="click_required_popup",
            )

        if function_name:
            return BBSOpenTarget(
                mode="click_only",
                detail_url=None,
                popup_function=function_name,
                popup_args=popup_args,
                canonical_id=canonical_id,
                requires_click=True,
                reason="click_required_function",
            )

        if result_card.href or result_card.onclick:
            return BBSOpenTarget(
                mode="click_only",
                detail_url=None,
                canonical_id=canonical_id,
                requires_click=True,
                reason="click_required_fallback",
            )

        return BBSOpenTarget(
            mode="unresolved",
            detail_url=None,
            canonical_id=canonical_id,
            requires_click=False,
            reason="missing_detail_target",
        )

    async def _extract_bbs_result_cards(
        self,
        page: Page,
        board: BBSBoardDefinition,
    ) -> list[BBSResultCard]:
        container = await self._find_bbs_result_container(page)
        if container is None:
            return []

        row_selector, rows = await self._find_bbs_result_rows(container)
        if not row_selector or rows is None:
            return []

        current_url = page.url
        results: list[BBSResultCard] = []
        try:
            row_count = await rows.count()
        except Exception:
            row_count = 0

        for row_index in range(row_count):
            row = rows.nth(row_index)
            link_selector, link = await self._find_bbs_title_link(row)
            if not link_selector or link is None:
                continue

            try:
                title = self._clean_text(await link.inner_text())
            except Exception:
                title = ""

            try:
                onclick = await link.get_attribute("onclick") or ""
            except Exception:
                onclick = ""

            try:
                href = await link.get_attribute("href") or ""
            except Exception:
                href = ""

            try:
                target_attr = await link.get_attribute("target") or ""
            except Exception:
                target_attr = ""

            try:
                data_bbs_id = await link.get_attribute("data-bbs-id") or ""
            except Exception:
                data_bbs_id = ""

            try:
                data_ntt_id = await link.get_attribute("data-ntt-id") or ""
            except Exception:
                data_ntt_id = ""

            try:
                row_text = self._clean_text(await row.inner_text())
            except Exception:
                row_text = ""

            try:
                row_html = await row.inner_html()
            except Exception:
                row_html = ""

            try:
                link_html = await link.evaluate("(node) => node.outerHTML")
            except Exception:
                link_html = ""

            meta = ""
            preview = ""
            if row_text:
                if title and row_text.startswith(title):
                    remainder = row_text[len(title):].strip()
                else:
                    remainder = row_text
                meta = remainder[:160]
                preview = remainder[:320]

            detail_url = self._resolve_bbs_detail_url(onclick, href, current_url)
            canonical_id = self._build_bbs_canonical_id(detail_url, board, row_index)
            if not title and not href and not onclick and not data_bbs_id and not data_ntt_id:
                continue
            if not self._is_bbs_article_link(title, href, onclick):
                continue

            results.append(
                BBSResultCard(
                    title=title,
                    meta=meta,
                    preview=preview,
                    onclick=onclick,
                    href=href,
                    detail_url=detail_url,
                    canonical_id=canonical_id,
                    target_attr=target_attr,
                    link_html=link_html,
                    data_bbs_id=data_bbs_id,
                    data_ntt_id=data_ntt_id,
                    row_html=row_html,
                    row_selector=row_selector,
                    row_index=row_index,
                )
            )

        if results:
            self._debug_dump_text(
                f"bbs_results_{board.normalized_key or 'board'}.json",
                json.dumps([card.__dict__ for card in results[:20]], ensure_ascii=False, indent=2),
            )
        return results

    async def _submit_bbs_query(
        self,
        page: Page,
        query: str,
        board: BBSBoardDefinition,
    ) -> str:
        logger.info("BBS board filter start: board=%s", board.label)
        filter_method = await self._apply_bbs_board_filter(page, board)
        logger.info(
            "BBS board filter applied: board=%s method=%s url=%s",
            board.label,
            filter_method,
            page.url,
        )

        await page.fill(OLTA_SELECTORS["bbs"]["search_input"], "")
        await page.fill(OLTA_SELECTORS["bbs"]["search_input"], query)
        logger.info(
            "BBS query submit: board=%s query=%s url=%s",
            board.label,
            query,
            page.url,
        )
        await page.evaluate(OLTA_SELECTORS["bbs"]["search_button_js"])
        await self._wait_for_bbs_refresh(page)
        logger.info(
            "BBS query complete: board=%s query=%s url=%s",
            board.label,
            query,
            page.url,
        )
        return filter_method

    async def search(
        self,
        session,
        queries: list[str],
        categories: list[str] | None = None,
        on_progress: ProgressCallback = None,
    ) -> list[CrawlResult]:
        try:
            context = await self.ensure_browser()
            return await self._real_search(queries, categories, context, on_progress=on_progress)
        except Exception:
            logger.warning("OLTA 크롤링 실패, 빈 결과 반환", exc_info=True)
            return []

    async def _real_search(
        self,
        queries: list[str],
        categories: list[str] | None = None,
        context: BrowserContext | None = None,
        on_progress: ProgressCallback = None,
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
                cards = await self._collect_query_cards(
                    page,
                    query,
                    categories,
                    query_page_limit,
                    on_progress=on_progress,
                )
                for card in cards:
                    existing = cards_by_id.get(card.id)
                    if not existing or card.relevance_score > existing.relevance_score:
                        cards_by_id[card.id] = card

            ranked_cards = sorted(cards_by_id.values(), key=lambda item: item.relevance_score, reverse=True)
            limited_cards = ranked_cards[: settings.olta_max_detail_fetch]
            details = await self._collect_details(context, limited_cards)

            # 로그인 상태이면 18개 각 BBS 게시판 검색(마크 클릭 후 상세 수집)
            if settings.olta_bbs_enabled and self._olta_logged_in:
                shared_page = self._shared_page if self._shared_page and not self._shared_page.is_closed() else None
                bbs_results = await self._search_all_bbs_boards(
                    context,
                    queries[:2],
                    page=shared_page,
                    on_progress=on_progress,
                )
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
        on_progress: ProgressCallback = None,
    ) -> list[SearchCard]:
        all_cards = []
        for collection_id in self._resolve_collection_ids(categories):
            cards = await self._collect_collection_cards(
                page,
                query,
                collection_id,
                page_limit,
                on_progress=on_progress,
            )
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
        on_progress: ProgressCallback = None,
    ) -> list[SearchCard]:
        board_name = self._get_collection_board_name(collection_id)
        await self._go_to_query(page, query)
        await page.evaluate(f"doCollection('{collection_id}')")
        await self._wait_for_collection_results(page)

        sub_boards = await self._discover_sub_boards(page)
        if not sub_boards:
            await self._emit_collection_progress(
                on_progress,
                board_name=board_name,
                status="collecting",
            )
            cards = await self._collect_collection_result_pages(
                page,
                query,
                page_limit,
                type_label=self._get_collection_type_label(collection_id),
            )
            await self._emit_collection_progress(
                on_progress,
                board_name=board_name,
                collected_count=len(cards),
                status="done",
            )
            return cards

        cards_by_id: dict[str, SearchCard] = {}
        selected_any_sub_board = False
        for sub_board in sub_boards:
            sub_board_name = self._clean_text(sub_board.get("label", ""))
            if not sub_board_name:
                continue

            sub_board_count = int(sub_board.get("count", -1))
            if sub_board_count == 0:
                await self._emit_collection_progress(
                    on_progress,
                    board_name=board_name,
                    sub_board_name=sub_board_name,
                    skipped=True,
                    status="skipped",
                )
                continue

            await self._emit_collection_progress(
                on_progress,
                board_name=board_name,
                sub_board_name=sub_board_name,
                status="collecting",
            )
            if not await self._select_sub_board(page, sub_board):
                logger.info(
                    "Main collection sub-board selection failed: collection=%s sub_board=%s",
                    collection_id,
                    sub_board_name,
                )
                continue

            selected_any_sub_board = True
            sub_board_cards = await self._collect_collection_result_pages(
                page,
                query,
                page_limit,
                type_label=self._get_collection_type_label(collection_id, sub_board_name),
            )
            for card in sub_board_cards:
                existing = cards_by_id.get(card.id)
                if not existing or card.relevance_score > existing.relevance_score:
                    cards_by_id[card.id] = card

            await self._emit_collection_progress(
                on_progress,
                board_name=board_name,
                sub_board_name=sub_board_name,
                collected_count=len(sub_board_cards),
                status="done",
            )

            await page.evaluate(f"doCollection('{collection_id}')")
            await self._wait_for_collection_results(page)

        if selected_any_sub_board:
            return list(cards_by_id.values())

        await self._emit_collection_progress(
            on_progress,
            board_name=board_name,
            status="collecting",
        )
        cards = await self._collect_collection_result_pages(
            page,
            query,
            page_limit,
            type_label=self._get_collection_type_label(collection_id),
        )
        await self._emit_collection_progress(
            on_progress,
            board_name=board_name,
            collected_count=len(cards),
            status="done",
        )
        return cards

    def _coerce_bbs_board(self, board: BBSBoardDefinition | str) -> BBSBoardDefinition:
        if isinstance(board, BBSBoardDefinition):
            return board

        label = self._clean_text(str(board))
        return BBSBoardDefinition(
            label=label,
            value=label,
            normalized_key=self._normalize_bbs_label(label),
            type_label=f"기타/{label}",
        )

    async def _extract_bbs_detail_text(self, page: Page) -> str:
        best_text = ""
        for selector in OLTA_SELECTORS["bbs"]["detail_content_selectors"]:
            try:
                locator = page.locator(selector).first
                if await locator.count() == 0:
                    continue
                text = await locator.inner_text()
                cleaned = self._extract_meaningful_content(text)
                if len(cleaned) > len(best_text):
                    best_text = cleaned
            except Exception:
                continue

        if best_text:
            return best_text

        raw_body = await page.locator("body").inner_text()
        return self._extract_meaningful_content(raw_body)

    async def _locate_bbs_result_link(self, page: Page, result_card: BBSResultCard) -> Locator | None:
        if result_card.row_selector:
            rows = page.locator(result_card.row_selector)
            try:
                if await rows.count() > result_card.row_index:
                    row = rows.nth(result_card.row_index)
                    for selector in OLTA_SELECTORS["bbs"].get("result_title_link_selectors", []):
                        links = row.locator(selector)
                        try:
                            link_count = await links.count()
                        except Exception:
                            continue

                        for link_index in range(link_count):
                            link = links.nth(link_index)
                            try:
                                href = await link.get_attribute("href") or ""
                                onclick = await link.get_attribute("onclick") or ""
                                title = self._clean_text(await link.inner_text())
                            except Exception:
                                continue

                            if result_card.href and href == result_card.href:
                                return link
                            if result_card.onclick and onclick == result_card.onclick:
                                return link
                            if result_card.title and title == result_card.title:
                                return link

                    _, fallback_link = await self._find_bbs_title_link(row)
                    if fallback_link is not None:
                        return fallback_link
            except Exception:
                pass

        for selector in OLTA_SELECTORS["bbs"].get("result_link_selectors", []):
            links = page.locator(selector)
            try:
                link_count = await links.count()
            except Exception:
                continue

            for link_index in range(link_count):
                link = links.nth(link_index)
                try:
                    href = await link.get_attribute("href") or ""
                    onclick = await link.get_attribute("onclick") or ""
                    title = self._clean_text(await link.inner_text())
                except Exception:
                    continue

                if result_card.href and href == result_card.href:
                    return link
                if result_card.onclick and onclick == result_card.onclick:
                    return link
                if result_card.title and title == result_card.title:
                    return link

        return None

    async def _detect_bbs_open_result(
        self,
        page: Page,
        before_url: str,
        popup_task: asyncio.Task | None = None,
    ) -> dict:
        settings = get_settings()
        timeout_seconds = max(0.5, settings.olta_bbs_same_tab_wait_timeout_ms / 1000)
        deadline = asyncio.get_running_loop().time() + timeout_seconds

        try:
            while asyncio.get_running_loop().time() < deadline:
                if popup_task is not None and popup_task.done():
                    try:
                        popup_page = popup_task.result()
                    except Exception:
                        popup_page = None
                    if popup_page is not None:
                        try:
                            await popup_page.wait_for_load_state(
                                "domcontentloaded",
                                timeout=settings.olta_bbs_detail_ready_timeout_ms,
                            )
                        except Exception:
                            pass
                        return {"mode": "popup", "target_page": popup_page}

                if page.url != before_url:
                    return {"mode": "same_tab", "target_page": page}

                for selector in OLTA_SELECTORS["bbs"].get("detail_ready_selectors", []):
                    try:
                        locator = page.locator(selector).first
                        if await locator.count() > 0:
                            return {"mode": "same_tab", "target_page": page, "selector": selector}
                    except Exception:
                        continue

                for selector in OLTA_SELECTORS["bbs"].get("modal_selectors", []):
                    try:
                        locator = page.locator(selector).first
                        if await locator.count() > 0:
                            return {"mode": "modal", "target_page": page, "selector": selector}
                    except Exception:
                        continue

                for selector in OLTA_SELECTORS["bbs"].get("iframe_selectors", []):
                    try:
                        locator = page.locator(selector).first
                        if await locator.count() > 0:
                            return {"mode": "iframe", "target_page": page, "selector": selector}
                    except Exception:
                        continue

                await asyncio.sleep(0.2)
        finally:
            if popup_task is not None and not popup_task.done():
                popup_task.cancel()
                try:
                    await popup_task
                except Exception:
                    pass

        return {"mode": "no_change", "target_page": None}

    async def _open_bbs_target(
        self,
        page: Page,
        result_card: BBSResultCard,
        open_target: BBSOpenTarget,
    ) -> dict | None:
        settings = get_settings()
        restore_url = page.url

        if open_target.mode == "direct_url" and open_target.detail_url:
            logger.debug(
                "BBS direct detail open: title=%s url=%s",
                result_card.title,
                open_target.detail_url,
            )
            await self._settle_navigation(page)
            await page.goto(open_target.detail_url, wait_until="domcontentloaded")
            try:
                await page.wait_for_load_state(
                    "networkidle",
                    timeout=settings.olta_bbs_detail_ready_timeout_ms,
                )
            except Exception:
                pass
            return {
                "mode": "direct_url",
                "target_page": page,
                "restore_url": restore_url,
                "close_after": False,
            }

        link = await self._locate_bbs_result_link(page, result_card)
        if link is None:
            return None

        popup_task = asyncio.create_task(
            page.wait_for_event("popup", timeout=settings.olta_bbs_popup_wait_timeout_ms)
        )
        try:
            await link.click()
        except Exception:
            if not popup_task.done():
                popup_task.cancel()
                try:
                    await popup_task
                except Exception:
                    pass
            return None

        opened = await self._detect_bbs_open_result(page, restore_url, popup_task)
        if opened.get("mode") == "no_change":
            return None

        opened["restore_url"] = restore_url
        opened["close_after"] = opened.get("mode") == "popup"
        return opened

    async def _collect_bbs_detail_from_target(
        self,
        board: BBSBoardDefinition,
        result_card: BBSResultCard,
        open_target: BBSOpenTarget,
        opened: dict,
        page_index: int,
        index: int,
        seen_ids: set[str],
    ) -> CrawlResult | None:
        target_page = opened.get("target_page")
        if target_page is None:
            return None

        card_id = open_target.canonical_id or result_card.canonical_id
        if not card_id:
            card_id = f"olta_bbs_{board.normalized_key}_{page_index}_{index}"

        if card_id in seen_ids:
            return None

        try:
            await target_page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass

        try:
            await target_page.wait_for_load_state(
                "networkidle",
                timeout=get_settings().olta_bbs_detail_ready_timeout_ms,
            )
        except Exception:
            pass

        detail_url = open_target.detail_url or target_page.url
        content = await self._extract_bbs_detail_text(target_page)
        comments = await self._extract_comments(target_page)

        if not content or "500 Internal Server error" in content:
            content = "\n".join(part for part in [result_card.meta, result_card.preview] if part)
            if not content:
                return None

        full_content = "\n".join(part for part in [result_card.meta, content] if part)
        if comments:
            full_content += f"\n\n[comments]\n{comments}"

        preview_text = content[:180] + "..." if len(content) > 180 else content
        seen_ids.add(card_id)

        return CrawlResult(
            id=card_id,
            title=result_card.title or f"{board.label} item {index + 1}",
            type=board.type_label,
            content=full_content,
            preview=preview_text,
            url=detail_url,
            relevance_score=max(0.1, 0.85 - (index * 0.04) - (page_index * 0.03)),
            document_year=self._extract_document_year(full_content),
            comments=comments,
            crawled_at=datetime.now(),
        )

    async def _is_bbs_search_page_ready(self, page: Page) -> bool:
        try:
            if await page.locator(OLTA_SELECTORS["bbs"]["search_input"]).count() == 0:
                return False
        except Exception:
            return False

        for selector in OLTA_SELECTORS["bbs"].get("page_ready_selectors", []):
            try:
                if await page.locator(selector).count() > 0:
                    return True
            except Exception:
                continue
        return True

    async def _settle_navigation(self, page: Page) -> None:
        """Wait for any in-flight navigation to finish before starting a new one."""
        for state in ("load", "domcontentloaded"):
            try:
                await page.wait_for_load_state(state, timeout=2000)
            except Exception:
                pass
        await asyncio.sleep(0.3)

    async def _restore_bbs_page_state(
        self,
        page: Page,
        board: BBSBoardDefinition,
        query: str,
        restore_url: str | None,
        page_index: int,
    ) -> bool:
        settings = get_settings()

        if restore_url:
            if page.url == restore_url and await self._is_bbs_search_page_ready(page):
                logger.debug("BBS restore skipped because page is already ready: board=%s page=%d", board.label, page_index + 1)
                return True

            try:
                await self._settle_navigation(page)
                await page.go_back(wait_until="domcontentloaded")
                await self._wait_for_bbs_refresh(page)
                if await self._is_bbs_search_page_ready(page):
                    logger.debug("BBS restore success via go_back: board=%s page=%d", board.label, page_index + 1)
                    return True
            except Exception:
                pass

            try:
                await self._settle_navigation(page)
                if page.url == restore_url:
                    await self._wait_for_bbs_refresh(page)
                    if await self._is_bbs_search_page_ready(page):
                        logger.debug("BBS restore skipped goto (same URL already): board=%s page=%d", board.label, page_index + 1)
                        return True
                await page.goto(restore_url, wait_until="domcontentloaded")
                await self._wait_for_bbs_refresh(page)
                if await self._is_bbs_search_page_ready(page):
                    logger.debug("BBS restore success via goto: board=%s page=%d", board.label, page_index + 1)
                    return True
            except Exception:
                pass

        try:
            await self._settle_navigation(page)
            search_url = urljoin(settings.olta_base_url, OLTA_SELECTORS["bbs"]["entry_url"])
            await page.goto(search_url, wait_until="domcontentloaded")
            await self._submit_bbs_query(page, query, board)
            if page_index > 0:
                await page.evaluate("(value) => doPaging(String(value))", page_index * 10)
                await self._wait_for_bbs_refresh(page)
            if await self._is_bbs_search_page_ready(page):
                logger.debug("BBS restore success via rebuild: board=%s page=%d", board.label, page_index + 1)
                return True
        except Exception:
            logger.debug("BBS restore rebuild failed: board=%s page=%d", board.label, page_index + 1, exc_info=True)

        return False

    async def _collect_bbs_result_from_url(
        self,
        auth_context: BrowserContext,
        board: BBSBoardDefinition,
        result_card: BBSResultCard,
        page_index: int,
        index: int,
        seen_ids: set[str],
        page: Page | None = None,
    ) -> CrawlResult | None:
        if not result_card.detail_url:
            return None
        settings = get_settings()
        target_page = page
        if target_page is None:
            target_page = await auth_context.new_page()
            target_page.set_default_timeout(settings.playwright_timeout)

        open_target = BBSOpenTarget(
            mode="direct_url",
            detail_url=result_card.detail_url,
            canonical_id=result_card.canonical_id,
            requires_click=False,
        )
        opened = await self._open_bbs_target(target_page, result_card, open_target)
        if opened is None:
            if page is None:
                await target_page.close()
            return None

        try:
            return await self._collect_bbs_detail_from_target(
                board=board,
                result_card=result_card,
                open_target=open_target,
                opened=opened,
                page_index=page_index,
                index=index,
                seen_ids=seen_ids,
            )
        finally:
            if opened.get("close_after"):
                try:
                    await opened["target_page"].close()
                except Exception:
                    pass
            if page is None:
                await target_page.close()
            else:
                await self._restore_bbs_page_state(
                    target_page,
                    board,
                    "",
                    opened.get("restore_url"),
                    page_index,
                )

    # ── BBS bbsId → 게시판 라벨 매핑 (알려진 값) ──
    _BBS_ID_LABEL_MAP: dict[str, str] = {
        "BBSMSTR_000000000151": "질의응답",
        "BBSMSTR_000000000181": "지방세상담",
        "BBSMSTR_000000000211": "자유게시판",
        "BBSMSTR_000000000221": "실무자료",
        "BBSMSTR_000000000011": "공지사항",
        "BBSMSTR_000000000081": "이용안내 Q&A",
        "BBSMSTR_000000000214": "시가표준액",
        "BBSMSTR_000000000261": "참고자료",
        "BBSMSTR_000000000342": "쟁송사무지원",
        "BBSMSTR_000000000343": "쟁송사무지원 사례",
        "BBSMSTR_000000000361": "전국단위사건 알림방",
        "BBSMSTR_000000000362": "쟁송사무워크숍 자료",
        "BBSMSTR_000000000371": "쟁송사무지원 신청사례",
        "BBSMSTR_000000000391": "소통마당",
        "BBSMSTR100000000001": "기타BBS",
    }

    _BBS_POPUP_URL_RE = re.compile(
        r"bbsPopUp\(\s*['\"]([^'\"]+)['\"]",
    )

    async def _extract_bbs_popup_links(self, page: Page) -> list[dict]:
        """검색 결과 페이지에서 bbsPopUp(URL) 패턴의 링크를 추출한다."""
        raw_links = await page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('a[onclick*="bbsPopUp"]').forEach((a) => {
                    const onclick = a.getAttribute('onclick') || '';
                    const text = (a.textContent || '').replace(/<[^>]*>/g, '').replace(/\\s+/g, ' ').trim();
                    results.push({ onclick, text });
                });
                return results;
            }
            """
        )

        links = []
        for item in raw_links:
            onclick = item.get("onclick", "")
            title = self._clean_text(item.get("text", ""))
            if not title or len(title) < 3:
                continue

            # bbsPopUp('https://...selectBoardArticle.do?nttId=...&bbsId=...') 패턴 추출
            # HTML 엔티티 디코딩
            onclick_decoded = onclick.replace("&amp;", "&").replace("&#39;", "'").replace("\\'", "'")
            match = self._BBS_POPUP_URL_RE.search(onclick_decoded)
            if not match:
                continue

            url = match.group(1).strip()
            if not url.startswith("http"):
                url = urljoin("https://www.olta.re.kr", url)

            # bbsId, nttId 추출
            bbs_id_match = re.search(r"bbsId=([^&]+)", url)
            ntt_id_match = re.search(r"nttId=(\d+)", url)
            bbs_id = bbs_id_match.group(1) if bbs_id_match else ""
            ntt_id = ntt_id_match.group(1) if ntt_id_match else ""

            board_label = self._BBS_ID_LABEL_MAP.get(bbs_id, bbs_id or "기타BBS")

            links.append({
                "url": url,
                "title": title,
                "bbs_id": bbs_id,
                "ntt_id": ntt_id,
                "board_label": board_label,
            })

        return links

    async def _fetch_bbs_detail_direct(
        self,
        auth_context: BrowserContext,
        url: str,
        title: str,
        card_id: str,
        board_label: str,
    ) -> CrawlResult | None:
        """BBS 상세 페이지를 URL로 직접 열어 콘텐츠를 수집한다."""
        settings = get_settings()
        detail_page = await auth_context.new_page()
        detail_page.set_default_timeout(settings.playwright_timeout)
        try:
            await detail_page.goto(url, wait_until="domcontentloaded")
            try:
                await detail_page.wait_for_load_state(
                    "networkidle",
                    timeout=settings.olta_bbs_detail_ready_timeout_ms,
                )
            except Exception:
                pass

            content = await self._extract_bbs_detail_text(detail_page)
            comments = await self._extract_comments(detail_page)

            if not content or "500 Internal Server error" in content:
                return None

            full_content = content
            if comments:
                full_content += f"\n\n[답변/댓글]\n{comments}"

            preview = content[:180] + "..." if len(content) > 180 else content
            score = max(0.1, 0.80)

            return CrawlResult(
                id=card_id,
                title=title,
                type=f"기타/{board_label}",
                content=full_content,
                preview=preview,
                url=url,
                relevance_score=score,
                document_year=self._extract_document_year(content),
                comments=comments,
                crawled_at=datetime.now(),
            )
        except Exception:
            logger.debug("BBS direct fetch failed: url=%s", url, exc_info=True)
            return None
        finally:
            try:
                await detail_page.close()
            except Exception:
                pass

    async def _search_all_bbs_boards(
        self,
        auth_context: BrowserContext,
        queries: list[str],
        page: Page | None = None,
        on_progress: ProgressCallback = None,
    ) -> list[CrawlResult]:
        """통합 BBS 검색: 전체 검색 후 bbsPopUp(URL) 링크를 추출하여 직접 수집."""
        settings = get_settings()
        if not queries:
            return []

        search_page = page
        owns_page = page is None
        if owns_page:
            search_page = await auth_context.new_page()
        search_page.set_default_timeout(settings.playwright_timeout)

        all_results: list[CrawlResult] = []
        seen_ids: set[str] = set()
        # 게시판별 수집 카운트 (progress 보고용)
        board_counts: dict[str, int] = {}

        try:
            search_url = urljoin(settings.olta_base_url, OLTA_SELECTORS["bbs"]["entry_url"])
            max_pages = settings.olta_bbs_max_pages_per_board * 3  # 통합 검색이므로 더 많은 페이지

            for query in queries:
                # 검색 페이지로 이동 + 검색 실행 (게시판 필터 없이)
                await self._settle_navigation(search_page)
                if search_page.is_closed():
                    if owns_page:
                        search_page = await auth_context.new_page()
                        search_page.set_default_timeout(settings.playwright_timeout)
                    else:
                        logger.warning("BBS shared search page closed, aborting")
                        break

                await search_page.goto(search_url, wait_until="domcontentloaded")
                await self._wait_for_bbs_refresh(search_page)
                await search_page.fill(OLTA_SELECTORS["bbs"]["search_input"], query)

                # doSearchPu()는 form submit → 페이지 reload이므로
                # expect_navigation으로 감싸서 네비게이션 완료를 대기
                try:
                    async with search_page.expect_navigation(
                        wait_until="domcontentloaded", timeout=15000,
                    ):
                        await search_page.evaluate(OLTA_SELECTORS["bbs"]["search_button_js"])
                except Exception:
                    # 이미 네비게이션이 끝났거나 타임아웃
                    pass
                await self._wait_for_bbs_refresh(search_page)

                logger.info("BBS unified search started: query=%s url=%s", query, search_page.url)

                # 여러 페이지를 순회하며 bbsPopUp 링크 수집
                collected_links: list[dict] = []
                for page_index in range(max_pages):
                    if page_index > 0:
                        try:
                            async with search_page.expect_navigation(
                                wait_until="domcontentloaded", timeout=10000,
                            ):
                                await search_page.evaluate(
                                    "(v) => doPaging(String(v))", page_index * 10,
                                )
                        except Exception:
                            pass
                        await self._wait_for_bbs_refresh(search_page)

                    page_links = await self._extract_bbs_popup_links(search_page)
                    if not page_links:
                        logger.info(
                            "BBS page %d has no bbsPopUp links, stopping pagination",
                            page_index + 1,
                        )
                        break

                    new_count = 0
                    for link in page_links:
                        ntt_id = link.get("ntt_id", "")
                        bbs_id = link.get("bbs_id", "")
                        card_id = (
                            f"olta_bbs_{bbs_id}_{ntt_id}" if bbs_id and ntt_id
                            else f"olta_bbs_{ntt_id}" if ntt_id
                            else f"olta_bbs_{hash(link['url'])}"
                        )
                        if card_id not in seen_ids:
                            link["card_id"] = card_id
                            collected_links.append(link)
                            seen_ids.add(card_id)
                            new_count += 1

                    logger.info(
                        "BBS page %d: %d bbsPopUp links found, %d new",
                        page_index + 1,
                        len(page_links),
                        new_count,
                    )

                logger.info(
                    "BBS unified search complete: query=%s total_links=%d",
                    query,
                    len(collected_links),
                )

                # 수집된 링크에서 상세 페이지 수집
                # 게시판별로 그룹핑하여 progress 보고
                boards_in_links: dict[str, list[dict]] = {}
                for link in collected_links:
                    bl = link.get("board_label", "기타BBS")
                    boards_in_links.setdefault(bl, []).append(link)

                for board_label, links in boards_in_links.items():
                    await self._emit_collection_progress(
                        on_progress,
                        board_name="기타",
                        sub_board_name=board_label,
                        status="collecting",
                    )

                    board_result_count = 0
                    for link in links:
                        result = await self._fetch_bbs_detail_direct(
                            auth_context,
                            link["url"],
                            link["title"],
                            link["card_id"],
                            board_label,
                        )
                        if result:
                            all_results.append(result)
                            board_result_count += 1

                    board_counts[board_label] = board_counts.get(board_label, 0) + board_result_count
                    await self._emit_collection_progress(
                        on_progress,
                        board_name="기타",
                        sub_board_name=board_label,
                        collected_count=board_counts[board_label],
                        skipped=board_counts[board_label] == 0,
                        status="done" if board_counts[board_label] > 0 else "skipped",
                    )
                    logger.info(
                        "BBS board fetch complete: %s -> %d results",
                        board_label,
                        board_result_count,
                    )

        except Exception:
            logger.warning("BBS unified search failed", exc_info=True)
        finally:
            if owns_page:
                try:
                    await search_page.close()
                except Exception:
                    pass

        logger.info(
            "BBS crawl complete: %d results, boards=%s",
            len(all_results),
            {k: v for k, v in board_counts.items() if v > 0},
        )
        return all_results

    async def _search_single_bbs_board(
        self,
        auth_context: BrowserContext,
        query: str,
        board_name: BBSBoardDefinition | str,
        page: Page | None = None,
    ) -> list[CrawlResult]:
        """Search one BBS board with board-specific filtering and BBS-specific result parsing."""
        settings = get_settings()
        board = self._coerce_bbs_board(board_name)
        search_page = page
        if search_page is None:
            search_page = await auth_context.new_page()
        search_page.set_default_timeout(settings.playwright_timeout)
        results: list[CrawlResult] = []
        seen_ids: set[str] = set()

        try:
            logger.info(
                "BBS single-board start: board=%s query=%s shared_page=%s",
                board.label,
                query,
                page is not None,
            )
            search_url = urljoin(settings.olta_base_url, OLTA_SELECTORS["bbs"]["entry_url"])
            await self._settle_navigation(search_page)
            await search_page.goto(search_url, wait_until="domcontentloaded")
            logger.info("BBS board page opened: board=%s url=%s", board.label, search_page.url)
            filter_method = await self._submit_bbs_query(search_page, query, board)
            active_selector = await self._get_bbs_result_link_selector(search_page)
            logger.debug(
                "BBS board query started: board=%s query=%s filter=%s selector=%s",
                board.label,
                query,
                filter_method,
                active_selector,
            )

            for page_index in range(settings.olta_bbs_max_pages_per_board):
                if page_index > 0:
                    offset = page_index * 10
                    try:
                        await search_page.evaluate("(value) => doPaging(String(value))", offset)
                        await self._wait_for_bbs_refresh(search_page)
                    except Exception:
                        break

                result_cards = await self._extract_bbs_result_cards(search_page, board)
                selector = await self._get_bbs_result_link_selector(search_page)
                logger.info(
                    "BBS results page scan: board=%s page=%d selector=%s count=%d",
                    board.label,
                    page_index + 1,
                    selector or "none",
                    len(result_cards),
                )
                if not result_cards:
                    empty_detected = False
                    for empty_sel in OLTA_SELECTORS["bbs"].get("empty_state_selectors", []):
                        try:
                            if await search_page.locator(empty_sel).count() > 0:
                                empty_detected = True
                                break
                        except Exception:
                            pass
                    if empty_detected:
                        logger.info("BBS board empty (no-data indicator): board=%s query=%s, skipping", board.label, query)
                        break

                    if page_index == 0:
                        logger.warning(
                            "BBS results empty after in-board search: board=%s query=%s. Reapplying board filter on result page.",
                            board.label,
                            query,
                        )
                        fallback_filter_method = await self._apply_bbs_board_filter(search_page, board)
                        logger.info(
                            "BBS fallback filter applied: board=%s method=%s url=%s",
                            board.label,
                            fallback_filter_method,
                            search_page.url,
                        )
                        result_cards = await self._extract_bbs_result_cards(search_page, board)
                        selector = await self._get_bbs_result_link_selector(search_page)
                        logger.info(
                            "BBS fallback results scan: board=%s page=%d selector=%s count=%d",
                            board.label,
                            page_index + 1,
                            selector or "none",
                            len(result_cards),
                        )

                if not result_cards:
                    try:
                        all_links = await search_page.locator("a[onclick], a[href]").count()
                    except Exception:
                        all_links = 0
                    logger.debug(
                        "BBS board produced no result cards: board=%s page=%d total_links=%d",
                        board.label,
                        page_index,
                        all_links,
                    )
                    break

                for index, result_card in enumerate(result_cards):
                    opened: dict | None = None
                    restore_failed = False
                    try:
                        open_target = self._build_bbs_open_target(
                            result_card=result_card,
                            current_url=search_page.url,
                            board=board,
                        )
                        logger.info(
                            "BBS result target: board=%s page=%d index=%d title=%s mode=%s detail=%s reason=%s",
                            board.label,
                            page_index + 1,
                            index,
                            result_card.title[:80],
                            open_target.mode,
                            open_target.detail_url or "",
                            open_target.reason or "",
                        )
                        if index < 3:
                            logger.debug(
                                "BBS result raw: board=%s page=%d index=%d href=%s onclick=%s target=%s",
                                board.label,
                                page_index + 1,
                                index,
                                result_card.href,
                                result_card.onclick,
                                result_card.target_attr,
                            )

                        if open_target.mode == "unresolved":
                            continue

                        logger.debug(
                            "BBS result collect start: board=%s page=%d index=%d mode=%s",
                            board.label,
                            page_index + 1,
                            index,
                            open_target.mode,
                        )
                        opened = await self._open_bbs_target(search_page, result_card, open_target)
                        if opened is None:
                            logger.warning(
                                "BBS result open failed: board=%s page=%d index=%d mode=%s",
                                board.label,
                                page_index + 1,
                                index,
                                open_target.mode,
                            )
                            continue

                        result = await self._collect_bbs_detail_from_target(
                            board=board,
                            result_card=result_card,
                            open_target=open_target,
                            opened=opened,
                            page_index=page_index,
                            index=index,
                            seen_ids=seen_ids,
                        )

                        if result:
                            results.append(result)
                            logger.debug(
                                "BBS result collect complete: board=%s page=%d index=%d result_id=%s",
                                board.label,
                                page_index + 1,
                                index,
                                result.id,
                            )
                    except Exception:
                        logger.debug(
                            "BBS result collection failed: board=%s index=%d",
                            board.label,
                            index,
                            exc_info=True,
                        )
                    finally:
                        if opened and opened.get("close_after") and opened.get("target_page") is not None:
                            try:
                                await opened["target_page"].close()
                            except Exception:
                                pass

                        if opened and opened.get("mode") not in {"popup"}:
                            restored = await self._restore_bbs_page_state(
                                search_page,
                                board,
                                query,
                                opened.get("restore_url"),
                                page_index,
                            )
                            if not restored:
                                logger.warning(
                                    "BBS restore failed: board=%s page=%d index=%d",
                                    board.label,
                                    page_index + 1,
                                    index,
                                )
                                restore_failed = True
                        elif opened:
                            await self._wait_for_bbs_refresh(search_page)

                    if restore_failed:
                        return results

            if results:
                logger.info("BBS board search: %s -> %d results (query=%s)", board.label, len(results), query)
            return results
        except Exception:
            logger.warning("BBS board search failed: %s (query=%s)", board.label, query, exc_info=True)
            return []
        finally:
            if page is None:
                await search_page.close()

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
        """검색 결과의 각 마크를 클릭하여 상세/원문 페이지에서 자료를 수집한다."""
        detail_page: Page | None = None
        try:
            # 마크 클릭 후 새 창(window.open)으로 열리는 것을 기다림
            async with page.expect_popup(timeout=5000) as popup_info:
                await links.nth(index).click()
            detail_page = await popup_info.value
        except Exception:
            # 새 창이 아닌 경우: 같은 페이지 내 네비게이션 시도
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

            # ID ?앹꽦
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
            title = self._clean_text(info.get("title", f"{board_name} 게시물{index + 1}"))
            meta = self._clean_text(info.get("meta", ""))

            full_content = "\n".join(part for part in [meta, content] if part)
            if comments:
                full_content += f"\n\n[?볤?/?듬?]\n{comments}"

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
            # 팝업인 경우 닫고, 같은 페이지 네비게이션인 경우 다시 돌아가기
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
        type_override: str | None = None,
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
            card = self._build_search_card(
                raw_card,
                query,
                position,
                page_index,
                type_override=type_override,
            )
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
        type_override: str | None = None,
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
            # bbsId로 게시판 분류 (각 게시판에서 type이 달라져야 함)
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
        resolved_type_label = type_override or type_label
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
            type=resolved_type_label,
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
        """게시글 본문/답변을 추출한다."""
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
                full_content += f"\n\n[?볤?/?듬?]\n{comments}"

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
            "처분청명",
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
            try:
                content = re.sub(pattern, "", content, flags=re.MULTILINE)
            except re.error:
                pass
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

    def _get_collection_board_name(self, collection_id: str) -> str:
        popup_name = COLLECTION_POPUP_MAP.get(collection_id)
        return POPUP_TYPE_MAP.get(popup_name, collection_id)

    def _get_collection_type_label(
        self,
        collection_id: str,
        sub_board_name: str | None = None,
    ) -> str:
        board_name = self._get_collection_board_name(collection_id)
        cleaned_sub_board_name = self._clean_text(sub_board_name or "")
        if cleaned_sub_board_name:
            return f"{board_name}/{cleaned_sub_board_name}"
        return board_name

    async def _emit_collection_progress(
        self,
        on_progress: ProgressCallback,
        *,
        board_name: str,
        sub_board_name: str | None = None,
        collected_count: int = 0,
        skipped: bool = False,
        status: str = "pending",
    ) -> None:
        if on_progress is None:
            return

        await on_progress(
            BoardCollectionStat(
                board_name=board_name,
                sub_board_name=sub_board_name,
                collected_count=collected_count,
                skipped=skipped,
                status=status,
            )
        )

    async def _wait_for_collection_results(self, page: Page) -> None:
        try:
            await page.wait_for_selector(
                OLTA_SELECTORS["search"]["result_title_links"],
                timeout=5000,
            )
        except Exception:
            try:
                await page.wait_for_load_state("domcontentloaded")
            except Exception:
                pass
        await asyncio.sleep(0.2)

    async def _discover_sub_boards(self, page: Page) -> list[dict]:
        sub_board_selectors = OLTA_SELECTORS["search"].get("sub_board", {})
        tab_container_selectors = sub_board_selectors.get("tab_container_selectors", [])
        tab_link_selectors = sub_board_selectors.get("tab_link_selectors", [])
        count_selectors = sub_board_selectors.get("count_selectors", [])
        known_labels = sub_board_selectors.get("known_labels", [])

        try:
            raw_sub_boards = await page.evaluate(
                """
                ({ tabContainerSelectors, tabLinkSelectors, countSelectors, knownLabels }) => {
                    const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim()
                    const extractCount = (node, text) => {
                        const texts = [text]
                        for (const selector of countSelectors) {
                            try {
                                node.querySelectorAll(selector).forEach((child) => {
                                    texts.push(normalize(child.textContent || child.innerText || ''))
                                })
                            } catch (error) {
                                // ignore selector failures in discovery mode
                            }
                        }

                        for (const source of texts) {
                            const normalized = normalize(source)
                            const match =
                                normalized.match(/\\((\\d[\\d,]*)\\)/) ||
                                normalized.match(/총\\s*(\\d[\\d,]*)\\s*건/i) ||
                                normalized.match(/(\\d[\\d,]*)\\s*건/i)
                            if (match) {
                                return Number((match[1] || '').replace(/,/g, ''))
                            }
                        }

                        return null
                    }

                    const toLabel = (text) => {
                        const stripped = normalize(
                            text
                                .replace(/\\(\\s*\\d[\\d,]*\\s*\\)/g, ' ')
                                .replace(/총\\s*\\d[\\d,]*\\s*건/gi, ' ')
                                .replace(/\\d[\\d,]*\\s*건/gi, ' ')
                                .replace(/\\b\\d[\\d,]*\\b/g, ' ')
                                .replace(/[|/]+/g, ' ')
                        )
                        const matchedKnown = knownLabels.find((label) => stripped.includes(label))
                        return matchedKnown || stripped
                    }

                    const containers = []
                    for (const selector of tabContainerSelectors) {
                        document.querySelectorAll(selector).forEach((node) => containers.push(node))
                    }
                    if (!containers.length) {
                        return []
                    }

                    const candidates = []
                    const seen = new Set()
                    const genericSelectors = ['a[onclick]', 'button[onclick]', 'li[onclick]', 'a', 'button']

                    for (const container of containers) {
                        const nodes = []
                        const nodeSet = new Set()
                        for (const selector of tabLinkSelectors) {
                            try {
                                container.querySelectorAll(selector).forEach((node) => {
                                    if (!nodeSet.has(node)) {
                                        nodeSet.add(node)
                                        nodes.push(node)
                                    }
                                })
                            } catch (error) {
                                // ignore selector failures in discovery mode
                            }
                        }
                        if (!nodes.length) {
                            for (const selector of genericSelectors) {
                                try {
                                    container.querySelectorAll(selector).forEach((node) => {
                                        if (!nodeSet.has(node)) {
                                            nodeSet.add(node)
                                            nodes.push(node)
                                        }
                                    })
                                } catch (error) {
                                    // ignore selector failures in discovery mode
                                }
                            }
                        }

                        for (const node of nodes) {
                            const text = normalize(node.textContent || node.innerText || '')
                            const onclick = node.getAttribute('onclick') || ''
                            const href = node.getAttribute('href') || ''
                            if (!text || text.length > 60) {
                                continue
                            }
                            if (/doCollection\\(/i.test(onclick)) {
                                continue
                            }
                            if (/검색|조회|닫기|열기|더보기|다음|이전|목록/i.test(text)) {
                                continue
                            }

                            const label = toLabel(text)
                            const count = extractCount(node, text)
                            const hasAction = Boolean(onclick || href)
                            const matchedKnown = knownLabels.some((knownLabel) => label.includes(knownLabel))
                            if (!label || label.length < 2) {
                                continue
                            }
                            if (count === null && !hasAction && !matchedKnown) {
                                continue
                            }

                            const key = `${label}::${onclick}::${href}`
                            if (seen.has(key)) {
                                continue
                            }
                            seen.add(key)
                            candidates.push({
                                label,
                                count: count === null ? -1 : count,
                                onclick,
                                href,
                                element_index: candidates.length,
                            })
                        }
                    }

                    return candidates
                }
                """,
                {
                    "tabContainerSelectors": tab_container_selectors,
                    "tabLinkSelectors": tab_link_selectors,
                    "countSelectors": count_selectors,
                    "knownLabels": known_labels,
                },
            )
        except Exception:
            logger.debug("Main collection sub-board discovery failed", exc_info=True)
            return []

        filtered_sub_boards: list[dict] = []
        seen_labels: set[str] = set()
        blocked_labels = {
            self._clean_text(label)
            for label in ("전체", "검색", "조회", "닫기", "열기", "더보기", "다음", "이전", "목록")
        }
        for sub_board in raw_sub_boards:
            label = self._clean_text(sub_board.get("label", ""))
            if not label or label in blocked_labels or label in seen_labels:
                continue
            seen_labels.add(label)
            filtered_sub_boards.append(
                {
                    "label": label,
                    "count": int(sub_board.get("count", -1)),
                    "onclick": sub_board.get("onclick", ""),
                    "href": sub_board.get("href", ""),
                    "element_index": int(sub_board.get("element_index", len(filtered_sub_boards))),
                }
            )
        return filtered_sub_boards

    async def _select_sub_board(self, page: Page, sub_board: dict) -> bool:
        sub_board_selectors = OLTA_SELECTORS["search"].get("sub_board", {})
        tab_container_selectors = sub_board_selectors.get("tab_container_selectors", [])
        tab_link_selectors = sub_board_selectors.get("tab_link_selectors", [])
        target = {
            "label": self._clean_text(sub_board.get("label", "")),
            "onclick": sub_board.get("onclick", ""),
            "href": sub_board.get("href", ""),
            "element_index": int(sub_board.get("element_index", 0)),
        }

        clicked = False
        try:
            clicked = await page.evaluate(
                """
                ({ target, tabContainerSelectors, tabLinkSelectors }) => {
                    const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim()
                    const toLabel = (text) => normalize(
                        text
                            .replace(/\\(\\s*\\d[\\d,]*\\s*\\)/g, ' ')
                            .replace(/총\\s*\\d[\\d,]*\\s*건/gi, ' ')
                            .replace(/\\d[\\d,]*\\s*건/gi, ' ')
                            .replace(/\\b\\d[\\d,]*\\b/g, ' ')
                    )
                    const containers = []
                    for (const selector of tabContainerSelectors) {
                        document.querySelectorAll(selector).forEach((node) => containers.push(node))
                    }
                    const genericSelectors = ['a[onclick]', 'button[onclick]', 'li[onclick]', 'a', 'button']
                    const candidates = []
                    const seen = new Set()

                    for (const container of containers) {
                        const nodes = []
                        const nodeSet = new Set()
                        for (const selector of tabLinkSelectors) {
                            try {
                                container.querySelectorAll(selector).forEach((node) => {
                                    if (!nodeSet.has(node)) {
                                        nodeSet.add(node)
                                        nodes.push(node)
                                    }
                                })
                            } catch (error) {
                                // ignore selector failures
                            }
                        }
                        if (!nodes.length) {
                            for (const selector of genericSelectors) {
                                try {
                                    container.querySelectorAll(selector).forEach((node) => {
                                        if (!nodeSet.has(node)) {
                                            nodeSet.add(node)
                                            nodes.push(node)
                                        }
                                    })
                                } catch (error) {
                                    // ignore selector failures
                                }
                            }
                        }

                        for (const node of nodes) {
                            const label = toLabel(node.textContent || node.innerText || '')
                            const onclick = node.getAttribute('onclick') || ''
                            const href = node.getAttribute('href') || ''
                            const key = `${label}::${onclick}::${href}`
                            if (!label || seen.has(key)) {
                                continue
                            }
                            seen.add(key)
                            candidates.push({ node, label, onclick, href, element_index: candidates.length })
                        }
                    }

                    const candidate =
                        candidates.find((item) =>
                            item.label === target.label &&
                            item.onclick === target.onclick &&
                            item.href === target.href
                        ) ||
                        candidates.find((item) => item.label === target.label && item.element_index === target.element_index) ||
                        candidates.find((item) => item.label === target.label)

                    if (!candidate) {
                        return false
                    }

                    if (typeof candidate.node.click === 'function') {
                        candidate.node.click()
                    } else {
                        candidate.node.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))
                    }
                    return true
                }
                """,
                {
                    "target": target,
                    "tabContainerSelectors": tab_container_selectors,
                    "tabLinkSelectors": tab_link_selectors,
                },
            )
        except Exception:
            logger.debug("Main collection sub-board click failed via DOM lookup", exc_info=True)

        if not clicked:
            raw_action = sub_board.get("onclick") or sub_board.get("href") or ""
            if raw_action.lower().startswith("javascript:"):
                raw_action = raw_action[len("javascript:") :]
            raw_action = raw_action.strip().rstrip(";")
            if raw_action:
                try:
                    await page.evaluate(raw_action)
                    clicked = True
                except Exception:
                    logger.debug("Main collection sub-board click failed via JS action", exc_info=True)

        if not clicked:
            return False

        await self._wait_for_collection_results(page)
        return True

    async def _collect_collection_result_pages(
        self,
        page: Page,
        query: str,
        page_limit: int | None,
        *,
        type_label: str | None = None,
    ) -> list[SearchCard]:
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
                await self._wait_for_collection_results(page)

            page_cards = await self._extract_cards_from_current_page(
                page,
                query,
                page_index,
                type_override=type_label,
            )
            for card in page_cards:
                existing = cards_by_id.get(card.id)
                if not existing or card.relevance_score > existing.relevance_score:
                    cards_by_id[card.id] = card

        return list(cards_by_id.values())

    async def _extract_total_count(self, page: Page) -> int:
        body = await page.locator("body").inner_text()
        match = re.search(r"\(총\s*([\d,]+)건\)", body)
        if not match:
            return 0
        return int(match.group(1).replace(",", ""))

    def _extract_document_year(self, text: str) -> int | None:
        years = re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text or "")
        if not years:
            return None

        numeric_years = [int(year) for year in years]
        current_year = datetime.now().year
        valid_years = [year for year in numeric_years if 1900 <= year <= current_year + 1]
        if not valid_years:
            return None
        return max(valid_years)

    async def _discover_sub_boards(self, page: Page) -> list[dict]:
        sub_board_selectors = OLTA_SELECTORS["search"].get("sub_board", {})
        tab_container_selectors = sub_board_selectors.get("tab_container_selectors", [])
        tab_link_selectors = sub_board_selectors.get("tab_link_selectors", [])
        count_selectors = sub_board_selectors.get("count_selectors", [])
        known_labels = sub_board_selectors.get("known_labels", [])

        try:
            raw_sub_boards = await page.evaluate(
                """
                ({ tabContainerSelectors, tabLinkSelectors, countSelectors, knownLabels }) => {
                    const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim()
                    const stripCountText = (value) => normalize(
                        (value || '')
                            .replace(/\\(\\s*\\d[\\d,]*\\s*\\)/g, ' ')
                            .replace(/\\b\\d[\\d,]*\\b/g, ' ')
                            .replace(/[|/]+/g, ' ')
                    )
                    const extractCount = (node, text) => {
                        const texts = [text]
                        for (const selector of countSelectors) {
                            try {
                                node.querySelectorAll(selector).forEach((child) => {
                                    texts.push(normalize(child.textContent || child.innerText || ''))
                                })
                            } catch (error) {
                                // ignore selector failures in discovery mode
                            }
                        }

                        for (const source of texts) {
                            const normalized = normalize(source)
                            const match = normalized.match(/\\((\\d[\\d,]*)\\)/) || normalized.match(/(\\d[\\d,]*)/)
                            if (match) {
                                return Number((match[1] || '').replace(/,/g, ''))
                            }
                        }

                        return null
                    }

                    const containers = []
                    const containerSet = new Set()
                    for (const selector of tabContainerSelectors) {
                        document.querySelectorAll(selector).forEach((node) => {
                            if (!containerSet.has(node)) {
                                containerSet.add(node)
                                containers.push(node)
                            }
                        })
                    }
                    if (!containers.length) {
                        return []
                    }

                    const candidates = []
                    const seen = new Set()
                    const genericSelectors = ['a[onclick]', 'button[onclick]', 'li[onclick]', 'a', 'button']

                    for (const container of containers) {
                        const nodes = []
                        const nodeSet = new Set()
                        for (const selector of tabLinkSelectors) {
                            try {
                                container.querySelectorAll(selector).forEach((node) => {
                                    if (!nodeSet.has(node)) {
                                        nodeSet.add(node)
                                        nodes.push(node)
                                    }
                                })
                            } catch (error) {
                                // ignore selector failures in discovery mode
                            }
                        }

                        if (!nodes.length) {
                            for (const selector of genericSelectors) {
                                try {
                                    container.querySelectorAll(selector).forEach((node) => {
                                        if (!nodeSet.has(node)) {
                                            nodeSet.add(node)
                                            nodes.push(node)
                                        }
                                    })
                                } catch (error) {
                                    // ignore selector failures in discovery mode
                                }
                            }
                        }

                        for (const node of nodes) {
                            const text = normalize(node.textContent || node.innerText || '')
                            const onclick = node.getAttribute('onclick') || ''
                            const href = node.getAttribute('href') || ''
                            if (!text || text.length > 60) {
                                continue
                            }
                            if (/doCollection\\(/i.test(onclick)) {
                                continue
                            }

                            const label = stripCountText(text)
                            const count = extractCount(node, text)
                            const hasAction = Boolean(onclick || href)
                            const matchedKnown = knownLabels.some((knownLabel) => label.includes(knownLabel))
                            if (!label || label.length < 2) {
                                continue
                            }
                            if (count === null && !hasAction && !matchedKnown) {
                                continue
                            }

                            const key = `${label}::${onclick}::${href}`
                            if (seen.has(key)) {
                                continue
                            }
                            seen.add(key)
                            candidates.push({
                                label,
                                count: count === null ? -1 : count,
                                onclick,
                                href,
                                element_index: candidates.length,
                            })
                        }
                    }

                    return candidates
                }
                """,
                {
                    "tabContainerSelectors": tab_container_selectors,
                    "tabLinkSelectors": tab_link_selectors,
                    "countSelectors": count_selectors,
                    "knownLabels": known_labels,
                },
            )
        except Exception:
            logger.debug("Main collection sub-board discovery failed", exc_info=True)
            return []

        cleaned_known_labels = [
            self._clean_text(label)
            for label in known_labels
            if self._clean_text(label)
        ]
        filtered_sub_boards: list[dict] = []
        seen_labels: set[str] = set()
        blocked_ascii_labels = {
            "all",
            "select",
            "search",
            "close",
            "open",
            "more",
            "next",
            "prev",
            "previous",
            "list",
        }

        for sub_board in raw_sub_boards:
            label = self._clean_text(sub_board.get("label", ""))
            normalized_label = self._normalize_bbs_label(label)
            ascii_label = re.sub(r"[^a-z0-9]+", "", label.casefold())
            if not label or not normalized_label or normalized_label in seen_labels:
                continue
            if ascii_label and ascii_label in blocked_ascii_labels:
                continue

            seen_labels.add(normalized_label)
            filtered_sub_boards.append(
                {
                    "label": label,
                    "count": int(sub_board.get("count", -1)),
                    "onclick": sub_board.get("onclick", ""),
                    "href": sub_board.get("href", ""),
                    "element_index": int(sub_board.get("element_index", len(filtered_sub_boards))),
                    "matches_known_label": any(
                        known_label in label for known_label in cleaned_known_labels
                    ),
                }
            )

        if any(sub_board["matches_known_label"] for sub_board in filtered_sub_boards):
            filtered_sub_boards = [
                sub_board for sub_board in filtered_sub_boards if sub_board["matches_known_label"]
            ]

        for sub_board in filtered_sub_boards:
            sub_board.pop("matches_known_label", None)

        return filtered_sub_boards

    async def _select_sub_board(self, page: Page, sub_board: dict) -> bool:
        sub_board_selectors = OLTA_SELECTORS["search"].get("sub_board", {})
        tab_container_selectors = sub_board_selectors.get("tab_container_selectors", [])
        tab_link_selectors = sub_board_selectors.get("tab_link_selectors", [])
        target = {
            "label": self._clean_text(sub_board.get("label", "")),
            "onclick": sub_board.get("onclick", ""),
            "href": sub_board.get("href", ""),
            "element_index": int(sub_board.get("element_index", 0)),
        }

        clicked = False
        try:
            clicked = await page.evaluate(
                """
                ({ target, tabContainerSelectors, tabLinkSelectors }) => {
                    const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim()
                    const stripCountText = (value) => normalize(
                        (value || '')
                            .replace(/\\(\\s*\\d[\\d,]*\\s*\\)/g, ' ')
                            .replace(/\\b\\d[\\d,]*\\b/g, ' ')
                            .replace(/[|/]+/g, ' ')
                    )
                    const containers = []
                    const containerSet = new Set()
                    for (const selector of tabContainerSelectors) {
                        document.querySelectorAll(selector).forEach((node) => {
                            if (!containerSet.has(node)) {
                                containerSet.add(node)
                                containers.push(node)
                            }
                        })
                    }

                    const genericSelectors = ['a[onclick]', 'button[onclick]', 'li[onclick]', 'a', 'button']
                    const candidates = []
                    const seen = new Set()

                    for (const container of containers) {
                        const nodes = []
                        const nodeSet = new Set()
                        for (const selector of tabLinkSelectors) {
                            try {
                                container.querySelectorAll(selector).forEach((node) => {
                                    if (!nodeSet.has(node)) {
                                        nodeSet.add(node)
                                        nodes.push(node)
                                    }
                                })
                            } catch (error) {
                                // ignore selector failures
                            }
                        }

                        if (!nodes.length) {
                            for (const selector of genericSelectors) {
                                try {
                                    container.querySelectorAll(selector).forEach((node) => {
                                        if (!nodeSet.has(node)) {
                                            nodeSet.add(node)
                                            nodes.push(node)
                                        }
                                    })
                                } catch (error) {
                                    // ignore selector failures
                                }
                            }
                        }

                        for (const node of nodes) {
                            const label = stripCountText(node.textContent || node.innerText || '')
                            const onclick = node.getAttribute('onclick') || ''
                            const href = node.getAttribute('href') || ''
                            const key = `${label}::${onclick}::${href}`
                            if (!label || seen.has(key)) {
                                continue
                            }
                            seen.add(key)
                            candidates.push({ node, label, onclick, href, element_index: candidates.length })
                        }
                    }

                    const candidate =
                        candidates.find((item) =>
                            item.label === target.label &&
                            item.onclick === target.onclick &&
                            item.href === target.href
                        ) ||
                        candidates.find((item) => item.label === target.label && item.element_index === target.element_index) ||
                        candidates.find((item) => item.label === target.label)

                    if (!candidate) {
                        return false
                    }

                    if (typeof candidate.node.click === 'function') {
                        candidate.node.click()
                    } else {
                        candidate.node.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))
                    }
                    return true
                }
                """,
                {
                    "target": target,
                    "tabContainerSelectors": tab_container_selectors,
                    "tabLinkSelectors": tab_link_selectors,
                },
            )
        except Exception:
            logger.debug("Main collection sub-board click failed via DOM lookup", exc_info=True)

        if not clicked:
            raw_action = sub_board.get("onclick") or sub_board.get("href") or ""
            if raw_action.lower().startswith("javascript:"):
                raw_action = raw_action[len("javascript:") :]
            raw_action = raw_action.strip().rstrip(";")
            if raw_action:
                try:
                    await page.evaluate(raw_action)
                    clicked = True
                except Exception:
                    logger.debug("Main collection sub-board click failed via JS action", exc_info=True)

        if not clicked:
            return False

        await self._wait_for_collection_results(page)
        return True

    def _clean_text(self, value: str) -> str:
        without_tags = re.sub(r"<[^>]+>", " ", value or "")
        normalized = without_tags.replace("\xa0", " ")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()


crawler_service = CrawlerService()

