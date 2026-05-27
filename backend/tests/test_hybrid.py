"""Tests for hybrid retrieval scoring (author will fill in once hybrid.py lands)."""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="hybrid retrieval not yet implemented; author-owned file")
def test_hybrid_rrf_combines_two_rankings() -> None:
    """Reciprocal-rank-fusion must merge two rankings into a single sorted list."""
    # TODO: instantiate scorer, feed two ranked lists, assert fused order.
    assert False


@pytest.mark.skip(reason="hybrid retrieval not yet implemented; author-owned file")
def test_hybrid_handles_empty_sparse_results() -> None:
    """Hybrid scorer must not crash if BM25 returns no hits."""
    # TODO: assert graceful fallback to dense-only ranking.
    assert False
