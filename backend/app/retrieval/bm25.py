"""BM25 sparse keyword-based retrieval for SEC filing chunks."""

from __future__ import annotations

from typing import Any

import structlog
from rank_bm25 import BM25Okapi
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Chunk as ChunkORM
from app.db.models import Filing
from app.retrieval.dense import ChunkResult

logger = structlog.get_logger().bind(retriever="bm25")


class BM25Retriever:
    """Retrieve chunks using BM25 keyword scoring.

    Builds an in-memory BM25 index from the chunks table. The index is
    rebuilt whenever build_index() is called (e.g., on startup or after
    ingestion).
    """

    def __init__(self, db_session_maker: async_sessionmaker) -> None:
        """Initialize the BM25 retriever.

        Args:
            db_session_maker: SQLAlchemy async session factory
        """
        self.db_session_maker = db_session_maker
        self._index: BM25Okapi | None = None
        self._chunks: list[dict[str, Any]] = []
        logger.info("bm25_retriever_initialized")

    async def build_index(self, ticker: str | None = None) -> int:
        """Build BM25 index from chunks in the database.

        Args:
            ticker: Optional ticker filter (e.g., "AAPL"). If provided, only
                   indexes chunks from filings with that ticker.

        Returns:
            Count of chunks indexed
        """
        async with self.db_session_maker() as session:
            if ticker:
                # Filter by ticker via JOIN
                query = (
                    select(
                        ChunkORM.id,
                        ChunkORM.filing_id,
                        ChunkORM.text,
                        ChunkORM.page_number,
                        ChunkORM.section,
                    )
                    .join(Filing, ChunkORM.filing_id == Filing.id)
                    .where(Filing.ticker == ticker)
                )
            else:
                # Load all chunks
                query = select(
                    ChunkORM.id,
                    ChunkORM.filing_id,
                    ChunkORM.text,
                    ChunkORM.page_number,
                    ChunkORM.section,
                )

            result = await session.execute(query)
            rows = result.fetchall()

        # Clear previous index and chunks
        self._chunks = []
        corpus: list[list[str]] = []

        for row in rows:
            chunk_data = {
                "chunk_id": row[0],
                "filing_id": row[1],
                "text": row[2],
                "page_number": row[3],
                "section": row[4],
            }
            self._chunks.append(chunk_data)

            # Tokenize: lowercase and split on whitespace
            tokenized = row[2].lower().split()
            corpus.append(tokenized)

        if not corpus:
            logger.warning("bm25_index_empty", ticker=ticker)
            self._index = None
            return 0

        # Build BM25 index
        self._index = BM25Okapi(corpus)

        logger.info("bm25_index_built", chunks_count=len(corpus), ticker=ticker)
        return len(corpus)

    def retrieve(self, query: str, top_k: int = 10) -> list[ChunkResult]:
        """Retrieve top-k chunks by BM25 keyword relevance.

        Args:
            query: User's natural language question
            top_k: Number of chunks to retrieve (default 10)

        Returns:
            List of ChunkResult sorted by descending BM25 score

        Raises:
            RuntimeError: If index has not been built yet
        """
        if self._index is None:
            raise RuntimeError("BM25 index not built. Call build_index() first.")

        # Tokenize query the same way as corpus
        tokenized_query = query.lower().split()

        # Get BM25 scores for all documents
        scores = self._index.get_scores(tokenized_query)

        # Normalize scores to 0-1 range
        max_score = max(scores) if len(scores) > 0 and max(scores) > 0 else 1.0
        normalized_scores = [s / max_score for s in scores]

        # Pair chunks with scores
        chunk_score_pairs = list(zip(self._chunks, normalized_scores))

        # Sort by descending score
        chunk_score_pairs.sort(key=lambda x: x[1], reverse=True)

        # Take top-k
        top_pairs = chunk_score_pairs[:top_k]

        # Build ChunkResult objects
        results = [
            ChunkResult(
                chunk_id=chunk["chunk_id"],
                filing_id=chunk["filing_id"],
                text=chunk["text"],
                page_number=chunk["page_number"],
                section=chunk["section"],
                score=score,
            )
            for chunk, score in top_pairs
        ]

        logger.info("bm25_retrieval_complete", query_len=len(query), chunks_found=len(results), top_k=top_k)
        return results
