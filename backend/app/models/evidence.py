from dataclasses import dataclass, field
from datetime import datetime

from app.models.schemas import CrawlResult


@dataclass
class EvidenceGroup:
    group_id: str
    theme: str
    rationale: str
    source_ids: list[str] = field(default_factory=list)
    representative_source_ids: list[str] = field(default_factory=list)
    primary_tax: str = ""
    primary_topic: str = ""
    source_types: list[str] = field(default_factory=list)
    review_notes: list[str] = field(default_factory=list)


@dataclass
class EvidenceSlot:
    slot_id: str
    group_id: str
    title: str
    summary: str
    issue: str = ""
    conclusion: str = ""
    applicability: str = ""
    exceptions: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    fact_distinctions: list[str] = field(default_factory=list)
    practice_notes: list[str] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)
    representative_source_ids: list[str] = field(default_factory=list)
    representative_links: list[str] = field(default_factory=list)
    source_type_summary: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_crawl_result(self) -> CrawlResult:
        content_lines = [
            self.summary,
            "",
            f"쟁점: {self.issue}" if self.issue else "",
            f"공통 결론: {self.conclusion}" if self.conclusion else "",
            f"적용 범위: {self.applicability}" if self.applicability else "",
            "",
            "핵심 근거:",
            *[f"- {point}" for point in self.key_points],
            "",
            "예외 및 제한:",
            *[f"- {point}" for point in self.exceptions],
            "",
            "해석 충돌 및 차이:",
            *[f"- {point}" for point in self.conflicts],
            "",
            "사실관계 차이:",
            *[f"- {point}" for point in self.fact_distinctions],
            "",
            "실무상 주의사항:",
            *[f"- {point}" for point in self.practice_notes],
            "",
            "대표 원문:",
            *[
                f"- {source_id}: {url}"
                for source_id, url in zip(self.representative_source_ids, self.representative_links, strict=False)
            ],
        ]
        return CrawlResult(
            id=self.slot_id,
            title=self.title,
            type="근거 묶음",
            content="\n".join(line for line in content_lines if line is not None).strip(),
            preview=(self.conclusion or self.summary)[:220],
            url=self.representative_links[0] if self.representative_links else "",
            relevance_score=self.confidence,
            crawled_at=datetime.now(),
        )


@dataclass
class SlotVerification:
    slot_id: str
    status: str = "supported"
    confidence: float = 0.0
    detail: str = ""
