"""LiteLLM integration: key pool, caching, failover."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import litellm
from litellm.caching.caching import Cache

from app.config import get_settings

# ---------------------------------------------------------------------------
# Initialise LiteLLM in-memory cache once at module load time
# ---------------------------------------------------------------------------
litellm.cache = Cache()  # in-memory by default
litellm.success_callback = []
litellm.failure_callback = []


class AllProvidersUnavailable(Exception):
    """Raised when every key in the pool has been exhausted."""


SIMULATABLE_STATUSES = frozenset({429, 500, 502, 503})


def get_key_pool() -> List[Tuple[str, str]]:
    """Return [(key_id, api_key), ...] from settings."""
    return get_settings().key_pool


def is_retryable(exc: Exception) -> bool:
    """Return True for errors that warrant trying the next key."""
    msg = str(exc).lower()
    retryable_phrases = [
        "429",
        "401",
        "403",
        "rate limit",
        "quota",
        "500",
        "502",
        "503",
        "service unavailable",
        "internal server error",
        "bad gateway",
        "api key not valid",
        "invalid api key",
        "invalid_api_key",
        "api_key_invalid",
        "unauthorized",
    ]
    return any(phrase in msg for phrase in retryable_phrases)


def _parse_simulate_header(header_value: Optional[str]) -> Optional[Dict[str, int]]:
    """
    Parse `X-Simulate-Failure` header value.
    E.g. "key_1=429,key_2=500" → {"key_1": 429, "key_2": 500}
         "*=429"               → {"*": 429}
    Returns None if header is absent/empty.
    """
    if not header_value:
        return None
    result: Dict[str, int] = {}
    for part in header_value.split(","):
        part = part.strip()
        if "=" in part:
            key, _, status = part.partition("=")
            try:
                status_code = int(status.strip())
                if status_code in SIMULATABLE_STATUSES:
                    result[key.strip()] = status_code
            except ValueError:
                pass
    return result or None


async def call_with_fallback(
    messages: List[Dict[str, str]],
    simulate_failures: Optional[Dict[str, int]] = None,
) -> Tuple[Any, Optional[str], int, str]:
    """
    Call LiteLLM with key-pool fallback.

    Returns:
        (response, key_id, fallback_attempts, model)
        key_id is None on cache hit (detected after first successful call).
    """
    settings = get_settings()
    model = settings.llm_model
    # Keep provider credentials paired with their own model/provider. Never
    # send a provider's key to another provider's endpoint.
    providers: List[Tuple[str, str, str]] = []
    if settings.groq_api_key.strip():
        providers.append(("groq_key_1", settings.groq_model, settings.groq_api_key.strip()))
    providers.extend(
        (key_id, settings.llm_model, api_key)
        for key_id, api_key in get_key_pool()
    )

    # If no keys are configured, try with no key (will likely fail, but lets
    # LiteLLM surface the error naturally).
    if not providers:
        raise AllProvidersUnavailable()

    # Determine which keys are globally simulated to fail
    wildcard_fail = simulate_failures and "*" in simulate_failures

    last_error: Optional[Exception] = None
    fallback_attempts = 0

    for key_id, model, api_key in providers:
        # --- Wildcard simulation: all keys fail ---
        if wildcard_fail:
            fallback_attempts += 1
            last_error = Exception(f"Simulated failure for {key_id}")
            continue

        # --- Per-key simulation ---
        if simulate_failures and key_id in simulate_failures:
            fallback_attempts += 1
            last_error = Exception(
                f"Simulated {simulate_failures[key_id]} for {key_id}"
            )
            continue

        # --- Real call ---
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                api_key=api_key,
                caching=True,
            )
            return response, key_id, fallback_attempts, model
        except Exception as exc:
            if is_retryable(exc):
                fallback_attempts += 1
                last_error = exc
                continue
            raise  # Non-retryable errors propagate immediately

    raise AllProvidersUnavailable() from last_error


def is_cache_hit(response: Any) -> bool:
    """Return True if the LiteLLM response came from cache."""
    hidden = getattr(response, "_hidden_params", {}) or {}
    return bool(hidden.get("cache_hit", False))


def extract_tokens(response: Any) -> Tuple[int, int]:
    """Return (input_tokens, output_tokens) from a LiteLLM response."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    prompt = getattr(usage, "prompt_tokens", 0) or 0
    completion = getattr(usage, "completion_tokens", 0) or 0
    return prompt, completion


def parse_simulate_header(header_value: Optional[str]) -> Optional[Dict[str, int]]:
    """Public re-export so main.py can call it."""
    return _parse_simulate_header(header_value)
