"""Unit tests for the section-aware recursive chunker (author-owned Prompt 3)."""
from __future__ import annotations
import pytest
from app.ingest.chunker import MAX_CHUNK_SIZE, CHUNK_OVERLAP, chunk, Chunk


def test_chunk_empty_text_returns_empty_list() -> None:
    """Empty or whitespace-only input must return []."""
    assert chunk("", 1, None) == []
    assert chunk("   \n\n  ", 1, None) == []


def test_chunk_short_text_returns_single_chunk() -> None:
    """Text shorter than MAX_CHUNK_SIZE should produce exactly one chunk."""
    text = "Apple faces supply chain risks."
    result = chunk(text, page_number=3, section="Risk Factors")
    assert len(result) == 1
    assert result[0].text == text
    assert result[0].page_number == 3
    assert result[0].section == "Risk Factors"
    assert result[0].char_start == 0


def test_chunk_respects_max_size() -> None:
    """No chunk may exceed MAX_CHUNK_SIZE characters."""
    # Build a long text with no easy paragraph breaks
    long_text = "Apple reported revenue growth. " * 60  # ~1860 chars
    result = chunk(long_text, page_number=1, section="MD&A")
    assert len(result) > 1
    for c in result:
        assert len(c.text) <= MAX_CHUNK_SIZE, (
            f"Chunk exceeded {MAX_CHUNK_SIZE} chars: {len(c.text)}"
        )


def test_chunk_overlap_between_adjacent_chunks() -> None:
    """Adjacent chunks must share at least some overlapping text
    (up to CHUNK_OVERLAP chars from the end of chunk N appearing
    at the start of chunk N+1).
    """
    long_text = "Revenue grew twelve percent year over year. " * 40  # ~1760 chars
    result = chunk(long_text, page_number=2, section="Financial Statements")
    assert len(result) >= 2
    for i in range(len(result) - 1):
        tail = result[i].text[-CHUNK_OVERLAP:]
        head = result[i + 1].text
        assert head.startswith(tail) or tail in head, (
            f"No overlap between chunk {i} and chunk {i+1}.\n"
            f"Tail: {tail!r}\nHead start: {head[:CHUNK_OVERLAP]!r}"
        )


def test_chunk_metadata_propagates() -> None:
    """Every chunk must carry the page_number and section from its source page."""
    text = "The Company designs and manufactures hardware. " * 30  # ~1410 chars
    result = chunk(text, page_number=7, section="Business")
    assert len(result) > 1
    for c in result:
        assert c.page_number == 7
        assert c.section == "Business"
