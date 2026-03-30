import os

import pytest

os.environ["USE_MOCK_CRAWLER"] = "true"
os.environ["USE_MOCK_LLM"] = "true"


@pytest.fixture
def mock_session_id():
    import asyncio

    from app.core.session_manager import session_manager

    session = asyncio.get_event_loop().run_until_complete(
        session_manager.create_session("cert_001", "test1234")
    )
    return session.session_id
