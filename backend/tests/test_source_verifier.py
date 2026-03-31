import pytest

from app.models.schemas import CrawlResult
from app.services.verification.source_verifier import source_verifier
from tests.mocks.mock_drafts import (
    MOCK_CRAWL_RESULTS,
    MOCK_DRAFT_NORMAL,
    MOCK_DRAFT_WITH_HALLUCINATION,
)


def _to_crawl_results(data_list):
    return [
        CrawlResult(**{**item, "preview": f"{item['content'][:100]}...", "relevance_score": 0.9})
        for item in data_list
    ]


@pytest.mark.asyncio
async def test_source_verified():
    results = await source_verifier.verify(MOCK_DRAFT_NORMAL, _to_crawl_results(MOCK_CRAWL_RESULTS))
    verified = [item for item in results if item.status == "verified"]
    assert len(verified) >= 2


@pytest.mark.asyncio
async def test_source_not_found():
    results = await source_verifier.verify(
        MOCK_DRAFT_WITH_HALLUCINATION, _to_crawl_results(MOCK_CRAWL_RESULTS)
    )
    not_found = [item for item in results if item.status == "not_found"]
    assert any(item.source_id == "src_999" for item in not_found)


@pytest.mark.asyncio
async def test_source_mismatch():
    draft_mismatch = "제36조에 따르면 농업법인은 감면됩니다. [출처: mock_law_002]"
    results = await source_verifier.verify(draft_mismatch, _to_crawl_results(MOCK_CRAWL_RESULTS))
    assert any(item.status == "mismatch" for item in results)


@pytest.mark.asyncio
async def test_source_mismatch_for_cited_percentage():
    draft_mismatch = "취득세 70%를 감면합니다. [출처: mock_law_001]"
    results = await source_verifier.verify(draft_mismatch, _to_crawl_results(MOCK_CRAWL_RESULTS))
    assert any(item.status == "mismatch" for item in results)


@pytest.mark.asyncio
async def test_source_verifier_handles_multi_source_tag():
    draft = (
        "서민주택과 영농조합법인 모두 취득세 50% 경감 규정이 있습니다. "
        "[출처: mock_law_001, mock_law_002]"
    )
    results = await source_verifier.verify(draft, _to_crawl_results(MOCK_CRAWL_RESULTS))
    assert {item.source_id for item in results} == {"mock_law_001", "mock_law_002"}
