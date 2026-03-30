import asyncio
import re
from typing import Awaitable, Callable, Optional

from app.config import get_settings
from app.models.evidence import EvidenceSlot
from app.models.schemas import CrawlResult
from app.models.verification import FinalAnswer, VerificationResult
from app.prompts.stage2_final_prompt import FINAL_ANSWER_PROMPT
from app.services.openai_service import openai_service


class FinalGenerator:
    async def generate(
        self,
        draft_answer: str,
        verification_result: VerificationResult,
        evidence_slots: list[EvidenceSlot],
        crawl_results: list[CrawlResult],
        on_token: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> FinalAnswer:
        settings = get_settings()
        streamed = False
        try:
            if settings.use_mock_llm:
                answer = self._mock_generate(draft_answer, verification_result, evidence_slots)
            else:
                answer, _ = await openai_service.create_text(
                    model=settings.openai_final_model,
                    system_prompt="너는 지방세 답변 최종 편집자이다. 반드시 Markdown 답변만 출력하라.",
                    user_prompt=FINAL_ANSWER_PROMPT.format(
                        draft_answer=draft_answer,
                        evidence_slots=openai_service.format_evidence_slots(evidence_slots),
                        verification_result=self._format_verification_result(verification_result),
                        verified_sources=self._format_verified_sources(
                            verification_result,
                            evidence_slots,
                            crawl_results,
                        ),
                        confidence_label=verification_result.confidence_label,
                        confidence_score=round(verification_result.overall_confidence * 100, 1),
                    ),
                    temperature=0.1,
                    max_tokens=1800,
                    on_token=on_token,
                )
                streamed = on_token is not None
        except Exception:
            warning_line = "\n\n⚠️ 검증 단계 편집에 실패하여 초안을 그대로 반환합니다."
            answer = draft_answer + warning_line

        if on_token and not streamed:
            for index in range(0, len(answer), 5):
                await on_token(answer[index : index + 5])
                await asyncio.sleep(0.03)

        verified_sources = self.build_verified_source_cards(
            verification_result,
            evidence_slots,
            crawl_results,
        )

        return FinalAnswer(
            answer=answer,
            confidence_score=round(verification_result.overall_confidence * 100, 1),
            confidence_label=verification_result.confidence_label,
            verified_sources=verified_sources,
            warnings=verification_result.warnings,
        )

    def _mock_generate(
        self,
        draft_answer: str,
        verification_result: VerificationResult,
        evidence_slots: list[EvidenceSlot],
    ) -> str:
        lines = []
        modified_map = {item["original"]: item for item in verification_result.modified_claims}

        for line in draft_answer.splitlines():
            stripped = line.strip()
            if stripped.startswith("📌 **참고 출처**"):
                continue
            if not stripped:
                lines.append(line)
                continue

            plain = re.sub(r"\[출처:\s*[^\]]+\]", "", stripped)
            plain = re.sub(r"\*+", "", plain).strip()

            if plain in verification_result.removed_claims:
                continue

            if plain in modified_map:
                line = modified_map[plain]["corrected"]

            if any(warning.endswith(plain) for warning in verification_result.warnings):
                line = f"{line} ⚠️ *확인 필요*"

            lines.append(line)

        lines.append("")
        lines.append("---")
        lines.append("📌 **참고 출처**")
        for slot in evidence_slots:
            rep = ", ".join(slot.representative_source_ids[:2])
            lines.append(f"- {slot.title} [{rep}]")

        lines.append("")
        lines.append("---")
        lines.append(
            f"📊 **답변 신뢰도**: {verification_result.confidence_label} ({round(verification_result.overall_confidence * 100, 1)}%)"
        )

        return "\n".join(lines).strip()

    def _format_verification_result(self, verification_result: VerificationResult) -> str:
        parts = [
            f"- overall_confidence: {verification_result.overall_confidence}",
            f"- confidence_label: {verification_result.confidence_label}",
            f"- removed_claims: {verification_result.removed_claims}",
            f"- modified_claims: {verification_result.modified_claims}",
            f"- warnings: {verification_result.warnings}",
            "- slot_verifications:",
        ]
        for item in verification_result.slot_verifications:
            parts.append(
                f"  - slot_id={item.slot_id}, status={item.status}, confidence={item.confidence}, detail={item.detail}"
            )
        return "\n".join(parts)

    def _format_verified_sources(
        self,
        verification_result: VerificationResult,
        evidence_slots: list[EvidenceSlot],
        crawl_results: list[CrawlResult],
    ) -> str:
        slot_map = {slot.slot_id: slot for slot in evidence_slots}
        result_map = {result.id: result for result in crawl_results}
        lines = []

        for slot_verification in verification_result.slot_verifications:
            if slot_verification.status not in {"supported", "partial"}:
                continue
            slot = slot_map.get(slot_verification.slot_id)
            if not slot:
                continue
            lines.append(
                f"- {slot.slot_id}: {slot.title} | conclusion={slot.conclusion} | applicability={slot.applicability}"
            )
            for source_id in slot.representative_source_ids[:3]:
                result = result_map.get(source_id)
                if result:
                    lines.append(f"  - source {result.id}: {result.title} ({result.type})")
        return "\n".join(lines)

    def build_verified_source_cards(
        self,
        verification_result: VerificationResult,
        evidence_slots: list[EvidenceSlot],
        crawl_results: list[CrawlResult],
    ) -> list[dict]:
        slot_map = {slot.slot_id: slot for slot in evidence_slots}
        result_map = {result.id: result for result in crawl_results}
        cards = []
        seen_ids = set()

        for slot_verification in verification_result.slot_verifications:
            if slot_verification.status not in {"supported", "partial"}:
                continue
            slot = slot_map.get(slot_verification.slot_id)
            if not slot:
                continue
            slot_result = slot.to_crawl_result().to_source_card()
            if slot_result["id"] not in seen_ids:
                cards.append(slot_result)
                seen_ids.add(slot_result["id"])
            for source_id in slot.representative_source_ids[:3]:
                result = result_map.get(source_id)
                if result and result.id not in seen_ids:
                    cards.append(result.to_source_card())
                    seen_ids.add(result.id)

        if cards:
            return cards

        return [
            result.to_source_card()
            for result in crawl_results
            if any(
                source.status == "verified" and source.source_id == result.id
                for source in verification_result.source_verifications
            )
        ]


final_generator = FinalGenerator()
