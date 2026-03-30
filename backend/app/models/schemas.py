from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


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


class CrawlResult(BaseModel):
    id: str
    title: str
    type: str
    content: str
    preview: str
    url: str
    relevance_score: float = 0.0
    document_year: Optional[int] = None
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
            "url": self.url,
            "document_year": self.document_year,
            "crawled_at": self.crawled_at.isoformat(),
        }
