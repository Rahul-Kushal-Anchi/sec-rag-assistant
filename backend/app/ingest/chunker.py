"""Section-aware recursive chunker for SEC filings.

Splits page text into ~800-char chunks with ~150-char overlap, preferring
paragraph boundaries over sentence boundaries over word boundaries.

Design decisions documented in DECISIONS.md D2:
- 800 char target (~200 tokens for text-embedding-3-small)
- 150 char overlap (~18%) preserves cross-boundary context
- Recursive separator hierarchy (paragraph -> sentence -> word -> char)
  mirrors human reading units
"""
from __future__ import annotations
from dataclasses import dataclass

MAX_CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
SEPARATORS = ["\n\n", "\n", ". ", " "]


@dataclass
class Chunk:
    """A single chunk of text extracted from a filing page."""
    text: str
    page_number: int
    section: str | None
    char_start: int


def chunk(text: str, page_number: int, section: str | None) -> list[Chunk]:
    """Split a page of text into overlapping chunks.

    Strategy: recursively try separators from coarsest (paragraph break)
    to finest (single space), splitting at the highest-level separator
    that produces chunks <= MAX_CHUNK_SIZE. Adds CHUNK_OVERLAP chars
    of overlap between adjacent chunks for context continuity.

    Empty or whitespace-only input returns an empty list.
    """
    if not text or not text.strip():
        return []

    pieces = _recursive_split(text, MAX_CHUNK_SIZE)
    return _merge_with_overlap(pieces, page_number, section)


def _recursive_split(
    text: str,
    max_size: int,
    separators: list[str] | None = None,
) -> list[str]:
    """Split text into pieces no larger than max_size.

    Tries each separator in priority order. Re-attaches separators to
    preserve punctuation. Recursively splits oversized pieces with the
    NEXT finer separator (never re-tries the same separator). Hard-splits
    at character if no separator remains.
    """
    if separators is None:
        separators = SEPARATORS

    if len(text) <= max_size:
        return [text]

    for idx, separator in enumerate(separators):
        if separator in text:
            raw_parts = text.split(separator)
            parts: list[str] = []
            for i, part in enumerate(raw_parts):
                if i < len(raw_parts) - 1:
                    parts.append(part + separator)
                else:
                    parts.append(part)
            result: list[str] = []
            remaining_separators = separators[idx + 1:]
            for part in parts:
                if not part:
                    continue
                if len(part) <= max_size:
                    result.append(part)
                else:
                    result.extend(_recursive_split(part, max_size, remaining_separators))
            return result

    return [
        text[i:i + max_size]
        for i in range(0, len(text), max_size)
    ]


def _merge_with_overlap(
    pieces: list[str],
    page_number: int,
    section: str | None,
) -> list[Chunk]:
    """Combine small pieces into chunks of ~MAX_CHUNK_SIZE with
    CHUNK_OVERLAP chars of overlap between adjacent chunks.

    Tracks char_start (offset in original text) for each chunk.
    """
    chunks: list[Chunk] = []
    current_text = ""
    current_start = 0
    position = 0

    for piece in pieces:
        if not piece:
            continue

        candidate = current_text + piece
        if len(candidate) <= MAX_CHUNK_SIZE:
            current_text = candidate
        else:
            if current_text:
                chunks.append(
                    Chunk(
                        text=current_text,
                        page_number=page_number,
                        section=section,
                        char_start=current_start,
                    )
                )
                overlap_text = current_text[-CHUNK_OVERLAP:]
                current_start = max(0, position - len(overlap_text))
                candidate_with_overlap = overlap_text + piece
                # Edge case: if overlap + piece exceeds max (only triggers
                # on hard-split fallback output), drop overlap to stay bounded.
                if len(candidate_with_overlap) > MAX_CHUNK_SIZE:
                    current_text = piece
                    current_start = position
                else:
                    current_text = candidate_with_overlap
            else:
                # Safety fallback: piece alone exceeds max. Should be rare
                # since _recursive_split guarantees piece <= max_size.
                chunks.append(
                    Chunk(
                        text=piece,
                        page_number=page_number,
                        section=section,
                        char_start=position,
                    )
                )
                current_text = ""
                current_start = position + len(piece)

        position += len(piece)

    if current_text:
        chunks.append(
            Chunk(
                text=current_text,
                page_number=page_number,
                section=section,
                char_start=current_start,
            )
        )

    return chunks