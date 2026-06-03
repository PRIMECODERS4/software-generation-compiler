"""Application configuration."""

from __future__ import annotations

import os


class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    USE_LLM: bool = bool(OPENAI_API_KEY)
    MAX_RETRIES: int = 3
    VALIDATION_STRICT: bool = True
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    CORS_ORIGINS: list[str] = ["*"]


settings = Settings()
