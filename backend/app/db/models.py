"""SQLAlchemy 2.0 ORM models for filings, chunks, and evaluation runs."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base used by all ORM models."""


FORM_TYPES = ("10-K", "10-Q")


class Filing(Base):
    """A single SEC filing ingested into the corpus."""

    __tablename__ = "filings"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    form_type: Mapped[str] = mapped_column(
        Enum(*FORM_TYPES, name="form_type_enum"), nullable=False
    )
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    accession_number: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    source_url: Mapped[str] = mapped_column(String(512), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chunks: Mapped[list[Chunk]] = relationship(
        "Chunk",
        back_populates="filing",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Chunk(Base):
    """A retrievable chunk of text extracted from a filing."""

    __tablename__ = "chunks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    filing_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    section: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding: Mapped[Any | None] = mapped_column(Vector(1536), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    filing: Mapped[Filing] = relationship("Filing", back_populates="chunks")


class EvalRun(Base):
    """A single offline evaluation run summary."""

    __tablename__ = "eval_runs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    hallucination_rate: Mapped[float] = mapped_column(Float, nullable=False)
    recall_at_10: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
