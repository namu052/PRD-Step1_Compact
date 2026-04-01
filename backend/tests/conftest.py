from datetime import datetime

import pytest

from app.models.schemas import CrawlResult


TEST_CRAWL_RESULTS = [
    CrawlResult(
        id="test_law_001",
        title="지방세특례제한법 제36조(서민주택 등에 대한 감면)",
        type="법령",
        content="제36조(서민주택 등에 대한 감면) ① 주택으로서 대통령령으로 정하는 주택을 취득하는 경우에는 취득세의 100분의 50을 2027년 12월 31일까지 경감한다. ② 대통령령으로 정하는 주택이란 취득 당시의 가액이 1억원 이하인 주택을 말한다.",
        preview="제36조(서민주택 등에 대한 감면) ① 주택으로서 대통령령으로 정하는 주택을 취득하는 경우에는 취득세의 100분의 50을 2027년 12월 31일까지 경감한다...",
        url="https://www.olta.re.kr/law/detail?lawId=36",
        relevance_score=0.9,
        crawled_at=datetime.now(),
    ),
    CrawlResult(
        id="test_law_002",
        title="지방세특례제한법 제11조(농업법인에 대한 감면)",
        type="법령",
        content="제11조(농업법인에 대한 감면) ① 영농조합법인이 그 법인의 사업에 직접 사용하기 위하여 취득하는 부동산에 대해서는 취득세의 100분의 50을 2027년 12월 31일까지 경감한다.",
        preview="제11조(농업법인에 대한 감면) ① 영농조합법인이 그 법인의 사업에 직접 사용하기 위하여 취득하는 부동산에 대해서는...",
        url="https://www.olta.re.kr/law/detail?lawId=11",
        relevance_score=0.85,
        crawled_at=datetime.now(),
    ),
    CrawlResult(
        id="test_interp_001",
        title="해석례 2024-0312 (서민주택 감면 적용 범위)",
        type="해석례",
        content="질의: 취득가액 1억원 이하 주택의 감면 적용 시 부속토지도 포함되는지 여부. 회신: 지방세특례제한법 제36조에 따른 서민주택 감면은 주택과 그 부속토지를 포함하여 적용하는 것이 타당함.",
        preview="질의: 취득가액 1억원 이하 주택의 감면 적용 시 부속토지도 포함되는지 여부...",
        url="https://www.olta.re.kr/interpret/detail?id=2024-0312",
        relevance_score=0.8,
        crawled_at=datetime.now(),
    ),
]

KEYWORD_TO_RESULTS = {
    "취득세": TEST_CRAWL_RESULTS,
    "감면": TEST_CRAWL_RESULTS,
    "서민주택": TEST_CRAWL_RESULTS[:1],
    "농업법인": TEST_CRAWL_RESULTS[1:2],
}


@pytest.fixture(autouse=True)
def force_fallback_paths(monkeypatch):
    async def fake_search(self, session, queries, categories=None):
        results = []
        seen_ids = set()
        for query in queries:
            for keyword, items in KEYWORD_TO_RESULTS.items():
                if keyword in query or query in keyword:
                    for item in items:
                        if item.id not in seen_ids:
                            seen_ids.add(item.id)
                            results.append(item)
        return results

    async def fail_create_text(*args, **kwargs):
        raise RuntimeError("test fallback text")

    async def fail_create_json(*args, **kwargs):
        raise RuntimeError("test fallback json")

    async def fail_create_embeddings(*args, **kwargs):
        raise RuntimeError("test fallback embeddings")

    async def fake_web_search(self, queries, max_results=None):
        from app.models.schemas import WebSearchResult

        results = []
        query_str = " ".join(queries) if isinstance(queries, list) else queries
        if any(kw in query_str for kw in ["취득세", "감면", "서민주택"]):
            results.append(
                WebSearchResult(
                    title="지방세특례제한법 제36조 서민주택 감면 안내",
                    url="https://example.com/tax/36",
                    content="서민주택 취득세 50% 감면 관련 안내입니다. 취득 당시 가액 1억원 이하 주택에 적용됩니다.",
                    score=0.9,
                )
            )
            results.append(
                WebSearchResult(
                    title="농업법인 취득세 감면 안내",
                    url="https://example.com/tax/11",
                    content="영농조합법인이 사업용 부동산 취득 시 취득세 50% 감면 대상입니다.",
                    score=0.85,
                )
            )
        return results

    from app.services.crawler_service import CrawlerService
    from app.services.openai_service import openai_service
    from app.services.web_search_service import WebSearchService

    monkeypatch.setattr(CrawlerService, "search", fake_search)
    monkeypatch.setattr(WebSearchService, "search", fake_web_search)
    monkeypatch.setattr(openai_service, "create_text", fail_create_text)
    monkeypatch.setattr(openai_service, "create_json", fail_create_json)
    monkeypatch.setattr(openai_service, "create_embeddings", fail_create_embeddings)


@pytest.fixture
def mock_session_id():
    import asyncio

    from app.core.session_manager import session_manager

    session = asyncio.get_event_loop().run_until_complete(
        session_manager.create_session("cert_001", "test1234")
    )
    return session.session_id
