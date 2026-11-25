"""Tests for LiteLLM cache hit/miss behavior."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_cache.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("LLM_API_KEYS", "fake_key_1,fake_key_2")
    monkeypatch.setenv("GROQ_API_KEY", " ")
    monkeypatch.setenv("ENABLE_FAILURE_SIMULATION", "false")
    from app.config import get_settings
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client():
    from app.database import init_db
    from app.main import app
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _live_response(text="cached answer"):
    usage = MagicMock()
    usage.prompt_tokens = 8
    usage.completion_tokens = 4

    message = MagicMock()
    message.content = text

    choice = MagicMock()
    choice.message = message

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    resp._hidden_params = {"cache_hit": False}
    return resp


def _cached_response(text="cached answer"):
    usage = MagicMock()
    usage.prompt_tokens = 8
    usage.completion_tokens = 4

    message = MagicMock()
    message.content = text

    choice = MagicMock()
    choice.message = message

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    resp._hidden_params = {"cache_hit": True}
    return resp


# ---------------------------------------------------------------------------
# Same message returns LLM_CACHE on second call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_same_message_returns_cache_second_time(client):
    live = _live_response("42")
    cached = _cached_response("42")
    call_count = 0

    async def side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return live
        return cached

    with patch("app.llm.litellm.acompletion", side_effect=side_effect):
        # First call — live
        r1 = await client.post(
            "/chat",
            json={"session_id": "cache-test-a", "message": "What is six times seven?"},
        )
        assert r1.status_code == 200
        assert r1.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"
        assert r1.json()["metadata"]["key_id"] == "key_1"

        # Second call — cache hit
        r2 = await client.post(
            "/chat",
            json={"session_id": "cache-test-b", "message": "What is six times seven?"},
        )
        assert r2.status_code == 200
        assert r2.json()["metadata"]["resolution_source"] == "LLM_CACHE"
        assert r2.json()["metadata"]["key_id"] is None
        assert r2.json()["metadata"]["fallback_attempts"] == 0


# ---------------------------------------------------------------------------
# Different message does NOT return from cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_different_message_not_from_cache(client):
    async def side_effect(**kwargs):
        # Always return live (no cache hit)
        return _live_response("different answer")

    with patch("app.llm.litellm.acompletion", side_effect=side_effect):
        r1 = await client.post(
            "/chat",
            json={"session_id": "cache-test-c", "message": "first question"},
        )
        r2 = await client.post(
            "/chat",
            json={"session_id": "cache-test-d", "message": "second question"},
        )

    assert r1.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert r2.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"
