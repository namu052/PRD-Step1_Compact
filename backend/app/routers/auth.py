from fastapi import APIRouter

from app.core.security import wipe_password
from app.core.session_manager import session_manager
from app.models.schemas import AuthRequest, AuthResponse, LogoutRequest
from app.services.gpki_service import gpki_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/certs")
async def list_certs():
    return await gpki_service.list_certs()


@router.post("/gpki", response_model=AuthResponse)
async def gpki_login(payload: AuthRequest):
    password = payload.password
    try:
        result = await gpki_service.authenticate(payload.cert_id, password)
        if not result.get("success"):
            return AuthResponse(success=False, error=result.get("error", "로그인 실패"))

        session = await session_manager.create_session(payload.cert_id, password)
        return AuthResponse(
            success=True,
            user_name=session.user_name,
            session_id=session.session_id,
        )
    finally:
        wipe_password(password)


@router.post("/logout")
async def logout(payload: LogoutRequest):
    await session_manager.destroy_session(payload.session_id)
    return {"success": True}
