from app.models.verification import ContentClaim, SourceVerification
from app.services.verification.verification_aggregator import verification_aggregator


def test_aggregator_high_confidence():
    result = verification_aggregator.aggregate(
        [SourceVerification(source_id="mock_law_001", status="verified")],
        [ContentClaim(claim_text="정상 주장", cited_sources=["mock_law_001"], verification_status="supported", confidence=0.85)],
    )
    assert result.overall_confidence >= 0.7
    assert result.confidence_label == "높음"
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
        [SourceVerification(source_id="mock_law_001", status="verified")],
        [
            ContentClaim(
                claim_text="부분 주장",
                cited_sources=["mock_law_001"],
                verification_status="partial",
                confidence=0.5,
                corrected_text="부분 주장 ⚠️ *일부 내용 확인 필요*",
            )
        ],
    )
    assert result.confidence_label == "보통"
    assert len(result.modified_claims) == 1
