import asyncio
import re
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from app.config import get_settings
from app.models.evidence import EvidenceSlot
from app.models.schemas import CrawlResult
from app.models.verification import VerificationResult
from app.prompts.grouped_answer_prompt import (
    GROUPED_ANSWER_SYSTEM_PROMPT,
    GROUPED_ANSWER_USER_PROMPT,
)
from app.prompts.revision_prompt import REVISION_SYSTEM_PROMPT, REVISION_USER_PROMPT
from app.prompts.stage1_prompt import NO_RESULTS_ANSWER
from app.prompts.stage1_prompt import STAGE1_SYSTEM_PROMPT, STAGE1_USER_PROMPT
from app.services.openai_service import openai_service


@dataclass
class DraftResponse:
    answer: str
    cited_sources: list[str]
    token_usage: dict


class LLMService:
    async def generate_draft(
        self,
        question: str,
        crawl_results: list[CrawlResult],
        evidence_slots: list[EvidenceSlot] | None = None,
        on_token: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> DraftResponse:
        settings = get_settings()

        if not crawl_results:
            if on_token:
                for index in range(0, len(NO_RESULTS_ANSWER), 5):
                    await on_token(NO_RESULTS_ANSWER[index : index + 5])
                    await asyncio.sleep(0.03)
            return DraftResponse(answer=NO_RESULTS_ANSWER, cited_sources=[], token_usage={})

        if evidence_slots:
            system_prompt = GROUPED_ANSWER_SYSTEM_PROMPT
            user_prompt = GROUPED_ANSWER_USER_PROMPT.format(
                question=question,
                evidence_slots=openai_service.format_evidence_slots(evidence_slots),
            )
        else:
            system_prompt = STAGE1_SYSTEM_PROMPT.format(
                crawl_results=openai_service.format_crawl_results(crawl_results)
            )
            user_prompt = STAGE1_USER_PROMPT.format(question=question)

        try:
            answer, usage = await openai_service.create_text(
                model=settings.openai_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=settings.draft_temperature,
                max_tokens=settings.draft_max_tokens,
                on_token=on_token,
            )
        except Exception:
            return await self._fallback_generate(question, crawl_results, on_token)
        cited_sources = self._extract_cited_sources(answer, crawl_results)
        return DraftResponse(answer=answer, cited_sources=cited_sources, token_usage=usage)

    async def revise_draft(
        self,
        question: str,
        draft_answer: str,
        verification_result: VerificationResult,
        crawl_results: list[CrawlResult],
        evidence_slots: list[EvidenceSlot] | None = None,
    ) -> DraftResponse:
        settings = get_settings()

        feedback_prompt = REVISION_USER_PROMPT.format(
            question=question,
            draft_answer=draft_answer,
            verification_feedback=self._format_verification_feedback(verification_result),
            evidence_context=(
                openai_service.format_evidence_slots(evidence_slots)
                if evidence_slots
                else openai_service.format_crawl_results(crawl_results)
            ),
        )

        try:
            answer, usage = await openai_service.create_text(
                model=settings.openai_model,
                system_prompt=REVISION_SYSTEM_PROMPT,
                user_prompt=feedback_prompt,
                temperature=settings.revision_temperature,
                max_tokens=settings.revision_max_tokens,
            )
        except Exception:
            answer = self._fallback_revise(draft_answer, verification_result)
            usage = {}
        cited_sources = self._extract_cited_sources(answer, crawl_results)
        return DraftResponse(answer=answer, cited_sources=cited_sources, token_usage=usage)

    def _fallback_revise(
        self,
        draft_answer: str,
        verification_result: VerificationResult,
    ) -> str:
        modified_map = {item["original"]: item for item in verification_result.modified_claims}
        revised_lines = []
        changed = False

        for line in draft_answer.splitlines():
            stripped = line.strip()
            plain = re.sub(r"\[출처:\s*[^\]]+\]", "", stripped)
            plain = re.sub(r"\*+", "", plain).strip()

            if plain and plain in verification_result.removed_claims:
                changed = True
                continue

            if plain and plain in modified_map:
                revised_lines.append(modified_map[plain]["corrected"])
                changed = True
                continue

            revised_lines.append(line)

        revised_text = "\n".join(revised_lines).strip()
        if changed:
            return revised_text

        fallback_lines = draft_answer.splitlines()
        for index, line in enumerate(fallback_lines):
            stripped = line.strip()
            if (
                stripped
                and not stripped.startswith("#")
                and not stripped.startswith("---")
                and not stripped.startswith("📌")
            ):
                fallback_lines[index] = f"{line} ⚠️ *검증 결과 추가 확인 필요*"
                break
        return "\n".join(fallback_lines).strip()

    async def _fallback_generate(
        self,
        question: str,
        crawl_results: list[CrawlResult],
        on_token: Optional[Callable[[str], Awaitable[None]]],
    ) -> DraftResponse:
        lines = self._build_fallback_lines(question, crawl_results)
        cited = [result.id for result in crawl_results]

        answer = "\n".join(lines)

        if on_token:
            for index in range(0, len(answer), 5):
                await on_token(answer[index : index + 5])
                await asyncio.sleep(0.03)

        return DraftResponse(
            answer=answer,
            cited_sources=cited,
            token_usage={"prompt_tokens": 0, "completion_tokens": len(answer)},
        )

    def _build_fallback_lines(self, question: str, crawl_results: list[CrawlResult]) -> list[str]:
        templates = {
            "mock_law_001": [
                "**지방세특례제한법 제36조**에 따르면 서민주택 취득 시 취득세 50%를 경감합니다. [출처: mock_law_001]",
                "취득가액 1억원 이하의 주택이 감면 대상입니다. [출처: mock_law_001]",
            ],
            "mock_law_002": [
                "영농조합법인이 농업에 직접 사용하기 위하여 취득하는 부동산도 감면 대상입니다. [출처: mock_law_002]",
            ],
            "mock_interp_001": [
                "서민주택 감면은 주택과 그 부속토지를 포함하여 적용하는 것이 타당합니다. [출처: mock_interp_001]",
            ],
            "mock_law_003": [
                "**지방세법 제115조**에 따르면 재산세 납기는 토지는 9월 16일부터 9월 30일까지입니다. [출처: mock_law_003]",
                "건축물은 7월 16일부터 7월 31일까지, 주택은 7월과 9월로 나누어 납부합니다. [출처: mock_law_003]",
            ],
        }

        lines = [f"## {question}", ""]
        used = []
        for result in crawl_results:
            used.extend(templates.get(result.id, [f"{result.title} [출처: {result.id}]"]))

        lines.extend(used)
        lines.append("")
        lines.append("---")
        lines.append("📌 **참고 출처**")
        for result in crawl_results:
            lines.append(f"- {result.title} ({result.type})")

        return lines

    def _extract_cited_sources(self, answer: str, crawl_results: list[CrawlResult]) -> list[str]:
        cited = []
        for result in crawl_results:
            if f"[출처: {result.id}]" in answer or f"[출처:{result.id}]" in answer:
                cited.append(result.id)
        return cited

    def _format_verification_feedback(self, verification_result: VerificationResult) -> str:
        lines = [
            f"- 전체 신뢰도: {verification_result.overall_confidence}",
            f"- 주장 신뢰도: {verification_result.claim_confidence}",
            f"- 출처 신뢰도: {verification_result.source_confidence}",
            f"- 근거 묶음 반영도: {verification_result.slot_confidence}",
            f"- 직접 출처 커버리지: {verification_result.citation_coverage}",
            f"- 검증된 출처 연결 비율: {verification_result.verified_citation_ratio}",
            f"- supported 주장 비율: {verification_result.supported_claim_ratio}",
            f"- 신뢰도 라벨: {verification_result.confidence_label}",
        ]
        if verification_result.critical_issues:
            lines.append(f"- 치명 이슈: {verification_result.critical_issues}")
        if verification_result.removed_claims:
            lines.append(f"- 제거 필요 주장: {verification_result.removed_claims}")
        if verification_result.modified_claims:
            lines.append(f"- 수정 필요 주장: {verification_result.modified_claims}")
        if verification_result.warnings:
            lines.append(f"- 경고: {verification_result.warnings}")
        for claim in verification_result.content_claims:
            lines.append(
                f"- claim={claim.claim_text} | status={claim.verification_status} | confidence={claim.confidence} | detail={claim.detail}"
            )
        for source in verification_result.source_verifications:
            lines.append(
                f"- source={source.source_id} | status={source.status} | detail={source.detail}"
            )
        for slot in verification_result.slot_verifications:
            lines.append(
                f"- slot={slot.slot_id} | status={slot.status} | confidence={slot.confidence} | detail={slot.detail}"
            )
        return "\n".join(lines)


llm_service = LLMService()
