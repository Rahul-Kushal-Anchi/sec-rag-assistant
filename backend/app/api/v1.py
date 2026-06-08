"""Version 1 HTTP routes. Endpoints are stubbed until retrieval/generation land."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, status

from app.api.schemas import (
    Answer,
    Citation,
    EvalReport,
    FilingResponse,
    QueryRequest,
)
from app.deps import DenseRetrieverDep
from app.retrieval.dense import ChunkResult

router = APIRouter(tags=["v1"])


@router.post(
    "/query",
    response_model=Answer,
    summary="Ask a question against the SEC filings corpus.",
    description="Currently returns dense retrieval results. Will stream tokens via SSE once the answerer pipeline is wired up.",
)
async def query(payload: QueryRequest, retriever: DenseRetrieverDep) -> Answer:
    """Retrieve, rerank, and generate an answer with citations.
    
    For now, returns top chunks from dense retrieval as a simple answer.
    """
    # Retrieve top chunks using dense retrieval
    chunks = await retriever.retrieve(payload.question, top_k=payload.max_results)
    
    if not chunks:
        # No chunks found
        return Answer(
            text="No relevant information found in the SEC filings corpus.",
            citations=[],
            confidence=0.0,
            latency_ms=0,
        )
    
    # Build a simple response from the top chunks
    citations = [
        Citation(
            filing_ticker="UNKNOWN",  # TODO: join with Filing table
            filing_form_type="10-K",  # TODO: join with Filing table
            filing_date=date(2025, 1, 1),  # TODO: join with Filing table
            page_number=chunk.page_number,
            snippet=chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text,
            score=chunk.score,
        )
        for chunk in chunks[:5]  # Top 5 citations
    ]
    
    # Simple concatenation of top chunks as "answer"
    answer_text = "\n\n".join(chunk.text for chunk in chunks[:3])
    
    return Answer(
        text=answer_text,
        citations=citations,
        confidence=chunks[0].score if chunks else 0.0,
        latency_ms=0,  # TODO: track actual latency
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
