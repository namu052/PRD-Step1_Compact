from fastapi import APIRouter

from app.core.security import wipe_password
from app.core.session_manager import session_manager
from app.models.schemas import AuthRequest, AuthResponse, LogoutRequest
from app.services.gpki_service import gpki_service
from app.services.crawler_service import crawler_service

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


@router.get("/olta-status")
async def olta_login_status():
    """OLTA 로그인 상태를 확인한다."""
    logged_in = await crawler_service.check_olta_login()
    return {"logged_in": logged_in}


@router.post("/olta-login")
async def olta_open_login():
    """수동 로그인을 위해 OLTA를 브라우저에서 연다."""
    url = await crawler_service.open_olta_for_login()
    return {
        "message": "브라우저에서 OLTA 로그인을 완료한 후 '로그인 확인' 버튼을 눌러주세요.",
        "url": url,
    }


@router.post("/olta-verify")
async def olta_verify_login():
    """수동 로그인 완료 후 로그인 상태를 재확인한다."""
    logged_in = await crawler_service.check_olta_login()
    if logged_in:
        return {"success": True, "message": "OLTA 로그인 확인 완료"}
    return {"success": False, "message": "OLTA 로그인이 확인되지 않습니다. 다시 시도해주세요."}
