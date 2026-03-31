import pytest

from app.models.schemas import CrawlResult
from app.services.embedding_service import embedding_service
from app.services.openai_service import openai_service
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
async def test_extract_keywords_expanded_terms():
    keywords = await search_service.extract_keywords("지방소득세 가산세 경정청구가 가능한가요?")
    joined = " ".join(keywords)
    assert "지방소득세" in joined or "가산세" in joined or "경정청구" in joined


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


@pytest.mark.asyncio
async def test_rank_results_embedding_mode(monkeypatch):
    async def fake_create_embeddings(texts, model):
        del model
        assert len(texts) == 3
        return [
            [1.0, 0.0],
            [0.95, 0.05],
            [0.1, 0.9],
        ]

    monkeypatch.setattr(openai_service, "create_embeddings", fake_create_embeddings)
    results = [
        CrawlResult(
            id="best",
            title="취득세 감면 해석",
            type="법제처 유권해석",
            content="취득세 감면 기준",
            preview="취득세 감면",
            url="https://example.com/best",
            relevance_score=0.7,
            document_year=2024,
        ),
        CrawlResult(
            id="other",
            title="재산세 납부 해석",
            type="법제처 유권해석",
            content="재산세 납부 기준",
            preview="재산세 납부",
            url="https://example.com/other",
            relevance_score=0.9,
            document_year=2024,
        ),
    ]

    ranked = await embedding_service.rank_results("취득세 감면", results, top_k=2)
    assert ranked[0].id == "best"
