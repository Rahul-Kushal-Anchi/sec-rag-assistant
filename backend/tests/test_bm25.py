"""Unit tests for BM25 sparse retrieval."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.retrieval.bm25 import BM25Retriever
from app.retrieval.dense import ChunkResult


def test_bm25_retrieve_raises_if_not_built() -> None:
    """Verify RuntimeError raised if retrieve() called before build_index()."""
    mock_session_maker = MagicMock()
    retriever = BM25Retriever(mock_session_maker)

    with pytest.raises(RuntimeError, match="BM25 index not built"):
        retriever.retrieve("test query")


@pytest.mark.asyncio
async def test_bm25_retrieve_returns_chunk_results() -> None:
    """Build index from 3 synthetic chunks, verify retrieve() returns ChunkResult list."""
    # Mock DB session
    mock_session = AsyncMock()
    mock_session_maker = MagicMock(return_value=mock_session)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Mock database query result with 3 chunks
    filing_id = uuid.uuid4()
    chunk1_id = uuid.uuid4()
    chunk2_id = uuid.uuid4()
    chunk3_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(
        return_value=[
            (chunk1_id, filing_id, "Apple faces supply chain risks", 1, "Risk Factors"),
            (chunk2_id, filing_id, "Revenue grew significantly last year", 2, "MD&A"),
            (chunk3_id, filing_id, "The company designs hardware products", 3, "Business"),
        ]
    )
    mock_session.execute = AsyncMock(return_value=mock_result)

    retriever = BM25Retriever(mock_session_maker)
    await retriever.build_index()

    results = retriever.retrieve("supply chain", top_k=10)

    assert isinstance(results, list)
    assert len(results) == 3
    assert all(isinstance(r, ChunkResult) for r in results)
    # First result should be the chunk about supply chain
    assert "supply" in results[0].text.lower()
    assert "chain" in results[0].text.lower()


@pytest.mark.asyncio
async def test_bm25_scores_normalized_0_to_1() -> None:
    """Verify all scores in [0, 1] range."""
    # Mock DB session
    mock_session = AsyncMock()
    mock_session_maker = MagicMock(return_value=mock_session)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Mock database query result
    filing_id = uuid.uuid4()
    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(
        return_value=[
            (uuid.uuid4(), filing_id, "Apple reported strong revenue growth", 1, "MD&A"),
            (uuid.uuid4(), filing_id, "The company faces regulatory challenges", 2, "Risk"),
            (uuid.uuid4(), filing_id, "Revenue increased by twenty percent", 3, "MD&A"),
        ]
    )
    mock_session.execute = AsyncMock(return_value=mock_result)

    retriever = BM25Retriever(mock_session_maker)
    await retriever.build_index()

    results = retriever.retrieve("revenue growth", top_k=10)

    # All scores should be in [0, 1] range
    for result in results:
        assert 0.0 <= result.score <= 1.0, f"Score {result.score} out of range [0, 1]"

    # Top result should have highest score (close to 1.0 after normalization)
    assert results[0].score >= results[-1].score


@pytest.mark.asyncio
async def test_bm25_top_k_respected() -> None:
    """Verify only top_k results returned."""
    # Mock DB session
    mock_session = AsyncMock()
    mock_session_maker = MagicMock(return_value=mock_session)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Mock database with 10 chunks
    filing_id = uuid.uuid4()
    mock_rows = [
        (uuid.uuid4(), filing_id, f"Chunk number {i} with some text", i, "Section")
        for i in range(10)
    ]
    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(return_value=mock_rows)
    mock_session.execute = AsyncMock(return_value=mock_result)

    retriever = BM25Retriever(mock_session_maker)
    await retriever.build_index()

    # Request only top 3
    results = retriever.retrieve("chunk text", top_k=3)

    assert len(results) == 3


@pytest.mark.asyncio
async def test_bm25_keyword_relevance() -> None:
    """Index 3 chunks where only one mentions 'revenue', query 'revenue growth',
    verify that chunk scores highest.
    """
    # Mock DB session
    mock_session = AsyncMock()
    mock_session_maker = MagicMock(return_value=mock_session)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Mock database with 3 chunks - only one mentions "revenue"
    filing_id = uuid.uuid4()
    chunk1_id = uuid.uuid4()
    chunk2_id = uuid.uuid4()
    chunk3_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(
        return_value=[
            (chunk1_id, filing_id, "The company designs innovative products", 1, "Business"),
            (chunk2_id, filing_id, "Revenue grew by fifteen percent this quarter", 2, "MD&A"),
            (chunk3_id, filing_id, "Supply chain risks remain significant", 3, "Risk"),
        ]
    )
    mock_session.execute = AsyncMock(return_value=mock_result)

    retriever = BM25Retriever(mock_session_maker)
    await retriever.build_index()

    results = retriever.retrieve("revenue growth", top_k=3)

    # The chunk about revenue should score highest
    assert "revenue" in results[0].text.lower()
    assert results[0].chunk_id == chunk2_id
    # It should have the highest score
    assert results[0].score >= results[1].score
    assert results[0].score >= results[2].score
