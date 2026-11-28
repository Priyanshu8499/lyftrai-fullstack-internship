"""Tests for /health, /chat and /sessions endpoints."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# App fixture with in-memory SQLite
# ---------------------------------------------------------------------------

TEST_SESSION = "s-4831ce131be853e133a5f344c9474f81f5fe92147975fd92f7bfd9f111148b70"


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    """Point the app at a fresh temp database for every test."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("LLM_API_KEYS", "fake_key_1,fake_key_2")
    monkeypatch.setenv("GROQ_API_KEY", " ")
    monkeypatch.setenv("ENABLE_FAILURE_SIMULATION", "true")
    # Bust settings cache
    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import _request_times
    _request_times.clear()


@pytest_asyncio.fixture
async def client():
    from app.database import init_db
    from app.main import app
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helper: build a mock LiteLLM response
# ---------------------------------------------------------------------------

def _mock_litellm_response(text="Hello!", input_tokens=10, output_tokens=5):
    usage = MagicMock()
    usage.prompt_tokens = input_tokens
    usage.completion_tokens = output_tokens

    message = MagicMock()
    message.content = text

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    response._hidden_params = {"cache_hit": False}
    return response


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_returns_correct_schema(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["keys_configured"] == 2
    assert data["cache_enabled"] is True


@pytest.mark.asyncio
async def test_health_requires_at_least_two_keys(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEYS", "only_one_key")
    from app.config import get_settings
    get_settings.cache_clear()

    resp = await client.get("/health")

    assert resp.status_code == 503
    assert resp.json()["detail"] == "at least two provider API keys are required"


@pytest.mark.asyncio
async def test_api_docs_are_not_exposed(client):
    assert (await client.get("/docs")).status_code == 404
    assert (await client.get("/openapi.json")).status_code == 404


# ---------------------------------------------------------------------------
# POST /chat - validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_422_empty_message(client):
    resp = await client.post("/chat", json={"session_id": "s-e8bc163c82eee18733288c7d4ac636db3a6deb013ef2d37b68322be20edc45cc", "message": "   "})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_chat_422_whitespace_session_id(client):
    resp = await client.post("/chat", json={"session_id": "   ", "message": "hello"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_chat_rejects_short_session_capability(client):
    resp = await client.post("/chat", json={"session_id": "guess", "message": "hello"})
    assert resp.status_code == 422
    history = await client.get("/sessions/guess/messages")
    assert history.status_code == 404


@pytest.mark.asyncio
async def test_chat_rejects_oversized_custom_instructions(client):
    resp = await client.post(
        "/chat",
        json={"session_id": TEST_SESSION, "message": "hello", "system_prompt": "x" * 2001},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_returns_security_headers(client):
    resp = await client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["cache-control"] == "no-store"
    assert resp.headers["x-frame-options"] == "DENY"


@pytest.mark.asyncio
async def test_chat_422_message_too_long(client):
    resp = await client.post("/chat", json={"session_id": "s-e8bc163c82eee18733288c7d4ac636db3a6deb013ef2d37b68322be20edc45cc", "message": "x" * 4001})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_chat_422_missing_session_id(client):
    resp = await client.post("/chat", json={"message": "hello"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_chat_422_missing_message(client):
    resp = await client.post("/chat", json={"session_id": "s-e8bc163c82eee18733288c7d4ac636db3a6deb013ef2d37b68322be20edc45cc"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /chat - happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_valid_returns_correct_schema(client):
    mock_resp = _mock_litellm_response("Paris is the capital of France.")
    with patch("app.llm.litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
        resp = await client.post(
            "/chat", json={"session_id": TEST_SESSION, "message": "What is the capital of France?"}
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == TEST_SESSION
    assert data["reply"] == "Paris is the capital of France."
    meta = data["metadata"]
    assert meta["resolution_source"] == "LIVE_INFERENCE"
    assert meta["model"] == "gemini/gemini-3.8-flash"
    assert isinstance(meta["latency_ms"], int)
    assert meta["input_tokens"] == 10
    assert meta["output_tokens"] == 5
    assert meta["key_id"] == "key_1"
    assert meta["fallback_attempts"] == 0


# ---------------------------------------------------------------------------
# GET /sessions/{id}/messages - 404 for unknown session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_session_404_unknown(client):
    resp = await client.get("/sessions/s-ebb7f95aef63176c698eedc738814e30f28a50dcfa23b3e83e917ceee670ad96/messages")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "session not found"


# ---------------------------------------------------------------------------
# Session history is stored after chat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_history_stored_after_chat(client):
    mock_resp = _mock_litellm_response("42 is the answer.")
    with patch("app.llm.litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
        await client.post(
            "/chat", json={"session_id": "s-268559d43cb6e25caa073bc3c4846d87c931f2a67d834c4dbac2005981e628fa", "message": "What is the answer?"}
        )

    resp = await client.get("/sessions/s-268559d43cb6e25caa073bc3c4846d87c931f2a67d834c4dbac2005981e628fa/messages")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "s-268559d43cb6e25caa073bc3c4846d87c931f2a67d834c4dbac2005981e628fa"
    msgs = data["messages"]
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "What is the answer?"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "42 is the answer."
    assert msgs[1]["metadata"]["resolution_source"] == "LIVE_INFERENCE"


@pytest.mark.asyncio
async def test_session_history_is_paginated(client):
    from app.database import save_messages

    await save_messages(TEST_SESSION, "first question", "first answer", {})
    await save_messages(TEST_SESSION, "second question", "second answer", {})

    latest = await client.get(f"/sessions/{TEST_SESSION}/messages?limit=2")
    assert latest.status_code == 200
    latest_data = latest.json()
    assert [message["content"] for message in latest_data["messages"]] == [
        "second question",
        "second answer",
    ]
    assert latest_data["next_before_id"] is not None

    earlier = await client.get(
        f"/sessions/{TEST_SESSION}/messages?limit=2&before_id={latest_data['next_before_id']}"
    )
    assert earlier.status_code == 200
    assert [message["content"] for message in earlier.json()["messages"]] == [
        "first question",
        "first answer",
    ]
    assert earlier.json()["next_before_id"] is None


@pytest.mark.asyncio
async def test_delete_session_removes_history(client):
    mock_resp = _mock_litellm_response("A saved reply.")
    with patch("app.llm.litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
        await client.post("/chat", json={"session_id": "s-22907f242f62053d498ed6cd8d04eb158f8227469618855a9897cb795042af05", "message": "Save this"})

    response = await client.delete("/sessions/s-22907f242f62053d498ed6cd8d04eb158f8227469618855a9897cb795042af05")

    assert response.status_code == 204
    assert (await client.get("/sessions/s-22907f242f62053d498ed6cd8d04eb158f8227469618855a9897cb795042af05/messages")).status_code == 404


@pytest.mark.asyncio
async def test_delete_session_404_unknown(client):
    response = await client.delete("/sessions/s-ebb7f95aef63176c698eedc738814e30f28a50dcfa23b3e83e917ceee670ad96")
    assert response.status_code == 404
    assert response.json()["detail"] == "session not found"
