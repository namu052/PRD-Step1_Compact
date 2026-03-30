import asyncio
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

        if settings.use_mock_llm:
            return await self._mock_generate(question, crawl_results, on_token)

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

        answer, usage = await openai_service.create_text(
            model=settings.openai_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=1800,
            on_token=on_token,
        )
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
        if settings.use_mock_llm:
            cited_sources = self._extract_cited_sources(draft_answer, crawl_results)
            return DraftResponse(answer=draft_answer, cited_sources=cited_sources, token_usage={})

        system_prompt = """너는 한국 지방세 전문 AI 상담원이다.
검증 피드백을 반영해 답변 초안을 수정하라.

규칙:
1. 신뢰도가 낮은 주장, unsupported, hallucinated 주장은 삭제 또는 수정할 것
2. partial 주장은 검증 피드백을 반영해 더 보수적으로 고칠 것
3. 근거 묶음의 공통 결론, 적용 범위, 예외, 충돌, 실무상 주의사항 구조를 유지할 것
4. 활용되지 않은 근거 묶음이 있으면 그 의미를 답변에 반영하거나, 정말 불필요한 경우만 제외할 것
5. 제공된 검색 결과와 근거 묶음에 없는 사실은 추가하지 말 것
6. 각 사실 문장에는 반드시 [출처: source_id] 태그를 남길 것
7. 법령 조문, 요건, 금액, 비율은 원문 근거가 있는 경우에만 명시할 것
8. Markdown 형식으로 작성할 것
9. 마지막에 '📌 참고 출처' 섹션을 유지할 것"""

        feedback_prompt = f"""질문: {question}

현재 초안:
{draft_answer}

검증 피드백:
{self._format_verification_feedback(verification_result)}

검색 결과:
{openai_service.format_evidence_slots(evidence_slots) if evidence_slots else openai_service.format_crawl_results(crawl_results)}

위 피드백을 반영해 답변을 더 보수적이고 정확하게 수정하라."""

        answer, usage = await openai_service.create_text(
            model=settings.openai_model,
            system_prompt=system_prompt,
            user_prompt=feedback_prompt,
            temperature=0.1,
            max_tokens=1800,
        )
        cited_sources = self._extract_cited_sources(answer, crawl_results)
        return DraftResponse(answer=answer, cited_sources=cited_sources, token_usage=usage)

    async def _mock_generate(
        self,
        question: str,
        crawl_results: list[CrawlResult],
        on_token: Optional[Callable[[str], Awaitable[None]]],
    ) -> DraftResponse:
        lines = self._build_mock_lines(question, crawl_results)
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

    def _build_mock_lines(self, question: str, crawl_results: list[CrawlResult]) -> list[str]:
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
            f"- 신뢰도 라벨: {verification_result.confidence_label}",
        ]
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
