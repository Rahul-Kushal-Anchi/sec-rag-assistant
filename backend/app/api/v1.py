"""Version 1 HTTP routes. Endpoints are stubbed until retrieval/generation land."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.schemas import (
    Answer,
    EvalReport,
    FilingResponse,
    QueryRequest,
)

router = APIRouter(tags=["v1"])


@router.post(
    "/query",
    response_model=Answer,
    summary="Ask a question against the SEC filings corpus.",
    description="Will stream tokens via SSE once the answerer pipeline is wired up.",
)
async def query(payload: QueryRequest) -> Answer:
    """Retrieve, rerank, and generate an answer with citations."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="answerer pipeline not implemented yet",
    )


@router.get(
    "/filings",
    response_model=list[FilingResponse],
    summary="List ingested filings.",
)
async def list_filings(
    ticker: str | None = Query(default=None),
    form_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[FilingResponse]:
    """Return ingested filings filtered by ticker/form_type with pagination."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="filings listing not implemented yet",
    )


@router.get(
    "/eval/runs",
    response_model=list[EvalReport],
    summary="List recent evaluation runs.",
)
async def list_eval_runs() -> list[EvalReport]:
    """Return summaries of previous offline evaluation runs."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="eval reporting not implemented yet",
    )
