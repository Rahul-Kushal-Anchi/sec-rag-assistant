"""Tests for the answerer orchestrator (author will fill in once answerer.py lands)."""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="answerer not yet implemented; author-owned file")
async def test_answerer_returns_structured_answer(mock_llm_client) -> None:  # type: ignore[no-untyped-def]
    """Answerer must return an Answer pydantic model with citations + confidence."""
    # TODO: wire mock retriever + mock LLM, call answerer, assert schema.
    assert False


@pytest.mark.skip(reason="answerer not yet implemented; author-owned file")
async def test_answerer_low_confidence_routes_to_idk(mock_llm_client) -> None:  # type: ignore[no-untyped-def]
    """If confidence < threshold, answerer must respond 'I don't know'."""
    # TODO: stub low-confidence path.
    assert False
