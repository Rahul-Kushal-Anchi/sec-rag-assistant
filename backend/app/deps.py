"""FastAPI dependency providers. Real wiring happens once retrieval/generation are implemented."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.db.session import get_session


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a database session per request; rollback on error."""
    async for session in get_session():
        yield session


def get_settings() -> Settings:
    """Return the singleton Settings instance."""
    return settings


DbSession = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
