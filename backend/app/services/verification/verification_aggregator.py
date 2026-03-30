from app.models.verification import VerificationResult


class VerificationAggregator:
    def aggregate(self, source_verifications, content_claims, slot_verifications=None) -> VerificationResult:
        slot_verifications = slot_verifications or []
        source_map = {item.source_id: item for item in source_verifications}
        removed_claims = []
        modified_claims = []
        warnings = []
        adjusted_scores = []

        for claim in content_claims:
            adjusted = claim.confidence
            if claim.cited_sources:
                statuses = [source_map[sid].status for sid in claim.cited_sources if sid in source_map]
                if any(status == "not_found" for status in statuses):
                    adjusted *= 0.3
                elif any(status == "mismatch" for status in statuses):
                    adjusted *= 0.5
                elif any(status == "expired" for status in statuses):
                    adjusted *= 0.4
            else:
                adjusted *= 0.2

            adjusted_scores.append(adjusted)

            if claim.verification_status == "hallucinated" or (
                claim.verification_status == "unsupported" and adjusted < 0.3
            ):
                removed_claims.append(claim.claim_text)

            if claim.verification_status == "partial" and claim.corrected_text:
                modified_claims.append(
                    {
                        "original": claim.claim_text,
                        "corrected": claim.corrected_text,
                        "reason": claim.detail,
                    }
                )

            if claim.verification_status == "unsupported" and adjusted >= 0.3:
                warnings.append(f"⚠️ 확인 필요: {claim.claim_text}")

        for slot in slot_verifications:
            adjusted = slot.confidence
            if slot.status == "contradicted":
                adjusted *= 0.2
                warnings.append(f"⚠️ 근거 묶음 충돌: {slot.slot_id}")
            elif slot.status == "unused":
                adjusted *= 0.5
                warnings.append(f"⚠️ 활용되지 않은 근거 묶음: {slot.slot_id}")
            elif slot.status == "partial":
                adjusted *= 0.8
            adjusted_scores.append(adjusted)

        overall_confidence = sum(adjusted_scores) / len(adjusted_scores) if adjusted_scores else 0.0
        if overall_confidence >= 0.7:
            label = "높음"
        elif overall_confidence >= 0.4:
            label = "보통"
        else:
            label = "낮음"

        return VerificationResult(
            source_verifications=source_verifications,
            content_claims=content_claims,
            slot_verifications=slot_verifications,
            overall_confidence=round(overall_confidence, 2),
            confidence_label=label,
            removed_claims=removed_claims,
            modified_claims=modified_claims,
            warnings=warnings,
        )


verification_aggregator = VerificationAggregator()
