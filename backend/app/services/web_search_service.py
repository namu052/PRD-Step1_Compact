import logging
from typing import Union

from app.config import get_settings
from app.models.schemas import WebSearchResult

logger = logging.getLogger(__name__)


class WebSearchService:
    async def search(
        self,
        queries: Union[str, list[str]],
        max_results: int | None = None,
    ) -> list[WebSearchResult]:
        settings = get_settings()

        if isinstance(queries, str):
            queries = [queries]

        limit = max_results or settings.web_search_max_results
        all_results: list[WebSearchResult] = []
        seen_urls: set[str] = set()

        for query in queries:
            try:
                results = await self._search_single(query, limit)
                for r in results:
                    if r.url not in seen_urls:
                        seen_urls.add(r.url)
                        all_results.append(r)
            except Exception:
                logger.warning("DuckDuckGo 검색 실패: query=%s", query, exc_info=True)

        return all_results

    async def _search_single(
        self, query: str, max_results: int
    ) -> list[WebSearchResult]:
        from duckduckgo_search import AsyncDDGS

        async with AsyncDDGS() as ddgs:
            raw_results = await ddgs.atext(
                query,
                region="kr-ko",
                max_results=max_results,
            )

        results = []
        for item in raw_results:
            results.append(
                WebSearchResult(
                    title=item.get("title", ""),
                    url=item.get("href", ""),
                    content=item.get("body", ""),
                    score=0.0,
                )
            )
        return results


web_search_service = WebSearchService()
