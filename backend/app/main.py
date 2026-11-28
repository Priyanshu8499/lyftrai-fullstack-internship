"""FastAPI application entry point."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from re import fullmatch
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import check_db, delete_session_messages, get_session_message_page, get_session_messages, init_db, save_messages
from app.llm import (
    AllProvidersUnavailable,
    call_with_fallback,
    extract_tokens,
    is_cache_hit,
    parse_simulate_header,
)
from app.models import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MessageItem,
    SessionMessagesResponse,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="AI Chat API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Simulate-Failure"],
)

_request_times = defaultdict(deque)
_rate_window_seconds = 60
_rate_limit = 20
_max_request_bytes = 16 * 1024


def add_security_headers(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.middleware("http")
async def protect_api(request: Request, call_next):
    """Add baseline browser protections and bound public chat traffic."""
    if request.url.path == "/chat" and request.method == "POST":
        try:
            if int(request.headers.get("content-length", "0")) > _max_request_bytes:
                return add_security_headers(JSONResponse(status_code=413, content={"detail": "request too large"}))
        except ValueError:
            return add_security_headers(JSONResponse(status_code=400, content={"detail": "invalid content length"}))

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        attempts = _request_times[client_ip]
        while attempts and now - attempts[0] >= _rate_window_seconds:
            attempts.popleft()
        if len(attempts) >= _rate_limit:
            return add_security_headers(JSONResponse(
                status_code=429,
                headers={"Retry-After": str(_rate_window_seconds)},
                content={"detail": "too many chat requests; try again shortly"},
            ))
        attempts.append(now)

    return add_security_headers(await call_next(request))


def validate_session_token(session_id: str) -> None:
    if not fullmatch(r"s-[0-9a-f]{64}", session_id):
        raise HTTPException(status_code=404, detail="session not found")


# ---------------------------------------------------------------------------
# Exception handlers — ensure no stack traces or HTML leak out
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    await check_db()
    key_count = get_settings().configured_key_count
    if key_count < 2:
        raise HTTPException(
            status_code=503,
            detail="at least two provider API keys are required",
        )
    return HealthResponse(
        status="ok",
        keys_configured=key_count,
        cache_enabled=True,  # LiteLLM cache is always enabled
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    x_simulate_failure: Optional[str] = Header(default=None),
) -> ChatResponse:
    cfg = get_settings()

    # Parse failure simulation header (only when feature flag is on)
    simulate_failures = None
    if cfg.enable_failure_simulation and x_simulate_failure:
        simulate_failures = parse_simulate_header(x_simulate_failure)

    # Build messages list
    # Keep model context and database work bounded on long-running chats.
    history = await get_session_messages(body.session_id, limit=40)

    system_prompt = body.system_prompt or cfg.default_system_prompt
    llm_messages = []
    if system_prompt:
        llm_messages.append({"role": "system", "content": system_prompt})
    # Add history (only role + content for LLM context)
    for h in history:
        llm_messages.append({"role": h["role"], "content": h["content"]})
    # Append new user message
    llm_messages.append({"role": "user", "content": body.message})

    # Call LLM with failover
    start_time = time.monotonic()
    try:
        response, used_key_id, fallback_attempts, used_model = await asyncio.wait_for(
            call_with_fallback(
                messages=llm_messages,
                simulate_failures=simulate_failures,
            ),
            timeout=80,
        )
    except AllProvidersUnavailable:
        raise HTTPException(status_code=503, detail="all providers unavailable")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="the AI request timed out; please try again")

    latency_ms = int((time.monotonic() - start_time) * 1000)

    # Determine if this was a cache hit
    hit = is_cache_hit(response)
    resolution_source = "LLM_CACHE" if hit else "LIVE_INFERENCE"
    key_id_out = None if hit else used_key_id
    fa_out = 0 if hit else fallback_attempts

    # Extract reply text
    reply_text = response.choices[0].message.content
    if not isinstance(reply_text, str) or not reply_text.strip():
        raise HTTPException(status_code=503, detail="all providers unavailable")

    # Extract token counts
    input_tokens, output_tokens = extract_tokens(response)

    # Build metadata for storage
    assistant_meta = {
        "resolution_source": resolution_source,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }

    # Persist to DB
    await save_messages(
        session_id=body.session_id,
        user_content=body.message,
        assistant_content=reply_text,
        assistant_metadata=assistant_meta,
    )

    return ChatResponse(
        session_id=body.session_id,
        reply=reply_text,
        metadata={
            "resolution_source": resolution_source,
            "model": used_model,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "key_id": key_id_out,
            "fallback_attempts": fa_out,
        },
    )


@app.get("/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
async def get_session(
    session_id: str,
    before_id: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=100),
) -> SessionMessagesResponse:
    validate_session_token(session_id)
    messages, next_before_id = await get_session_message_page(
        session_id, before_id=before_id, limit=limit
    )
    if not messages:
        raise HTTPException(status_code=404, detail="session not found")
    items = [MessageItem(**m) for m in messages]
    return SessionMessagesResponse(
        session_id=session_id, messages=items, next_before_id=next_before_id
    )


@app.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str) -> Response:
    validate_session_token(session_id)
    deleted = await delete_session_messages(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="session not found")
    return Response(status_code=204)
