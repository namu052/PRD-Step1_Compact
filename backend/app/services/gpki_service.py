from app.config import get_settings
from app.models.schemas import CertInfo


MOCK_CERTS = [
    {
        "id": "cert_001",
        "owner": "홍길동",
        "department": "OO시 세무과",
        "validFrom": "2024-01-01",
        "validTo": "2027-12-31",
        "serial": "A1B2C3D4E5F6",
    },
    {
        "id": "cert_002",
        "owner": "김영희",
        "department": "OO시 재무과",
        "validFrom": "2024-01-01",
        "validTo": "2027-12-31",
        "serial": "F6E5D4C3B2A1",
    },
]


class GPKIService:
    async def list_certs(self) -> list[CertInfo]:
        _ = get_settings()
        return [CertInfo(**item) for item in MOCK_CERTS]

    async def authenticate(self, cert_id: str, password: str) -> dict:
        _ = get_settings()
        cert = next((item for item in MOCK_CERTS if item["id"] == cert_id), None)
        if not cert:
            return {"success": False, "error": "인증서를 찾을 수 없습니다"}
        if password != "test1234":
            return {"success": False, "error": "비밀번호가 일치하지 않습니다"}
        return {"success": True, "user_name": cert["owner"]}


gpki_service = GPKIService()
