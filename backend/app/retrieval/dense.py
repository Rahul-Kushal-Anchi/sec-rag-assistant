"""Dense vector retrieval using pgvector for SEC filing chunks."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.ingest.embedder import OpenAIEmbedder

logger = structlog.get_logger().bind(retriever="dense")


@dataclass
class ChunkResult:
    """A single chunk retrieved from the vector database."""

    chunk_id: uuid.UUID
    filing_id: uuid.UUID
    text: str
    page_number: int
    section: str | None
    score: float  # cosine similarity 0-1


class DenseRetriever:
    """Retrieve chunks using pgvector cosine similarity on OpenAI embeddings.

    Uses HNSW index for fast approximate nearest neighbor search.
    """

    def __init__(
        self,
        db_session_maker: async_sessionmaker,
        embedder: OpenAIEmbedder,
    ) -> None:
        """Initialize the dense retriever.

        Args:
            db_session_maker: SQLAlchemy async session factory
            embedder: OpenAI embedder for query encoding
        """
        self.db_session_maker = db_session_maker
        self.embedder = embedder
        logger.info("dense_retriever_initialized")

    async def create_index(self) -> None:
        """Create HNSW index on chunks.embedding for fast cosine similarity search.

        Uses pgvector's HNSW index with parameters:
        - m=16: max connections per layer (balance between speed and accuracy)
        - ef_construction=64: build-time search depth

        This is safe to call multiple times (IF NOT EXISTS).
        """
        create_index_sql = text("""
            CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
            ON chunks USING hnsw (embedding vector_cosine_ops)
            WITH (m=16, ef_construction=64)
        """)

        async with self.db_session_maker() as session:
            await session.execute(create_index_sql)
            await session.commit()
            logger.info("hnsw_index_created", index="chunks_embedding_hnsw_idx")

    async def retrieve(self, query: str, top_k: int = 10) -> list[ChunkResult]:
        """Retrieve top-k most similar chunks to the query using cosine similarity.

        Args:
            query: User's natural language question
            top_k: Number of chunks to retrieve (default 10)

        Returns:
            List of ChunkResult sorted by descending similarity score
        """
        # Embed the query
        query_vectors = await self.embedder.embed_batch([query])
        query_vector = query_vectors[0]

        # Convert Python list to pgvector format: '[1.0, 2.0, ...]'
        vector_str = "[" + ",".join(str(x) for x in query_vector) + "]"

        # Query using pgvector's <=> operator (cosine distance)
        # Score = 1 - distance, so higher score = more similar
        similarity_query = text("""
            SELECT
                id,
                filing_id,
                text,
                page_number,
                section,
                1 - (embedding <=> :query_vector::vector) AS score
            FROM chunks
            ORDER BY embedding <=> :query_vector::vector
            LIMIT :top_k
        """)

        async with self.db_session_maker() as session:
            result = await session.execute(
                similarity_query,
                {"query_vector": vector_str, "top_k": top_k},
            )
            rows = result.fetchall()

        chunks = [
            ChunkResult(
                chunk_id=row[0],
                filing_id=row[1],
                text=row[2],
                page_number=row[3],
                section=row[4],
                score=float(row[5]),
            )
            for row in rows
        ]

        logger.info("dense_retrieval_complete", query_len=len(query), chunks_found=len(chunks), top_k=top_k)
        return chunks
