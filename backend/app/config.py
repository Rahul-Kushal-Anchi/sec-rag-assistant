"""Application configuration loaded from environment variables via Pydantic Settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root (parent of backend/) — where .env lives
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Typed application settings sourced from environment variables and ``.env``."""

    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    DATABASE_URL: str = Field(
        ...,
        description="Async SQLAlchemy URL, e.g. postgresql+asyncpg://user:pw@host:5432/db",
    )
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key for embeddings and fallback LLM.")
    ANTHROPIC_API_KEY: str = Field(..., description="Anthropic API key for Claude (default LLM).")

    LANGSMITH_API_KEY: str | None = Field(default=None, description="Optional LangSmith API key.")
    LANGSMITH_PROJECT: str = Field(default="sec-rag-assistant")
    LANGSMITH_TRACING: bool = Field(default=False)

    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")
    RERANKER_MODEL: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2")

    LOG_LEVEL: str = Field(default="INFO")

    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])


settings = Settings()  # type: ignore[call-arg]
