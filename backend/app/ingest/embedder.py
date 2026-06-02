"""OpenAI embedding client with batching and retry logic."""

from __future__ import annotations

import openai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.logging_config import get_logger

logger = get_logger(__name__)


class OpenAIEmbedder:
    """Async embedding client for OpenAI text-embedding-3-small."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        """Initialize the embedder with API credentials.

        Args:
            api_key: OpenAI API key.
            model: Embedding model name (default: text-embedding-3-small).
        """
        self.model = model
        self.client = openai.AsyncClient(api_key=api_key)
        self.log = logger.bind(model=model)

    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts using OpenAI embeddings API.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of 1536-dimensional embedding vectors.

        Raises:
            openai.RateLimitError: If rate limit exceeded after retries.
            openai.APIStatusError: If API returns error status after retries.
        """
        if not texts:
            return []

        self.log.debug("embedding_batch", batch_size=len(texts))

        try:
            response = await self.client.embeddings.create(input=texts, model=self.model)
            embeddings = [item.embedding for item in response.data]
            return embeddings
        except (openai.RateLimitError, openai.APIStatusError) as exc:
            self.log.warning(
                "embedding_api_error",
                error_type=type(exc).__name__,
                error_msg=str(exc),
            )
            raise

    async def embed_in_batches(
        self, texts: list[str], batch_size: int = 100
    ) -> list[list[float]]:
        """Embed a large list of texts in batches.

        Args:
            texts: List of text strings to embed.
            batch_size: Number of texts per API call (default: 100).

        Returns:
            List of 1536-dimensional embedding vectors (same order as input).
        """
        if not texts:
            return []

        self.log.info("embedding_in_batches", total_texts=len(texts), batch_size=batch_size)

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = await self.embed_batch(batch)
            all_embeddings.extend(batch_embeddings)

            self.log.debug(
                "batch_embedded",
                batch_start=i,
                batch_end=min(i + batch_size, len(texts)),
                total=len(texts),
            )

        self.log.info("embedding_complete", total_embeddings=len(all_embeddings))
        return all_embeddings
