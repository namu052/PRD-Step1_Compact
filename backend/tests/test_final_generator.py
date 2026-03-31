import pytest

from app.models.evidence import EvidenceSlot
from app.models.schemas import CrawlResult
from app.services.verification.final_generator import final_generator
from app.services.verification.verification_aggregator import verification_aggregator
from app.services.verification.content_verifier import content_verifier
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


def _to_evidence_slots(crawl_results):
    return [
        EvidenceSlot(
            slot_id="slot_group_001",
            group_id="group_001",
            title="취득세 감면 근거 묶음",
            issue="취득세 감면 적용 여부",
            conclusion="질문과 직접 관련된 취득세 감면 결론을 묶음 기준으로 정리한다.",
            applicability="주택 취득 및 영농조합법인 관련 사실관계에서 적용 가능성을 검토한다.",
            exceptions=["세부 요건을 충족하지 않으면 감면이 제한될 수 있다."],
            conflicts=["사실관계에 따라 해석이 달라질 수 있다."],
            fact_distinctions=["취득 목적과 사용 형태에 따라 결론이 달라질 수 있다."],
            practice_notes=["대표 원문과 사실관계를 함께 확인해야 한다."],
            summary="취득세 감면 관련 주요 근거를 묶은 슬롯이다.",
            key_points=[result.title for result in crawl_results[:3]],
            representative_source_ids=[result.id for result in crawl_results[:3]],
            representative_links=[result.url for result in crawl_results[:3]],
            source_type_summary=sorted({result.type for result in crawl_results[:3]}),
            confidence=0.9,
        )
    ]


@pytest.mark.asyncio
async def test_final_generator_normal():
    crawl_results = _to_crawl_results(MOCK_CRAWL_RESULTS)
    evidence_slots = _to_evidence_slots(crawl_results)
    sources = await source_verifier.verify(MOCK_DRAFT_NORMAL, crawl_results)
    claims = await content_verifier.verify(MOCK_DRAFT_NORMAL, crawl_results)
    verification = verification_aggregator.aggregate(sources, claims)
    final_answer = await final_generator.generate(MOCK_DRAFT_NORMAL, verification, evidence_slots, crawl_results)
    assert "📊 **답변 신뢰도**" in final_answer.answer
    assert final_answer.confidence_label in ("높음", "매우 높음")


@pytest.mark.asyncio
async def test_final_generator_removes_hallucination():
    crawl_results = _to_crawl_results(MOCK_CRAWL_RESULTS)
    evidence_slots = _to_evidence_slots(crawl_results)
    sources = await source_verifier.verify(MOCK_DRAFT_WITH_HALLUCINATION, crawl_results)
    claims = await content_verifier.verify(MOCK_DRAFT_WITH_HALLUCINATION, crawl_results)
    verification = verification_aggregator.aggregate(sources, claims)
    final_answer = await final_generator.generate(
        MOCK_DRAFT_WITH_HALLUCINATION, verification, evidence_slots, crawl_results
    )
    assert "지방세법 제999조" not in final_answer.answer
