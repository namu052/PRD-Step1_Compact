from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_session() -> str:
    response = client.post(
        "/api/auth/gpki",
        json={"cert_id": "cert_001", "password": "test1234"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    return payload["session_id"]


def test_chat_pipeline_stream_order():
    session_id = create_session()

    response = client.post("/api/chat", json={"session_id": session_id, "question": "취득세 감면 대상"})
    assert response.status_code == 200
    body = response.text

    assert "event: stage_change" in body
    assert '"stage": "crawling"' in body
    assert '"stage": "drafting"' in body
    assert '"stage": "verifying"' in body
    assert '"stage": "finalizing"' in body
    assert "event: notice" in body
    assert "질문 분석 완료" in body
    assert "자료 수집 및 분석 완료" in body
    assert "초안 작성 완료" in body
    assert "검증 완료" in body
    assert "최종 답변 정리 완료" in body
    assert "event: token" in body
    assert "event: sources" in body
    assert '"stage": "done"' in body
    assert body.index('"stage": "crawling"') < body.index('"stage": "drafting"')
    assert body.index('"stage": "drafting"') < body.index("event: token")
    assert body.index('"stage": "verifying"') > body.index("event: token")
    assert body.index('"stage": "finalizing"') > body.index('"stage": "verifying"')
    assert body.index("event: sources") > body.index('"stage": "finalizing"')
    assert body.rindex('"stage": "done"') > body.index("event: sources")
    assert '"confidence"' in body


def test_chat_requires_session():
    response = client.post(
        "/api/chat",
        json={"session_id": "missing-session", "question": "취득세 감면 대상"},
    )
    assert response.status_code == 401


def test_chat_no_results_message():
    session_id = create_session()

    response = client.post("/api/chat", json={"session_id": session_id, "question": "자동차세 환급"})
    assert response.status_code == 200
    body = response.text

    assert 'event: token' in body
    assert '못했습니다' in body
    assert 'event: sources' in body
    assert '"confidence": null' in body


def test_preview_returns_cached_source():
    session_id = create_session()
    response = client.post("/api/chat", json={"session_id": session_id, "question": "재산세 납부 기한"})
    assert response.status_code == 200

    preview = client.get(f"/api/preview/mock_law_003?session_id={session_id}")
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["id"] == "mock_law_003"
    assert "지방세법 제115조" in payload["title"]
