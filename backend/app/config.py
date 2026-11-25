"""Application settings loaded from environment variables."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Comma-separated Gemini API keys
    llm_api_keys: str = ""

    # SQLite database path extracted from DATABASE_URL
    database_url: str = "sqlite:////data/app.db"

    # CORS origins
    allowed_origins: str = "http://localhost:3000"

    # Whether failure simulation via header is enabled
    enable_failure_simulation: bool = False

    # Default system prompt
    default_system_prompt: Optional[str] = "You are a helpful assistant."

    # LiteLLM model name
    llm_model: str = "gemini/gemini-3.8-flash"

    @property
    def key_pool(self) -> List[tuple[str, str]]:
        """Return [(key_id, api_key), ...] from LLM_API_KEYS env var."""
        if not self.llm_api_keys.strip():
            return []
        raw_keys = [k.strip() for k in self.llm_api_keys.split(",") if k.strip()]
        return [(f"key_{i + 1}", key) for i, key in enumerate(raw_keys)]

    @property
    def db_path(self) -> str:
        """Extract filesystem path from DATABASE_URL (strips sqlite://// prefix)."""
        url = self.database_url
        if url.startswith("sqlite:////"):
            return "/" + url[len("sqlite:////"):]
        if url.startswith("sqlite:///"):
            return url[len("sqlite:///"):]
        return url

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
