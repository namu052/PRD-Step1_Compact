import pytest

from app.services.crawler_service import crawler_service


@pytest.mark.asyncio
async def test_mock_crawl_취득세():
    results = await crawler_service.search(None, ["취득세 감면"])
    assert len(results) >= 3
    ids = [result.id for result in results]
    assert "mock_law_001" in ids
    assert "mock_law_002" in ids
    assert "mock_interp_001" in ids


@pytest.mark.asyncio
async def test_mock_crawl_재산세():
    results = await crawler_service.search(None, ["재산세 납부"])
    assert len(results) >= 1
    assert results[0].id == "mock_law_003"


@pytest.mark.asyncio
async def test_mock_crawl_no_results():
    results = await crawler_service.search(None, ["존재하지않는세목"])
    assert len(results) == 0
