import logging
import re
from dataclasses import dataclass, field

from app.config import get_settings
from app.models.schemas import VerificationHistory
from app.models.verification import VerificationResult
from app.prompts.gap_analysis_prompt import (
    GAP_ANALYSIS_SCHEMA,
    GAP_ANALYSIS_SYSTEM_PROMPT,
    GAP_ANALYSIS_USER_PROMPT,
)
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)


@dataclass
class GapAnalysis:
    gaps: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    should_continue: bool = False


class GapAnalyzerService:
    async def analyze(
        self,
        draft_answer: str,
        verification_result: VerificationResult,
        history: VerificationHistory,
    ) -> GapAnalysis:
        settings = get_settings()
        try:
            payload, _ = await openai_service.create_json(
                model=settings.openai_verification_model,
                system_prompt=GAP_ANALYSIS_SYSTEM_PROMPT,
                user_prompt=GAP_ANALYSIS_USER_PROMPT.format(
                    draft_answer=draft_answer,
                    overall_confidence=verification_result.overall_confidence,
                    claim_confidence=verification_result.claim_confidence,
                    source_confidence=verification_result.source_confidence,
                    critical_issues=verification_result.critical_issues,
                    removed_claims=verification_result.removed_claims,
                    modified_claims=verification_result.modified_claims,
                    warnings=verification_result.warnings,
                    verification_history=history.to_summary(),
                ),
                schema_name="gap_analysis",
                schema=GAP_ANALYSIS_SCHEMA,
                temperature=0.0,
                max_tokens=800,
            )
            return GapAnalysis(
                gaps=payload.get("gaps", []),
                search_queries=payload.get("search_queries", []),
                should_continue=payload.get("should_continue", False),
            )
        except Exception:
            logger.warning("LLM gap 분석 실패, fallback 사용", exc_info=True)
            return self._fallback_analyze(draft_answer, verification_result)

    def _fallback_analyze(
        self,
        draft_answer: str,
        verification_result: VerificationResult,
    ) -> GapAnalysis:
        gaps = []
        queries = []

        for claim in verification_result.content_claims:
            if claim.verification_status in {"unsupported", "hallucinated"}:
                gaps.append(claim.claim_text)
                keywords = re.findall(r"[가-힣]{2,}", claim.claim_text)
                if keywords:
                    queries.append(" ".join(keywords[:3]))

        if verification_result.removed_claims:
            for claim in verification_result.removed_claims[:2]:
                keywords = re.findall(r"[가-힣]{2,}", claim)
                if keywords:
                    queries.append(" ".join(keywords[:3]))

        should_continue = len(gaps) > 0 or len(queries) > 0
        return GapAnalysis(
            gaps=gaps[:5],
            search_queries=queries[:3],
            should_continue=should_continue,
        )


gap_analyzer_service = GapAnalyzerService()
