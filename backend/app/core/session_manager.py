import uuid

from app.config import get_settings
from app.models.session import Session


class SessionManager:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}

    async def create_session(self, cert_id: str, password: str) -> Session:
        session_id = str(uuid.uuid4())
        mock_users = {"cert_001": "홍길동", "cert_002": "김영희"}
        user_name = mock_users.get(cert_id, "사용자")
        session = Session(session_id=session_id, user_name=user_name, cert_id=cert_id)
        self.sessions[session_id] = session
        return session

    async def get_session(self, session_id: str):
        session = self.sessions.get(session_id)
        if session and not session.is_expired(get_settings().session_timeout_minutes):
            session.touch()
            return session
        if session:
            await self.destroy_session(session_id)
        return None

    async def destroy_session(self, session_id: str) -> None:
        session = self.sessions.pop(session_id, None)
        if session and session.browser_context:
            try:
                await session.browser_context.close()
            except Exception:
                pass

    async def cleanup_expired(self) -> None:
        timeout = get_settings().session_timeout_minutes
        expired = [sid for sid, session in self.sessions.items() if session.is_expired(timeout)]
        for sid in expired:
            await self.destroy_session(sid)


session_manager = SessionManager()
