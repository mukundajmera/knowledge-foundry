"""Knowledge Foundry — Embedding Service.

Generates embeddings via OpenAI text-embedding-3-large with Redis-backed
caching. Supports batch embedding for ingestion and single-query embedding.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import openai

from src.core.config import OpenAISettings, RedisSettings, get_settings
from src.core.exceptions import EmbeddingError
from src.core.interfaces import EmbeddingProvider

logger = logging.getLogger(__name__)


class EmbeddingService(EmbeddingProvider):
    """OpenAI embedding provider with Redis caching.

    Uses text-embedding-3-large (3072 dims) as default.
    Caches embeddings in Redis with infinite TTL (deterministic output).
    """

    def __init__(
        self,
        openai_client: openai.AsyncOpenAI | None = None,
        redis_client: Any | None = None,
        openai_settings: OpenAISettings | None = None,
        redis_settings: RedisSettings | None = None,
    ) -> None:
        settings = get_settings()
        self._openai_settings = openai_settings or settings.openai
        self._redis_settings = redis_settings or settings.redis
        
        self._mock_mode = False
        if not self._openai_settings.api_key:
            logger.warning("No OpenAI API key found. Using MOCK embeddings.")
            self._mock_mode = True
            # Initialize with dummy key to prevent client init error, though we won't use it
            self._client = openai.AsyncOpenAI(api_key="mock-key")
        else:
            self._client = openai_client or openai.AsyncOpenAI(
                api_key=self._openai_settings.api_key,
            )
            
        self._redis = redis_client  # Optional — gracefully degrades without cache
        self._model = self._openai_settings.embedding_model
        self._dimensions = self._openai_settings.embedding_dimensions

    def _cache_key(self, text: str) -> str:
        """Generate a deterministic cache key for a text."""
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{self._redis_settings.key_prefix}emb:{text_hash}"

    async def _get_cached(self, text: str) -> list[float] | None:
        """Try to get a cached embedding."""
        if not self._redis:
            return None
        try:
            key = self._cache_key(text)
            cached = await self._redis.get(key)
            if cached:
                return json.loads(cached)
        except Exception as exc:
            logger.warning("Cache read failed: %s", exc)
        return None

    async def _set_cached(self, text: str, embedding: list[float]) -> None:
        """Cache an embedding (infinite TTL — deterministic output)."""
        if not self._redis:
            return
        try:
            key = self._cache_key(text)
            await self._redis.set(key, json.dumps(embedding))
        except Exception as exc:
            logger.warning("Cache write failed: %s", exc)

    async def embed_query(self, text: str) -> list[float]:
        """Generate embedding for a single query text.

        Checks cache first, falls back to API call.

        Args:
            text: The query text to embed.

        Returns:
            Embedding vector (3072-dim by default).

        Raises:
            EmbeddingError: If embedding generation fails.
        """
        # Check cache
        cached = await self._get_cached(text)
        if cached:
            logger.debug("Embedding cache hit for query")
            return cached

        # Mock mode fallback
        if self._mock_mode:
            logger.info("Generating MOCK embedding for query")
            # Deterministic pseudo-random vector based on text length
            # to allow some basic similarity testing if needed
            seed = len(text)
            mock_embedding = [(i + seed) % 100 / 100.0 for i in range(self._dimensions)]
            # Normalize? Not strictly needed for mock
            return mock_embedding

        # Generate via API
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=text,
                dimensions=self._dimensions,
            )
            embedding = response.data[0].embedding

            # Cache the result
            await self._set_cached(text, embedding)
            return embedding
        except openai.RateLimitError as exc:
            raise EmbeddingError(
                f"OpenAI embedding rate limit exceeded: {exc}",
                details={"model": self._model},
            ) from exc
        except Exception as exc:
            raise EmbeddingError(
                f"Embedding generation failed: {exc}",
                details={"model": self._model},
            ) from exc

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Checks cache for each text individually, then batch-calls the API
        for uncached texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors (same order as input).

        Raises:
            EmbeddingError: If embedding generation fails.
        """
        if not texts:
            return []
            
        # Mock mode fallback for batch
        if self._mock_mode:
            logger.info("Generating MOCK embeddings for batch of %d texts", len(texts))
            results = []
            for text in texts:
                seed = len(text)
                results.append([(i + seed) % 100 / 100.0 for i in range(self._dimensions)])
            return results

        results: list[list[float] | None] = [None] * len(texts)
        uncached_indices: list[int] = []

        # Check cache for each text
        for i, text in enumerate(texts):
            cached = await self._get_cached(text)
            if cached:
                results[i] = cached
            else:
                uncached_indices.append(i)

        if not uncached_indices:
            logger.debug("All %d embeddings served from cache", len(texts))
            return [r for r in results if r is not None]  # type: ignore[misc]

        # Batch call for uncached texts
        uncached_texts = [texts[i] for i in uncached_indices]
        try:
            # OpenAI supports up to 2048 texts per batch
            batch_size = 100
            for batch_start in range(0, len(uncached_texts), batch_size):
                batch = uncached_texts[batch_start : batch_start + batch_size]
                response = await self._client.embeddings.create(
                    model=self._model,
                    input=batch,
                    dimensions=self._dimensions,
                )

                for j, emb_data in enumerate(response.data):
                    global_idx = uncached_indices[batch_start + j]
                    embedding = emb_data.embedding
                    results[global_idx] = embedding
                    # Cache each result
                    await self._set_cached(texts[global_idx], embedding)

            logger.info(
                "Generated %d embeddings (%d cached, %d new)",
                len(texts),
                len(texts) - len(uncached_indices),
                len(uncached_indices),
            )

        except openai.RateLimitError as exc:
            raise EmbeddingError(
                f"OpenAI embedding rate limit exceeded: {exc}",
                details={"model": self._model, "batch_size": len(uncached_texts)},
            ) from exc
        except Exception as exc:
            raise EmbeddingError(
                f"Batch embedding generation failed: {exc}",
                details={"model": self._model, "batch_size": len(uncached_texts)},
            ) from exc

        return [r for r in results if r is not None]  # type: ignore[misc]
