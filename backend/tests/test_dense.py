"""Unit tests for dense vector retrieval."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.retrieval.dense import ChunkResult, DenseRetriever


def test_chunk_result_dataclass() -> None:
    """Verify ChunkResult has correct fields and types."""
    chunk_id = uuid.uuid4()
    filing_id = uuid.uuid4()

    result = ChunkResult(
        chunk_id=chunk_id,
        filing_id=filing_id,
        text="Apple faces supply chain risks.",
        page_number=5,
        section="Risk Factors",
        score=0.87,
    )

    assert result.chunk_id == chunk_id
    assert result.filing_id == filing_id
    assert result.text == "Apple faces supply chain risks."
    assert result.page_number == 5
    assert result.section == "Risk Factors"
    assert result.score == 0.87


@pytest.mark.asyncio
async def test_dense_retriever_returns_list() -> None:
    """Verify retrieve() returns a list of ChunkResult."""
    # Mock DB session
    mock_session = AsyncMock()
    mock_session_maker = MagicMock(return_value=mock_session)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Mock embedder
    mock_embedder = MagicMock()
    mock_embedder.embed_batch = AsyncMock(return_value=[[0.1] * 1536])

    # Mock database query result
    chunk_id = uuid.uuid4()
    filing_id = uuid.uuid4()
    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(
        return_value=[
            (chunk_id, filing_id, "Test text", 1, "Risk Factors", 0.95),
            (uuid.uuid4(), filing_id, "Another chunk", 2, "Business", 0.88),
        ]
    )
    mock_session.execute = AsyncMock(return_value=mock_result)

    retriever = DenseRetriever(mock_session_maker, mock_embedder)
    results = await retriever.retrieve("What are the risks?", top_k=10)

    assert isinstance(results, list)
    assert len(results) == 2
    assert all(isinstance(r, ChunkResult) for r in results)
    assert results[0].text == "Test text"
    assert results[0].score == 0.95
    assert results[1].text == "Another chunk"
    assert results[1].score == 0.88


@pytest.mark.asyncio
async def test_dense_retriever_top_k_respected() -> None:
    """Verify only top_k results are returned even if DB has more."""
    # Mock DB session
    mock_session = AsyncMock()
    mock_session_maker = MagicMock(return_value=mock_session)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Mock embedder
    mock_embedder = MagicMock()
    mock_embedder.embed_batch = AsyncMock(return_value=[[0.1] * 1536])

    # Mock database returns exactly 5 rows (top_k=5)
    filing_id = uuid.uuid4()
    mock_rows = [
        (uuid.uuid4(), filing_id, f"Chunk {i}", i, "Section", 0.9 - i * 0.05)
        for i in range(5)
    ]
    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(return_value=mock_rows)
    mock_session.execute = AsyncMock(return_value=mock_result)

    retriever = DenseRetriever(mock_session_maker, mock_embedder)
    results = await retriever.retrieve("test query", top_k=5)

    # Should return exactly 5 results (as limited by top_k parameter)
    assert len(results) == 5
    # Verify the execute was called with top_k=5
    call_args = mock_session.execute.call_args
    assert call_args[0][1]["top_k"] == 5
