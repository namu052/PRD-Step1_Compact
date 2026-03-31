import pytest

from app.models.schemas import CrawlResult
from app.services.verification.content_verifier import content_verifier
from tests.mocks.mock_drafts import (
    MOCK_CRAWL_RESULTS,
    MOCK_DRAFT_ALL_WRONG,
    MOCK_DRAFT_NORMAL,
    MOCK_DRAFT_WITH_HALLUCINATION,
)


def _to_crawl_results(data_list):
    return [
        CrawlResult(**{**item, "preview": f"{item['content'][:100]}...", "relevance_score": 0.9})
        for item in data_list
    ]


@pytest.mark.asyncio
async def test_content_supported():
    results = await content_verifier.verify(MOCK_DRAFT_NORMAL, _to_crawl_results(MOCK_CRAWL_RESULTS))
    assert len([item for item in results if item.verification_status == "supported"]) >= 2


@pytest.mark.asyncio
async def test_content_hallucinated():
    results = await content_verifier.verify(
        MOCK_DRAFT_WITH_HALLUCINATION, _to_crawl_results(MOCK_CRAWL_RESULTS)
    )
    assert any(item.verification_status == "hallucinated" for item in results)


@pytest.mark.asyncio
async def test_content_unsupported():
    results = await content_verifier.verify(
        MOCK_DRAFT_ALL_WRONG, _to_crawl_results(MOCK_CRAWL_RESULTS)
    )
    assert any(item.verification_status in {"unsupported", "hallucinated"} for item in results)


@pytest.mark.asyncio
async def test_content_partial():
    draft_partial = "주택 관련 혜택이 있습니다. [출처: mock_law_001]"
    results = await content_verifier.verify(draft_partial, _to_crawl_results(MOCK_CRAWL_RESULTS))
    assert any(item.verification_status == "partial" for item in results)


@pytest.mark.asyncio
async def test_content_hallucinated_by_contradiction_pair():
    draft = "서민주택은 전액 면제됩니다. [출처: mock_law_001]"
    results = await content_verifier.verify(draft, _to_crawl_results(MOCK_CRAWL_RESULTS))
    assert any(item.verification_status == "hallucinated" for item in results)


@pytest.mark.asyncio
async def test_content_assertive_claim_without_citation_is_unsupported():
    draft = "지방세특례제한법 제36조에 따라 취득세 50%를 경감합니다."
    results = await content_verifier.verify(draft, _to_crawl_results(MOCK_CRAWL_RESULTS))
    assert any(
        item.verification_status == "unsupported" and "출처" in item.detail
        for item in results
    )
