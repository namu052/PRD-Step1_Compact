from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class Session:
    session_id: str
    user_name: str
    cert_id: str
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    browser_context: Optional[Any] = None
    crawl_cache: dict = field(default_factory=dict)

    def touch(self) -> None:
        self.last_active = datetime.now()

    def is_expired(self, timeout_minutes: int) -> bool:
        elapsed = (datetime.now() - self.last_active).total_seconds() / 60
        return elapsed > timeout_minutes
