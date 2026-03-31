from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.models.evidence import SlotVerification


@dataclass
class SourceVerification:
    source_id: str
    title: str = ""
    url: str = ""
    status: str = "verified"
    detail: str = ""
    verified_at: datetime = field(default_factory=datetime.now)


@dataclass
class ContentClaim:
    claim_text: str
    cited_sources: list[str] = field(default_factory=list)
    verification_status: str = "supported"
    confidence: float = 0.0
    detail: str = ""
    corrected_text: Optional[str] = None


@dataclass
class VerificationResult:
    source_verifications: list[SourceVerification] = field(default_factory=list)
    content_claims: list[ContentClaim] = field(default_factory=list)
    slot_verifications: list[SlotVerification] = field(default_factory=list)
    overall_confidence: float = 0.0
    claim_confidence: float = 0.0
    source_confidence: float = 0.0
    slot_confidence: float = 0.0
    citation_coverage: float = 0.0
    verified_citation_ratio: float = 0.0
    supported_claim_ratio: float = 0.0
    confidence_label: str = "보통"
    removed_claims: list[str] = field(default_factory=list)
    modified_claims: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    critical_issues: list[str] = field(default_factory=list)


@dataclass
class FinalAnswer:
    answer: str = ""
    confidence_score: float = 0.0
    confidence_label: str = "보통"
    verified_sources: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
