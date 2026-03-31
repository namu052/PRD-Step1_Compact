import pytest


@pytest.fixture(autouse=True)
def force_fallback_paths(monkeypatch):
    async def fail_real_search(*args, **kwargs):
        raise RuntimeError("test fallback crawler")

    async def fail_create_text(*args, **kwargs):
        raise RuntimeError("test fallback text")

    async def fail_create_json(*args, **kwargs):
        raise RuntimeError("test fallback json")

    async def fail_create_embeddings(*args, **kwargs):
        raise RuntimeError("test fallback embeddings")

    from app.services.crawler_service import crawler_service
    from app.services.openai_service import openai_service

    monkeypatch.setattr(crawler_service, "_real_search", fail_real_search)
    monkeypatch.setattr(openai_service, "create_text", fail_create_text)
    monkeypatch.setattr(openai_service, "create_json", fail_create_json)
    monkeypatch.setattr(openai_service, "create_embeddings", fail_create_embeddings)


@pytest.fixture
def mock_session_id():
    import asyncio

    from app.core.session_manager import session_manager

    session = asyncio.get_event_loop().run_until_complete(
        session_manager.create_session("cert_001", "test1234")
    )
    return session.session_id
