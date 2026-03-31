import re

from app.config import get_settings
from app.models.evidence import EvidenceSlot, SlotVerification
from app.prompts.grouped_verification_prompt import GROUPED_VERIFICATION_PROMPT
from app.services.openai_service import openai_service


GROUPED_VERIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "slot_verifications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slot_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["supported", "partial", "contradicted", "unused"],
                    },
                    "confidence": {"type": "number"},
                    "detail": {"type": "string"},
                },
                "required": ["slot_id", "status", "confidence", "detail"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["slot_verifications"],
    "additionalProperties": False,
}


class GroupedAnswerVerifier:
    async def verify(self, final_answer: str, evidence_slots: list[EvidenceSlot]) -> list[SlotVerification]:
        settings = get_settings()
        try:
            payload, _ = await openai_service.create_json(
                model=settings.openai_verification_model,
                system_prompt="너는 지방세 종합답변 묶음 검증 전문가이다. 반드시 JSON schema만 출력하라.",
                user_prompt=GROUPED_VERIFICATION_PROMPT.format(
                    final_answer=final_answer,
                    evidence_slots=openai_service.format_evidence_slots(evidence_slots),
                ),
                schema_name="grouped_answer_verification",
                schema=GROUPED_VERIFICATION_SCHEMA,
                temperature=0.0,
                max_tokens=1200,
            )
            return [
                SlotVerification(
                    slot_id=item["slot_id"],
                    status=item["status"],
                    confidence=float(item["confidence"]),
                    detail=item["detail"],
                )
                for item in payload.get("slot_verifications", [])
            ]
        except Exception:
            return self._fallback_verify(final_answer, evidence_slots)

    def _fallback_verify(self, final_answer: str, evidence_slots: list[EvidenceSlot]) -> list[SlotVerification]:
        answer_text = re.sub(r"\s+", " ", final_answer).lower()
        results = []
        for slot in evidence_slots:
            all_text = (
                f"{slot.title} {slot.summary} {slot.conclusion} "
                + " ".join(slot.key_points)
                + " "
                + " ".join(slot.exceptions)
            )
            terms = [token.lower() for token in re.split(r"[\s,/()-]+", all_text) if len(token) >= 2]
            unique_terms = list(dict.fromkeys(terms))[:30]
            overlap = sum(1 for term in unique_terms if term in answer_text)
            ratio = overlap / len(unique_terms) if unique_terms else 0.0
            if ratio >= 0.3:
                results.append(SlotVerification(slot_id=slot.slot_id, status="supported", confidence=0.85, detail="묶음 요지가 최종 답변에 반영됨"))
            elif ratio >= 0.15:
                results.append(SlotVerification(slot_id=slot.slot_id, status="partial", confidence=0.55, detail="묶음 요지가 부분 반영됨"))
            else:
                results.append(SlotVerification(slot_id=slot.slot_id, status="unused", confidence=0.2, detail="최종 답변에서 묶음 사용 흔적이 약함"))
        return results


grouped_answer_verifier = GroupedAnswerVerifier()
