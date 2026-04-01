import pytest

from app.services.crawler_service import crawler_service


@pytest.mark.asyncio
async def test_crawler_returns_results_for_matching_query():
    results = await crawler_service.search(None, ["취득세 감면"])
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_crawler_returns_empty_for_unknown_query():
    results = await crawler_service.search(None, ["존재하지않는세목xyz"])
    assert results == []
