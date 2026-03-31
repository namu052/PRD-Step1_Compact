import re

from app.config import get_settings
from app.models.verification import VerificationResult


class VerificationAggregator:
    def aggregate(self, source_verifications, content_claims, slot_verifications=None) -> VerificationResult:
        settings = get_settings()
        slot_verifications = slot_verifications or []
        source_map = {item.source_id: item for item in source_verifications}
        removed_claims = []
        modified_claims = []
        warnings = []
        critical_issues = []
        claim_weighted_scores = []
        claim_total_weight = 0.0
        cited_claims = 0
        verified_citation_claims = 0
        supported_claims = 0

        for claim in content_claims:
            adjusted = claim.confidence
            has_verified_citation = False
            if claim.cited_sources:
                cited_claims += 1
                statuses = [source_map[sid].status for sid in claim.cited_sources if sid in source_map]
                has_verified_citation = bool(statuses) and all(status == "verified" for status in statuses)
                if any(status == "not_found" for status in statuses):
                    adjusted *= settings.aggregator_penalty_not_found
                elif any(status == "mismatch" for status in statuses):
                    adjusted *= settings.aggregator_penalty_mismatch
                elif any(status == "expired" for status in statuses):
                    adjusted *= settings.aggregator_penalty_expired
            else:
                adjusted *= settings.aggregator_penalty_no_citation

            weight = self._claim_weight(claim.claim_text)
            claim_weighted_scores.append(adjusted * weight)
            claim_total_weight += weight
            if claim.verification_status in {"supported", "partial"}:
                supported_claims += 1
            if claim.verification_status == "supported" and has_verified_citation:
                verified_citation_claims += 1

            if claim.verification_status == "hallucinated" or (
                claim.verification_status == "unsupported" and adjusted < 0.3
            ):
                removed_claims.append(claim.claim_text)
                critical_issues.append(f"제거 필요 주장: {claim.claim_text}")

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
            elif not claim.cited_sources and adjusted < 0.3:
                warnings.append(f"⚠️ 직접 출처 없음: {claim.claim_text}")
                critical_issues.append(f"직접 출처 부족: {claim.claim_text}")

        source_scores = []
        cited_source_failures = 0
        for source in source_verifications:
            source_score = self._source_score(source.status)
            source_scores.append(source_score)
            if source.status in {"not_found", "mismatch"}:
                warnings.append(f"⚠️ 출처 검증 실패: {source.source_id}")
                critical_issues.append(f"출처 검증 실패: {source.source_id} ({source.status})")
                cited_source_failures += 1
            elif source.status == "expired":
                warnings.append(f"⚠️ 최신성 확인 필요 출처: {source.source_id}")

        slot_scores = []
        contradicted_slots = 0
        for slot in slot_verifications:
            adjusted = slot.confidence
            if slot.status == "contradicted":
                adjusted *= settings.aggregator_slot_contradicted
                warnings.append(f"⚠️ 근거 묶음 충돌: {slot.slot_id}")
                critical_issues.append(f"근거 묶음 충돌: {slot.slot_id}")
                contradicted_slots += 1
            elif slot.status == "unused":
                adjusted *= settings.aggregator_slot_unused
                warnings.append(f"⚠️ 활용되지 않은 근거 묶음: {slot.slot_id}")
            elif slot.status == "partial":
                adjusted *= settings.aggregator_slot_partial
            slot_scores.append(adjusted)

        claim_confidence = (
            sum(claim_weighted_scores) / claim_total_weight if claim_total_weight else 0.0
        )
        source_confidence = sum(source_scores) / len(source_scores) if source_scores else 0.0
        slot_confidence = sum(slot_scores) / len(slot_scores) if slot_scores else 0.0
        citation_coverage = cited_claims / len(content_claims) if content_claims else 0.0
        verified_citation_ratio = (
            verified_citation_claims / cited_claims if cited_claims else 0.0
        )
        supported_claim_ratio = supported_claims / len(content_claims) if content_claims else 0.0

        weighted_components = []
        if content_claims:
            weighted_components.append(
                (claim_confidence, settings.aggregator_claim_weight)
            )
        if source_verifications:
            weighted_components.append(
                (source_confidence, settings.aggregator_source_weight)
            )
        if slot_verifications:
            weighted_components.append(
                (slot_confidence, settings.aggregator_slot_weight)
            )

        total_component_weight = sum(weight for _, weight in weighted_components)
        base_confidence = (
            sum(score * weight for score, weight in weighted_components) / total_component_weight
            if total_component_weight
            else 0.0
        )

        overall_confidence = base_confidence
        unsupported_claims = sum(
            1 for claim in content_claims if claim.verification_status in {"unsupported", "hallucinated"}
        )
        if any(claim.verification_status == "hallucinated" for claim in content_claims):
            overall_confidence = min(overall_confidence, settings.aggregator_cap_hallucinated)
        elif content_claims and unsupported_claims >= max(1, len(content_claims) // 2):
            overall_confidence = min(overall_confidence, settings.aggregator_cap_unsupported_heavy)

        if cited_source_failures:
            overall_confidence = min(overall_confidence, settings.aggregator_cap_source_failure)

        if slot_verifications and slot_confidence < 0.35:
            overall_confidence = min(overall_confidence, settings.aggregator_cap_slot_gap)
        if content_claims and citation_coverage < 0.5:
            warnings.append("⚠️ 직접 출처가 연결된 주장 비율이 낮습니다.")
            critical_issues.append("직접 출처 커버리지 부족")
            overall_confidence = min(overall_confidence, settings.aggregator_cap_low_citation_coverage)
        if cited_claims and verified_citation_ratio < 0.6:
            warnings.append("⚠️ 검증된 출처에 직접 연결된 주장 비율이 낮습니다.")
            critical_issues.append("검증된 출처 연결 비율 부족")
            overall_confidence = min(overall_confidence, settings.aggregator_cap_low_verified_citation_ratio)
        if content_claims and supported_claim_ratio < 0.5:
            warnings.append("⚠️ 뒷받침되는 주장 비율이 낮습니다.")
            critical_issues.append("supported 주장 비율 부족")
            overall_confidence = min(overall_confidence, settings.aggregator_cap_low_supported_ratio)

        overall_confidence = max(0.0, min(1.0, overall_confidence))
        if overall_confidence >= settings.confidence_very_high:
            label = "매우 높음"
        elif overall_confidence >= settings.confidence_high:
            label = "높음"
        elif overall_confidence >= settings.confidence_medium:
            label = "보통"
        else:
            label = "낮음"

        return VerificationResult(
            source_verifications=source_verifications,
            content_claims=content_claims,
            slot_verifications=slot_verifications,
            overall_confidence=round(overall_confidence, 2),
            claim_confidence=round(claim_confidence, 2),
            source_confidence=round(source_confidence, 2),
            slot_confidence=round(slot_confidence, 2),
            citation_coverage=round(citation_coverage, 2),
            verified_citation_ratio=round(verified_citation_ratio, 2),
            supported_claim_ratio=round(supported_claim_ratio, 2),
            confidence_label=label,
            removed_claims=removed_claims,
            modified_claims=modified_claims,
            warnings=list(dict.fromkeys(warnings)),
            critical_issues=list(dict.fromkeys(critical_issues)),
        )

    def _claim_weight(self, claim_text: str) -> float:
        weight = 1.0
        if re.search(r"제\d+조", claim_text):
            weight += 0.3
        if re.search(r"\d+[억만천백]?원|\d+%|\d+분의\s*\d+", claim_text):
            weight += 0.2
        return weight

    def _source_score(self, status: str) -> float:
        scores = {
            "verified": 1.0,
            "expired": 0.45,
            "mismatch": 0.15,
            "not_found": 0.0,
        }
        return scores.get(status, 0.0)


verification_aggregator = VerificationAggregator()
