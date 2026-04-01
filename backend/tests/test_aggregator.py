from app.models.verification import ContentClaim, SourceVerification
from app.services.verification.verification_aggregator import verification_aggregator


def test_aggregator_high_confidence():
    result = verification_aggregator.aggregate(
        [SourceVerification(source_id="test_law_001", status="verified")],
        [ContentClaim(claim_text="정상 주장", cited_sources=["test_law_001"], verification_status="supported", confidence=0.85)],
    )
    assert result.overall_confidence >= 0.7
    assert result.confidence_label in ("높음", "매우 높음")
    assert not result.removed_claims


def test_aggregator_with_hallucination():
    result = verification_aggregator.aggregate(
        [SourceVerification(source_id="src_999", status="not_found")],
        [ContentClaim(claim_text="허위 주장", cited_sources=["src_999"], verification_status="hallucinated", confidence=0.0)],
    )
    assert result.overall_confidence < 0.4
    assert "허위 주장" in result.removed_claims


def test_aggregator_partial_claim():
    result = verification_aggregator.aggregate(
        [SourceVerification(source_id="test_law_001", status="verified")],
        [
            ContentClaim(
                claim_text="부분 주장",
                cited_sources=["test_law_001"],
                verification_status="partial",
                confidence=0.5,
                corrected_text="부분 주장 ⚠️ *일부 내용 확인 필요*",
            )
        ],
    )
    assert result.confidence_label == "보통"
    assert len(result.modified_claims) == 1


def test_aggregator_very_high_confidence():
    result = verification_aggregator.aggregate(
        [SourceVerification(source_id="test_law_001", status="verified")],
        [
            ContentClaim(
                claim_text="제36조에 따라 취득세 50% 감면",
                cited_sources=["test_law_001"],
                verification_status="supported",
                confidence=0.9,
            )
        ],
    )
    assert result.confidence_label == "매우 높음"


def test_aggregator_caps_confidence_when_source_fails():
    result = verification_aggregator.aggregate(
        [SourceVerification(source_id="src_999", status="not_found")],
        [
            ContentClaim(
                claim_text="제36조에 따라 취득세 50% 감면",
                cited_sources=["src_999"],
                verification_status="supported",
                confidence=0.9,
            )
        ],
    )
    assert result.overall_confidence <= 0.4
    assert result.critical_issues


def test_aggregator_tracks_component_scores():
    result = verification_aggregator.aggregate(
        [SourceVerification(source_id="test_law_001", status="verified")],
        [
            ContentClaim(
                claim_text="제36조에 따라 취득세 50% 감면",
                cited_sources=["test_law_001"],
                verification_status="supported",
                confidence=0.9,
            )
        ],
    )
    assert result.claim_confidence > 0
    assert result.source_confidence > 0


def test_aggregator_tracks_citation_health_metrics():
    result = verification_aggregator.aggregate(
        [
            SourceVerification(source_id="test_law_001", status="verified"),
            SourceVerification(source_id="src_999", status="not_found"),
        ],
        [
            ContentClaim(
                claim_text="제36조에 따라 취득세 50% 감면",
                cited_sources=["test_law_001"],
                verification_status="supported",
                confidence=0.9,
            ),
            ContentClaim(
                claim_text="모든 1주택자는 전액 면제",
                cited_sources=[],
                verification_status="unsupported",
                confidence=0.1,
            ),
            ContentClaim(
                claim_text="지방세법 제999조에 따라 전액 면제",
                cited_sources=["src_999"],
                verification_status="unsupported",
                confidence=0.2,
            ),
        ],
    )
    assert result.citation_coverage < 1.0
    assert result.verified_citation_ratio < 1.0
    assert result.supported_claim_ratio < 0.5
    assert result.critical_issues
