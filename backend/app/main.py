"""FastAPI application entry point."""
from __future__ import annotations

import time
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import check_db, get_session_messages, init_db, save_messages, session_exists
from app.llm import (
    AllProvidersUnavailable,
    call_with_fallback,
    extract_tokens,
    get_key_pool,
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

app = FastAPI(title="AI Chat API", version="1.0.0")

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    await init_db()


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
    keys = get_key_pool()
    return HealthResponse(
        status="ok",
        keys_configured=len(keys),
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
    history = await get_session_messages(body.session_id)

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
        response, used_key_id, fallback_attempts = await call_with_fallback(
            messages=llm_messages,
            simulate_failures=simulate_failures,
        )
    except AllProvidersUnavailable:
        raise HTTPException(status_code=503, detail="all providers unavailable")

    latency_ms = int((time.monotonic() - start_time) * 1000)

    # Determine if this was a cache hit
    hit = is_cache_hit(response)
    resolution_source = "LLM_CACHE" if hit else "LIVE_INFERENCE"
    key_id_out = None if hit else used_key_id
    fa_out = 0 if hit else fallback_attempts

    # Extract reply text
    reply_text: str = response.choices[0].message.content

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
            "model": cfg.llm_model,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "key_id": key_id_out,
            "fallback_attempts": fa_out,
        },
    )


@app.get("/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
async def get_session(session_id: str) -> SessionMessagesResponse:
    exists = await session_exists(session_id)
    if not exists:
        raise HTTPException(status_code=404, detail="session not found")

    messages = await get_session_messages(session_id)
    items = []
    for m in messages:
        items.append(
            MessageItem(
                role=m["role"],
                content=m["content"],
                metadata=m.get("metadata"),
            )
        )
    return SessionMessagesResponse(session_id=session_id, messages=items)
