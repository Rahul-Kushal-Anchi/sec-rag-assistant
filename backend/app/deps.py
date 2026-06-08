"""FastAPI dependency providers. Real wiring happens once retrieval/generation are implemented."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.db.session import SessionLocal, get_session
from app.ingest.embedder import OpenAIEmbedder
from app.retrieval.dense import DenseRetriever

# Lazy-initialized singleton retriever
_dense_retriever: DenseRetriever | None = None


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a database session per request; rollback on error."""
    async for session in get_session():
        yield session


def get_settings() -> Settings:
    """Return the singleton Settings instance."""
    return settings


def get_dense_retriever() -> DenseRetriever:
    """Return the singleton DenseRetriever instance (lazy initialization)."""
    global _dense_retriever
    if _dense_retriever is None:
        embedder = OpenAIEmbedder(
            api_key=settings.OPENAI_API_KEY,
            model=settings.EMBEDDING_MODEL,
        )
        _dense_retriever = DenseRetriever(
            db_session_maker=SessionLocal,
            embedder=embedder,
        )
    return _dense_retriever


DbSession = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
DenseRetrieverDep = Annotated[DenseRetriever, Depends(get_dense_retriever)]

