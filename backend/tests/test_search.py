import pytest

from app.config import get_settings
from app.models.schemas import CrawlResult
from app.services.embedding_service import embedding_service
from app.services.search_service import search_service


@pytest.mark.asyncio
async def test_extract_keywords_취득세():
    keywords = await search_service.extract_keywords("취득세 감면 대상이 어떻게 되나요?")
    assert "취득세 감면" in keywords


@pytest.mark.asyncio
async def test_extract_keywords_재산세():
    keywords = await search_service.extract_keywords("재산세 납부 기한은 언제인가요?")
    assert "재산세 납부" in keywords


@pytest.mark.asyncio
async def test_extract_keywords_unknown():
    keywords = await search_service.extract_keywords("잘 모르겠는 질문입니다")
    assert len(keywords) >= 1


@pytest.mark.asyncio
async def test_build_search_plan_specific_year():
    plan = await search_service.build_search_plan("2021년 취득세 감면 판례를 알려줘")
    assert plan.detected_year == 2021
    assert plan.prefer_latest is False
    assert "case_search" in plan.categories
    assert "2021년과 가까운 자료" in plan.weighting_label


@pytest.mark.asyncio
async def test_build_search_plan_without_year_prefers_latest():
    plan = await search_service.build_search_plan("취득세 감면 최신 해석을 알려줘")
    assert plan.detected_year is None
    assert plan.prefer_latest is True
    assert "최신 자료" in plan.weighting_label


@pytest.mark.asyncio
async def test_rank_results_prefers_specific_year():
    settings = get_settings()
    original_use_mock_crawler = settings.use_mock_crawler
    settings.use_mock_crawler = False
    try:
        results = [
            CrawlResult(
                id="old",
                title="2019년 취득세 감면 해석",
                type="법제처 유권해석",
                content="2019년 취득세 감면 기준",
                preview="2019년 자료",
                url="https://example.com/old",
                relevance_score=0.8,
                document_year=2019,
            ),
            CrawlResult(
                id="target",
                title="2021년 취득세 감면 해석",
                type="법제처 유권해석",
                content="2021년 취득세 감면 기준",
                preview="2021년 자료",
                url="https://example.com/target",
                relevance_score=0.8,
                document_year=2021,
            ),
        ]

        ranked = await embedding_service.rank_results(
            "2021년 취득세 감면",
            results,
            top_k=2,
            preferred_year=2021,
            prefer_latest=False,
        )
        assert ranked[0].id == "target"
    finally:
        settings.use_mock_crawler = original_use_mock_crawler
