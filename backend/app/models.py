"""Pydantic request / response models."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    session_id: str
    message: str
    system_prompt: Optional[str] = None

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 128:
            raise ValueError("session_id must be between 1 and 128 characters")
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 1:
            raise ValueError("message must not be empty")
        if len(trimmed) > 4000:
            raise ValueError("message must not exceed 4000 characters")
        return trimmed


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ChatMetadata(BaseModel):
    resolution_source: Literal["LIVE_INFERENCE", "LLM_CACHE"]
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    key_id: Optional[str]  # None on cache hit
    fallback_attempts: int


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    metadata: ChatMetadata


class HealthResponse(BaseModel):
    status: str
    keys_configured: int
    cache_enabled: bool


class MessageItem(BaseModel):
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


class SessionMessagesResponse(BaseModel):
    session_id: str
    messages: List[MessageItem]
