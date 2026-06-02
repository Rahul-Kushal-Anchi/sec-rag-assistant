"""Chunking strategy for SEC filings (AUTHOR-OWNED: design decision lives in DECISIONS.md D2)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    """A single chunk of text extracted from a filing page."""

    text: str
    page_number: int
    section: str | None
    char_start: int


def chunk(text: str, page_number: int, section: str | None) -> list[Chunk]:
    """Split a page of text into retrievable chunks (AUTHOR-OWNED stub).

    This function is intentionally left as a stub. The author will implement
    the real chunking strategy in Prompt 3.

    Args:
        text: Clean page text.
        page_number: Page number in the filing.
        section: Section name (e.g., "Risk Factors") or None.

    Returns:
        Empty list (stub behavior). Real implementation will return list of Chunks.
    """
    # TODO: rahul will implement this in author-owned step. See CURSOR_BUILD_GUIDE.md prompts 3, 6, 9.
    return []
