"""Tests for key-pool failover logic."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.llm import parse_simulate_header


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_failover.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("LLM_API_KEYS", "fake_key_1,fake_key_2")
    monkeypatch.setenv("GROQ_API_KEY", " ")
    monkeypatch.setenv("ENABLE_FAILURE_SIMULATION", "true")
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


def test_simulation_header_accepts_only_documented_statuses():
    assert parse_simulate_header("key_1=429,key_2=503") == {
        "key_1": 429,
        "key_2": 503,
    }
    assert parse_simulate_header("key_1=418") is None


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
            json={"session_id": "s-8272cc2d63b4c898178a0ba8248230aba981ce563e57ed12f6368da1373d494b", "message": "hello"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata"]["key_id"] == "key_2"
    assert data["metadata"]["fallback_attempts"] == 1


@pytest.mark.asyncio
async def test_invalid_gemini_key_falls_back_to_next_key(client):
    good_resp = _mock_response("fallback after invalid key")

    async def side_effect(**kwargs):
        if kwargs.get("api_key") == "fake_key_1":
            raise Exception("API key not valid. Please pass a valid API key.")
        return good_resp

    with patch("app.llm.litellm.acompletion", side_effect=side_effect):
        resp = await client.post(
            "/chat", json={"session_id": "s-0fbf9ea7cc5a39ecfc007da1f7e135a23e1f54fa46cabc39cb00581523ab4680", "message": "hello"}
        )

    assert resp.status_code == 200
    assert resp.json()["metadata"]["key_id"] == "key_2"
    assert resp.json()["metadata"]["fallback_attempts"] == 1


@pytest.mark.asyncio
async def test_groq_provider_is_used_and_reported(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake_groq_key")
    monkeypatch.setenv("GROQ_MODEL", "groq/openai/gpt-oss-20b")
    from app.config import get_settings
    get_settings.cache_clear()
    good_resp = _mock_response("Groq response")

    async def side_effect(**kwargs):
        assert kwargs["api_key"] == "fake_groq_key"
        assert kwargs["model"] == "groq/openai/gpt-oss-20b"
        return good_resp

    with patch("app.llm.litellm.acompletion", side_effect=side_effect):
        resp = await client.post(
            "/chat", json={"session_id": "s-cc5c670a8ad53385c6fa66924518672979379999f64b8d192c956b06a91dba23", "message": "hello"}
        )

    assert resp.status_code == 200
    assert resp.json()["metadata"]["key_id"] == "groq_key_1"
    assert resp.json()["metadata"]["model"] == "groq/openai/gpt-oss-20b"


@pytest.mark.asyncio
async def test_groq_auth_failure_falls_back_to_gemini(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake_groq_key")
    from app.config import get_settings
    get_settings.cache_clear()
    good_resp = _mock_response("Gemini fallback response")

    async def side_effect(**kwargs):
        if kwargs.get("api_key") == "fake_groq_key":
            raise Exception("401 invalid_api_key")
        return good_resp

    with patch("app.llm.litellm.acompletion", side_effect=side_effect):
        resp = await client.post(
            "/chat", json={"session_id": "s-9acdc754bc9561b7f8073b7a7a9bcfbdce37cc3613d310ecdd173ef2445c0cb3", "message": "hello"}
        )

    assert resp.status_code == 200
    assert resp.json()["metadata"]["key_id"] == "key_1"
    assert resp.json()["metadata"]["model"] == "gemini/gemini-3.8-flash"
    assert resp.json()["metadata"]["fallback_attempts"] == 1


# ---------------------------------------------------------------------------
# *=429 means all keys fail → 503
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wildcard_failure_returns_503(client):
    resp = await client.post(
        "/chat",
        json={"session_id": "s-eac34041273d800c5d9626686105880c26b646cb82fa242e46e573f2e8070574", "message": "hello"},
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
            json={"session_id": "s-87cbe9e45b52862be0e4ead43d1156261b7d1d834b45d8fa301f8fed1ffe9602", "message": "hi"},
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
            json={"session_id": "s-20fd17873a5b5714a4f63aec89d0267484f4ca41b951165f8232c7bed87aff30", "message": "hi"},
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
        json={"session_id": "s-b485d00562f2695edc57eb65aa9cb69dec4cb567faa1efeb47b6eea4590231da", "message": "should not be saved"},
        headers={"X-Simulate-Failure": "*=429"},
    )
    assert resp.status_code == 503
    # Session should not exist
    history_resp = await client.get("/sessions/s-b485d00562f2695edc57eb65aa9cb69dec4cb567faa1efeb47b6eea4590231da/messages")
    assert history_resp.status_code == 404
