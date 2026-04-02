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
    """수동 로그인 완료 후 로그인 상태를 재확인한다.
    Playwright 브라우저를 앞으로 가져온 뒤 로그인 여부를 체크한다."""
    await crawler_service.bring_browser_to_front()
    logged_in = await crawler_service.check_olta_login()
    if logged_in:
        return {"success": True, "message": "OLTA 로그인 확인 완료"}
    return {"success": False, "message": "OLTA 로그인이 확인되지 않습니다. Playwright 브라우저에서 로그인해 주세요."}


@router.get("/olta-debug")
async def olta_debug():
    """디버그: Playwright 페이지의 현재 상태를 덤프한다."""
    try:
        page = await crawler_service.ensure_shared_page()
        url = page.url
        texts = await page.evaluate("""
            () => {
                const candidates = Array.from(document.querySelectorAll(
                    'a, button, input[type="button"], input[type="submit"]'
                ));
                return candidates.slice(0, 30).map(n => {
                    const text = (n.textContent || '').trim().substring(0, 50);
                    const value = (n.value || '').trim().substring(0, 50);
                    const onclick = (n.getAttribute('onclick') || '').substring(0, 80);
                    const tag = n.tagName;
                    return {tag, text, value, onclick};
                });
            }
        """)
        body_lines = await page.evaluate("""
            () => {
                const body = document.body?.innerText || '';
                return body.split('\\n').filter(l => /로그|login|logout/i.test(l)).slice(0, 10);
            }
        """)
        return {"url": url, "buttons": texts, "body_login_lines": body_lines}
    except Exception as e:
        return {"error": str(e)}
