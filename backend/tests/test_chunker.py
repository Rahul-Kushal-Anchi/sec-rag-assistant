"""Tests for the chunking strategy (author will fill in once chunker.py lands)."""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="chunker not yet implemented; author-owned file")
def test_chunker_respects_section_boundaries() -> None:
    """Chunks must never straddle SEC 10-K section boundaries."""
    # TODO: import from app.ingest.chunker and assert on real fixture text.
    assert False


@pytest.mark.skip(reason="chunker not yet implemented; author-owned file")
def test_chunker_overlap_within_bounds() -> None:
    """Consecutive chunks share the configured overlap and nothing more."""
    # TODO: validate overlap window and max chunk size.
    assert False
