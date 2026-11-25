"""Tests for key-pool failover logic."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_failover.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("LLM_API_KEYS", "fake_key_1,fake_key_2")
    monkeypatch.setenv("ENABLE_FAILURE_SIMULATION", "true")
    from app.config import get_settings
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client():
    from app.database import init_db
    from app.main import app
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _mock_response(text="ok", input_tokens=5, output_tokens=3, cache_hit=False):
    usage = MagicMock()
    usage.prompt_tokens = input_tokens
    usage.completion_tokens = output_tokens

    message = MagicMock()
    message.content = text

    choice = MagicMock()
    choice.message = message

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    resp._hidden_params = {"cache_hit": cache_hit}
    return resp


# ---------------------------------------------------------------------------
# key_1=429 falls back to key_2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_key1_fails_fallback_to_key2(client):
    good_resp = _mock_response("fallback response")

    async def side_effect(**kwargs):
        if kwargs.get("api_key") == "fake_key_1":
            raise Exception("429 rate limit exceeded")
        return good_resp

    with patch("app.llm.litellm.acompletion", side_effect=side_effect):
        resp = await client.post(
            "/chat",
            json={"session_id": "fo-test-1", "message": "hello"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata"]["key_id"] == "key_2"
    assert data["metadata"]["fallback_attempts"] == 1


# ---------------------------------------------------------------------------
# *=429 means all keys fail → 503
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wildcard_failure_returns_503(client):
    resp = await client.post(
        "/chat",
        json={"session_id": "fo-test-2", "message": "hello"},
        headers={"X-Simulate-Failure": "*=429"},
    )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "all providers unavailable"


# ---------------------------------------------------------------------------
# fallback_attempts is correct
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_attempts_correct(client):
    good_resp = _mock_response("success on key_2")

    async def side_effect(**kwargs):
        if kwargs.get("api_key") == "fake_key_1":
            raise Exception("500 internal server error")
        return good_resp

    with patch("app.llm.litellm.acompletion", side_effect=side_effect):
        resp = await client.post(
            "/chat",
            json={"session_id": "fo-test-3", "message": "hi"},
        )
    assert resp.status_code == 200
    assert resp.json()["metadata"]["fallback_attempts"] == 1
    assert resp.json()["metadata"]["key_id"] == "key_2"


# ---------------------------------------------------------------------------
# Simulate header: key_1=429 → falls back, key_id=key_2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simulate_header_key1_429(client):
    good_resp = _mock_response("from key2")
    with patch("app.llm.litellm.acompletion", new_callable=AsyncMock, return_value=good_resp):
        resp = await client.post(
            "/chat",
            json={"session_id": "fo-test-4", "message": "hi"},
            headers={"X-Simulate-Failure": "key_1=429"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata"]["key_id"] == "key_2"
    assert data["metadata"]["fallback_attempts"] == 1


# ---------------------------------------------------------------------------
# 503 on simulated all-fail does NOT save history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_503_does_not_save_history(client):
    resp = await client.post(
        "/chat",
        json={"session_id": "fo-test-5", "message": "should not be saved"},
        headers={"X-Simulate-Failure": "*=429"},
    )
    assert resp.status_code == 503
    # Session should not exist
    history_resp = await client.get("/sessions/fo-test-5/messages")
    assert history_resp.status_code == 404
