import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
from app.models.evidence import EvidenceSlot
from app.models.schemas import CrawlResult, WebSearchResult
from app.models.verification import VerificationResult
from app.prompts.grouped_answer_prompt import (
    GROUPED_ANSWER_SYSTEM_PROMPT,
    GROUPED_ANSWER_USER_PROMPT,
)
from app.prompts.revision_prompt import REVISION_SYSTEM_PROMPT, REVISION_USER_PROMPT
from app.prompts.stage1_prompt import NO_RESULTS_ANSWER
from app.prompts.stage1_prompt import STAGE1_SYSTEM_PROMPT, STAGE1_USER_PROMPT
from app.prompts.web_draft_prompt import WEB_DRAFT_SYSTEM_PROMPT, WEB_DRAFT_USER_PROMPT
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
            logger.warning("LLM 초안 생성 실패, fallback 사용", exc_info=True)
            return await self._fallback_generate(question, crawl_results, on_token)
        cited_sources = self._extract_cited_sources(answer, crawl_results)
        return DraftResponse(answer=answer, cited_sources=cited_sources, token_usage=usage)

    async def generate_web_draft(
        self,
        question: str,
        web_results: list[WebSearchResult],
        on_token: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> DraftResponse:
        settings = get_settings()

        if not web_results:
            if on_token:
                for index in range(0, len(NO_RESULTS_ANSWER), 5):
                    await on_token(NO_RESULTS_ANSWER[index : index + 5])
                    await asyncio.sleep(0.03)
            return DraftResponse(answer=NO_RESULTS_ANSWER, cited_sources=[], token_usage={})

        formatted = self._format_web_results(web_results)
        system_prompt = WEB_DRAFT_SYSTEM_PROMPT.format(web_results=formatted)
        user_prompt = WEB_DRAFT_USER_PROMPT.format(question=question)

        try:
            answer, usage = await openai_service.create_text(
                model=settings.openai_verification_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=settings.draft_temperature,
                max_tokens=settings.draft_max_tokens,
                on_token=on_token,
            )
        except Exception:
            logger.warning("LLM 웹 초안 생성 실패, fallback 사용", exc_info=True)
            return self._fallback_web_draft(question, web_results, on_token)

        cited_sources = re.findall(r"\[출처:\s*(web_\d+)\]", answer)
        return DraftResponse(
            answer=answer,
            cited_sources=list(dict.fromkeys(cited_sources)),
            token_usage=usage,
        )

    def _format_web_results(self, web_results: list[WebSearchResult]) -> str:
        blocks = []
        for idx, result in enumerate(web_results, 1):
            blocks.append(
                "\n".join([
                    f"- source_id: web_{idx:03d}",
                    f"  title: {result.title}",
                    f"  url: {result.url}",
                    f"  content: {result.content[:1400]}",
                ])
            )
        return "\n\n".join(blocks)

    def _fallback_web_draft(
        self,
        question: str,
        web_results: list[WebSearchResult],
        on_token,
    ) -> DraftResponse:
        lines = [f"## {question}", ""]
        for idx, result in enumerate(web_results, 1):
            lines.append(f"- {result.title} [출처: web_{idx:03d}]")
        lines.append("")
        lines.append("---")
        lines.append("**참고 출처**")
        for idx, result in enumerate(web_results, 1):
            lines.append(f"- web_{idx:03d}: {result.url}")

        answer = "\n".join(lines)
        return DraftResponse(
            answer=answer,
            cited_sources=[f"web_{i:03d}" for i in range(1, len(web_results) + 1)],
            token_usage={},
        )

    async def revise_draft(
        self,
        question: str,
        draft_answer: str,
        verification_result: VerificationResult | None,
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
                model=settings.openai_verification_model,
                system_prompt=REVISION_SYSTEM_PROMPT,
                user_prompt=feedback_prompt,
                temperature=settings.revision_temperature,
                max_tokens=settings.revision_max_tokens,
            )
        except Exception:
            logger.warning("LLM 초안 수정 실패, fallback 사용", exc_info=True)
            if verification_result is not None:
                answer = self._fallback_revise(draft_answer, verification_result)
            else:
                answer = draft_answer or "답변을 생성할 수 없습니다. 다시 시도해 주세요."
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
        lines = [f"## {question}", ""]
        for result in crawl_results:
            lines.append(f"{result.title} [출처: {result.id}]")

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

    def _format_verification_feedback(self, verification_result: VerificationResult | None) -> str:
        if verification_result is None:
            return "초안 없음 - OLTA 자료를 기반으로 처음부터 답변을 작성해 주세요."

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
