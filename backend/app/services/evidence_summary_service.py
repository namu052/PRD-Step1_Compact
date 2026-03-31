from app.config import get_settings
from app.models.evidence import EvidenceGroup, EvidenceSlot
from app.models.schemas import CrawlResult
from app.prompts.evidence_summary_prompt import EVIDENCE_SUMMARY_PROMPT
from app.services.openai_service import openai_service


SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "issue": {"type": "string"},
        "conclusion": {"type": "string"},
        "applicability": {"type": "string"},
        "exceptions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "conflicts": {
            "type": "array",
            "items": {"type": "string"},
        },
        "fact_distinctions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "practice_notes": {
            "type": "array",
            "items": {"type": "string"},
        },
        "summary": {"type": "string"},
        "key_points": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "title",
        "issue",
        "conclusion",
        "applicability",
        "exceptions",
        "conflicts",
        "fact_distinctions",
        "practice_notes",
        "summary",
        "key_points",
    ],
    "additionalProperties": False,
}


class EvidenceSummaryService:
    async def summarize(
        self,
        question: str,
        groups: list[EvidenceGroup],
        crawl_results: list[CrawlResult],
    ) -> list[EvidenceSlot]:
        crawl_map = {result.id: result for result in crawl_results}
        slots = []
        for group in groups:
            group_sources = [crawl_map[source_id] for source_id in group.source_ids if source_id in crawl_map]
            if not group_sources:
                continue
            slots.append(await self._summarize_group(question, group, group_sources))
        return slots

    async def _summarize_group(
        self,
        question: str,
        group: EvidenceGroup,
        group_sources: list[CrawlResult],
    ) -> EvidenceSlot:
        settings = get_settings()
        representative_sources = self._pick_representative_sources(group, group_sources)
        try:
            group_documents = openai_service.format_crawl_results(
                group_sources,
                content_limit=settings.summary_content_limit,
            )
            payload, _ = await openai_service.create_json(
                model=settings.openai_summarization_model,
                system_prompt="너는 지방세 근거 문서를 묶어 요약하는 전문가이다. 반드시 JSON schema만 출력하라.",
                user_prompt=EVIDENCE_SUMMARY_PROMPT.format(
                    question=question,
                    group_documents=group_documents,
                ),
                schema_name="evidence_group_summary",
                schema=SUMMARY_SCHEMA,
                temperature=0.1,
                max_tokens=settings.summary_max_tokens,
            )
        except Exception:
            return self._fallback_summary(group, group_sources)
        return EvidenceSlot(
            slot_id=f"slot_{group.group_id}",
            group_id=group.group_id,
            title=payload["title"],
            summary=payload["summary"],
            issue=payload["issue"],
            conclusion=payload["conclusion"],
            applicability=payload["applicability"],
            exceptions=payload["exceptions"][:4],
            conflicts=payload["conflicts"][:4],
            fact_distinctions=payload["fact_distinctions"][:4],
            practice_notes=payload["practice_notes"][:4],
            key_points=payload["key_points"][:6],
            representative_source_ids=[item.id for item in representative_sources],
            representative_links=[item.url for item in representative_sources],
            source_type_summary=group.source_types[:4],
            confidence=round(
                sum(item.relevance_score for item in representative_sources)
                / max(len(representative_sources), 1),
                2,
            ),
        )

    def _fallback_summary(self, group: EvidenceGroup, group_sources: list[CrawlResult]) -> EvidenceSlot:
        representative_sources = self._pick_representative_sources(group, group_sources)
        summary = " / ".join(source.preview for source in representative_sources if source.preview)[:260]
        key_points = [source.title for source in representative_sources[:4]]
        return EvidenceSlot(
            slot_id=f"slot_{group.group_id}",
            group_id=group.group_id,
            title=f"{group.theme} 근거 묶음",
            summary=summary or group.theme,
            issue=group.theme,
            conclusion=representative_sources[0].preview if representative_sources else group.theme,
            applicability=group.rationale,
            exceptions=group.review_notes[:2],
            conflicts=[],
            fact_distinctions=[],
            practice_notes=["세부 사실관계와 적용 요건은 대표 원문을 다시 확인해야 합니다."],
            key_points=key_points,
            representative_source_ids=[item.id for item in representative_sources],
            representative_links=[item.url for item in representative_sources],
            source_type_summary=group.source_types[:4],
            confidence=round(sum(item.relevance_score for item in representative_sources) / max(len(representative_sources), 1), 2),
        )

    def _pick_representative_sources(
        self,
        group: EvidenceGroup,
        group_sources: list[CrawlResult],
    ) -> list[CrawlResult]:
        preferred_ids = set(group.representative_source_ids)
        chosen = [source for source in group_sources if source.id in preferred_ids]
        seen_types = {source.type for source in chosen}

        for source in group_sources:
            if len(chosen) >= 4:
                break
            if source.id in preferred_ids:
                continue
            if source.type not in seen_types:
                chosen.append(source)
                seen_types.add(source.type)

        for source in group_sources:
            if len(chosen) >= 4:
                break
            if source.id not in {item.id for item in chosen}:
                chosen.append(source)

        settings = get_settings()
        return chosen[: settings.max_representative_sources]


evidence_summary_service = EvidenceSummaryService()
