"""Pydantic v2 request/response DTOs exposed by the HTTP API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

FormType = Literal["10-K", "10-Q"]


class QueryRequest(BaseModel):
    """Inbound payload for /v1/query."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=3, max_length=2000)
    max_results: int = Field(5, ge=1, le=20)


class Citation(BaseModel):
    """A single supporting span returned alongside an answer."""

    model_config = ConfigDict(extra="forbid")

    filing_ticker: str
    filing_form_type: FormType
    filing_date: date
    page_number: int = Field(..., ge=0)
    snippet: str
    score: float = Field(..., ge=0.0, le=1.0)


class Answer(BaseModel):
    """Structured LLM answer returned by /v1/query."""

    model_config = ConfigDict(extra="forbid")

    text: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    latency_ms: int = Field(..., ge=0)


class FilingResponse(BaseModel):
    """Filing record as exposed via the HTTP API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticker: str
    form_type: FormType
    filing_date: date
    accession_number: str


class EvalReport(BaseModel):
    """Summary of a single offline evaluation run."""

    model_config = ConfigDict(from_attributes=True)

    run_id: str
    config: dict
    hallucination_rate: float = Field(..., ge=0.0, le=1.0)
    recall_at_10: float = Field(..., ge=0.0, le=1.0)
    created_at: datetime
