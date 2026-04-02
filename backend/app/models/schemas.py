from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WebSearchResult(BaseModel):
    title: str
    url: str
    content: str
    score: float = 0.0


class VerificationRound(BaseModel):
    round_number: int
    confidence: float
    gaps_found: list[str] = []
    actions_taken: str = ""


class VerificationHistory(BaseModel):
    rounds: list[VerificationRound] = []
    final_confidence: float = 0.0

    def add_round(
        self,
        confidence: float,
        gaps: list[str] | None = None,
        actions: str = "",
    ) -> None:
        self.rounds.append(
            VerificationRound(
                round_number=len(self.rounds) + 1,
                confidence=confidence,
                gaps_found=gaps or [],
                actions_taken=actions,
            )
        )
        self.final_confidence = confidence

    def to_summary(self) -> str:
        if not self.rounds:
            return "검증 이력 없음"
        lines = []
        for r in self.rounds:
            gaps_text = f" | 미비점: {', '.join(r.gaps_found[:3])}" if r.gaps_found else ""
            lines.append(
                f"- {r.round_number}차 검증: 신뢰도 {round(r.confidence * 100, 1)}%{gaps_text}"
                + (f" | {r.actions_taken}" if r.actions_taken else "")
            )
        lines.append(f"- 최종 신뢰도: {round(self.final_confidence * 100, 1)}%")
        return "\n".join(lines)


class AuthRequest(BaseModel):
    cert_id: str
    password: str


class AuthResponse(BaseModel):
    success: bool
    user_name: Optional[str] = None
    session_id: Optional[str] = None
    error: Optional[str] = None


class LogoutRequest(BaseModel):
    session_id: str


class CertInfo(BaseModel):
    id: str
    owner: str
    department: str
    validFrom: str
    validTo: str
    serial: str


class ChatRequest(BaseModel):
    session_id: str
    question: str


class SourceCard(BaseModel):
    id: str
    title: str
    type: str
    preview: str


class SourceDetail(BaseModel):
    id: str
    title: str
    type: str
    content: str
    url: str
    crawled_at: Optional[datetime] = None


class BoardCollectionStat(BaseModel):
    board_name: str
    sub_board_name: Optional[str] = None
    collected_count: int = 0
    skipped: bool = False
    status: str = "pending"


class CollectionProgress(BaseModel):
    total_collected: int = 0
    boards: list[BoardCollectionStat] = Field(default_factory=list)
    current_board: Optional[str] = None
    current_sub_board: Optional[str] = None


class CrawlResult(BaseModel):
    id: str
    title: str
    type: str
    content: str
    preview: str
    url: str
    relevance_score: float = 0.0
    document_year: Optional[int] = None
    comments: str = ""
    crawled_at: datetime = Field(default_factory=datetime.now)

    def to_source_card(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "preview": self.preview,
        }

    def to_source_detail(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "content": self.content,
            "comments": self.comments,
            "url": self.url,
            "document_year": self.document_year,
            "crawled_at": self.crawled_at.isoformat(),
        }
