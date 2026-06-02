"""Shared pytest fixtures: app client, in-memory DB, deterministic mocks."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@pytest_asyncio.fixture()
async def db_engine():
    """In-memory async SQLite engine for fast unit tests.
    
    Note: SQLite doesn't support JSONB, so we handle it specially during table creation.
    """
    from app.db.models import Base
    from sqlalchemy.types import JSON
    from sqlalchemy.dialects.postgresql import JSONB
    
    # Create engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    
    # Temporarily replace JSONB columns with JSON for SQLite
    # This is a workaround since SQLite doesn't have JSONB
    def create_tables_sqlite_compat(connection):
        """Create tables with JSON instead of JSONB for SQLite."""
        # Iterate through all tables and temporarily swap JSONB -> JSON
        for table in Base.metadata.sorted_tables:
            for column in table.columns:
                if isinstance(column.type, JSONB):
                    column.type = JSON()
        
        Base.metadata.create_all(connection)
    
    # Create all tables with SQLite-compatible types
    async with engine.begin() as conn:
        await conn.run_sync(create_tables_sqlite_compat)
    
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    """Per-test session that rolls back at teardown."""
    session_maker = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest_asyncio.fixture()
async def db_session_maker(db_engine) -> async_sessionmaker[AsyncSession]:
    """Session maker factory for tests that need to create their own sessions."""
    return async_sessionmaker(bind=db_engine, expire_on_commit=False)


@pytest.fixture()
def mock_embedder() -> Any:
    """Return a deterministic embedder returning a 1536-d unit-ish vector."""

    def _embed(text: str) -> list[float]:
        seed = sum(ord(c) for c in text) or 1
        return [((seed * (i + 1)) % 1000) / 1000.0 for i in range(1536)]

    embedder = AsyncMock()
    embedder.embed.side_effect = _embed
    embedder.embed_batch.side_effect = lambda texts: [_embed(t) for t in texts]
    return embedder


@pytest.fixture()
def mock_llm_client() -> AsyncMock:
    """Async mock standing in for the production LLM client."""
    client = AsyncMock()
    client.chat.return_value = {
        "text": "stub answer",
        "citations": [],
        "confidence": 0.0,
    }
    return client


@pytest_asyncio.fixture()
async def client() -> AsyncIterator[AsyncClient]:
    """Async HTTP client targeting the FastAPI app via ASGI transport."""
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
