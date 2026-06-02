"""End-to-end ingestion pipeline: parse → chunk → embed → persist."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tqdm import tqdm

from app.config import settings
from app.db.models import Chunk as ChunkORM
from app.db.models import Filing
from app.db.session import SessionLocal
from app.ingest import chunker
from app.ingest.embedder import OpenAIEmbedder
from app.ingest.html_parser import parse_filing
from app.logging_config import get_logger

logger = get_logger(__name__)


class IngestionPipeline:
    """Orchestrates parsing, chunking, embedding, and database persistence."""

    def __init__(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        embedder: OpenAIEmbedder,
    ) -> None:
        """Initialize the ingestion pipeline.

        Args:
            db_session_maker: Async session factory for database access.
            embedder: OpenAI embedding client.
        """
        self.db_session_maker = db_session_maker
        self.embedder = embedder
        self.log = logger

    async def ingest_filing(self, file_path: Path) -> int:
        """Parse, chunk, embed, and persist a single SEC filing.

        Args:
            file_path: Path to the full-submission.txt file.

        Returns:
            Number of chunks inserted (0 if filing already exists or no chunks produced).

        Raises:
            Exception: If parsing or database operations fail.
        """
        log = self.log.bind(file_path=str(file_path))

        # Parse the filing
        try:
            parsed = parse_filing(file_path)
        except Exception as exc:
            log.error("parse_failed", error=str(exc))
            raise

        log = log.bind(
            ticker=parsed.ticker,
            accession_number=parsed.accession_number,
            form_type=parsed.form_type,
        )

        # Open DB session and transaction
        async with self.db_session_maker() as session:
            # Check idempotency: skip if filing already exists
            stmt = select(Filing).where(Filing.accession_number == parsed.accession_number)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                log.info("filing_already_exists", filing_id=str(existing.id))
                return 0

            # Insert Filing row
            filing_orm = Filing(
                ticker=parsed.ticker,
                form_type=parsed.form_type,
                filing_date=parsed.filing_date,
                accession_number=parsed.accession_number,
                source_url=parsed.source_url,
            )
            session.add(filing_orm)
            await session.flush()  # Get the UUID

            log = log.bind(filing_id=str(filing_orm.id))

            # Chunk all pages
            all_chunks: list[chunker.Chunk] = []
            for page in parsed.pages:
                page_chunks = chunker.chunk(page.text, page.page_number, page.section)
                all_chunks.extend(page_chunks)

            if not all_chunks:
                log.warning(
                    "no_chunks_produced",
                    message=(
                        "Chunker returned empty list — likely author-owned stub not yet "
                        "implemented. Filing metadata persisted but no chunks inserted."
                    ),
                )
                await session.commit()
                return 0

            # Extract texts for embedding
            chunk_texts = [c.text for c in all_chunks]

            # Embed in batches
            log.info("embedding_chunks", chunk_count=len(chunk_texts))
            try:
                embeddings = await self.embedder.embed_in_batches(chunk_texts, batch_size=100)
            except Exception as exc:
                log.error("embedding_failed", error=str(exc))
                raise

            # Build Chunk ORM objects
            chunk_orms = [
                ChunkORM(
                    filing_id=filing_orm.id,
                    text=c.text,
                    page_number=c.page_number,
                    section=c.section,
                    embedding=emb,
                    metadata_json={"char_start": c.char_start},
                )
                for c, emb in zip(all_chunks, embeddings, strict=True)
            ]

            # Bulk insert
            session.add_all(chunk_orms)
            await session.commit()

            log.info(
                "filing_ingested",
                chunks_inserted=len(chunk_orms),
            )

            return len(chunk_orms)

    async def ingest_directory(self, root_dir: Path) -> dict[str, Any]:
        """Ingest all filings in a directory tree.

        Args:
            root_dir: Root directory containing TICKER/FORM_TYPE/ACCESSION/full-submission.txt files.

        Returns:
            Summary dict with keys: filings_processed, chunks_inserted, skipped, errors.
        """
        log = self.log.bind(root_dir=str(root_dir))

        if not root_dir.exists():
            raise ValueError(f"Directory not found: {root_dir}")

        # Find all full-submission.txt files
        filing_paths = list(root_dir.rglob("full-submission.txt"))
        log.info("discovered_filings", count=len(filing_paths))

        if not filing_paths:
            log.warning("no_filings_found")
            return {
                "filings_processed": 0,
                "chunks_inserted": 0,
                "skipped": 0,
                "errors": [],
            }

        filings_processed = 0
        chunks_inserted = 0
        skipped = 0
        errors: list[str] = []

        for file_path in tqdm(filing_paths, desc="Ingesting filings", unit="filing"):
            try:
                chunk_count = await self.ingest_filing(file_path)
                if chunk_count == 0:
                    skipped += 1
                else:
                    filings_processed += 1
                    chunks_inserted += chunk_count
            except Exception as exc:
                error_msg = f"{file_path}: {type(exc).__name__}: {exc}"
                errors.append(error_msg)
                log.error("ingestion_error", file_path=str(file_path), error=str(exc))

        log.info(
            "ingestion_complete",
            filings_processed=filings_processed,
            chunks_inserted=chunks_inserted,
            skipped=skipped,
            errors_count=len(errors),
        )

        return {
            "filings_processed": filings_processed,
            "chunks_inserted": chunks_inserted,
            "skipped": skipped,
            "errors": errors,
        }


async def main() -> None:
    """CLI entry point for ingesting a directory of SEC filings."""
    parser = argparse.ArgumentParser(description="Ingest SEC filings into the database.")
    parser.add_argument(
        "root_dir",
        type=Path,
        help="Root directory containing TICKER/FORM_TYPE/ACCESSION/full-submission.txt files",
    )
    args = parser.parse_args()

    # Initialize components
    embedder = OpenAIEmbedder(api_key=settings.OPENAI_API_KEY, model=settings.EMBEDDING_MODEL)
    pipeline = IngestionPipeline(db_session_maker=SessionLocal, embedder=embedder)

    # Run ingestion
    summary = await pipeline.ingest_directory(args.root_dir)

    # Print summary
    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    print(f"Filings processed: {summary['filings_processed']}")
    print(f"Chunks inserted:   {summary['chunks_inserted']}")
    print(f"Skipped (already exist or no chunks): {summary['skipped']}")
    print(f"Errors:            {len(summary['errors'])}")

    if summary["errors"]:
        print("\nErrors:")
        for error in summary["errors"][:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(summary["errors"]) > 10:
            print(f"  ... and {len(summary['errors']) - 10} more")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
