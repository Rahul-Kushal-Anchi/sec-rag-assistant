"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import router as v1_router
from app.config import settings
from app.logging_config import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: configure logging on startup; nothing to tear down yet."""
    configure_logging(settings.LOG_LEVEL)
    logger = get_logger("app.main")
    logger.info("application_startup", log_level=settings.LOG_LEVEL)
    yield
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    """Application factory so tests can build an isolated instance."""
    app = FastAPI(
        title="SEC RAG Assistant",
        version="0.1.0",
        description="Retrieval-augmented question answering over SEC 10-K and 10-Q filings.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router, prefix="/v1")

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        """Liveness probe used by docker-compose and CI."""
        return {"status": "ok"}

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    return app


app = create_app()
