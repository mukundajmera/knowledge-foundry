"""Knowledge Foundry — L2 Embedding Cache.

Caches embedding vectors to avoid redundant calls to the embedding model.
Uses the same ResponseCache infrastructure as L1/L3 but with persistent TTL.

L2 sits between L1 (response) and L3 (retrieval) in the cache hierarchy:
  L1: Full RAG responses → 5-min TTL
  L2: Embedding vectors  → persistent (same text = same embedding)
  L3: Retrieval results  → 2-min TTL
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from src.cache.response_cache import CacheStats, ResponseCache

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """Cache for embedding vectors.

    Since embeddings are deterministic for a given model + text,
    they can be cached aggressively with long TTL (24h default).
    This avoids redundant API calls and reduces latency + cost.
    """

    def __init__(
        self,
        *,
        ttl_seconds: float = 86_400.0,  # 24 hours
        max_entries: int = 50_000,
    ) -> None:
        self._cache = ResponseCache(
            default_ttl_seconds=ttl_seconds,
            max_entries=max_entries,
        )

    @staticmethod
    def make_key(text: str, model: str = "default") -> str:
        """Generate cache key from text content and model name."""
        raw = f"emb:{model}:{text}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def get(self, text: str, model: str = "default") -> list[float] | None:
        """Get cached embedding vector for text.

        Args:
            text: The text that was embedded.
            model: Embedding model identifier.

        Returns:
            Cached embedding vector or None on miss.
        """
        key = self.make_key(text, model)
        result = await self._cache.get(key)
        if result is not None:
            logger.debug("Embedding cache HIT: key=%s...", key[:12])
        return result

    async def set(
        self, text: str, embedding: list[float], model: str = "default",
    ) -> None:
        """Store an embedding vector in cache.

        Args:
            text: The text that was embedded.
            embedding: The embedding vector to cache.
            model: Embedding model identifier.
        """
        key = self.make_key(text, model)
        await self._cache.set(key, embedding)
        logger.debug("Embedding cache SET: key=%s..., dim=%d", key[:12], len(embedding))

    async def invalidate(self, text: str, model: str = "default") -> bool:
        """Remove a cached embedding."""
        key = self.make_key(text, model)
        return await self._cache.invalidate(key)

    async def clear(self) -> None:
        """Clear all cached embeddings."""
        await self._cache.clear()

    @property
    def stats(self) -> CacheStats:
        """Return cache performance statistics."""
        return self._cache.stats

    @property
    def size(self) -> int:
        """Number of cached embeddings."""
        return self._cache.size

    async def health_check(self) -> dict[str, Any]:
        """Return cache health info."""
        health = await self._cache.health_check()
        health["cache_level"] = "L2_embedding"
        return health


def create_embedding_cache() -> EmbeddingCache:
    """Create a pre-configured L2 embedding cache."""
    return EmbeddingCache(ttl_seconds=86_400.0, max_entries=50_000)
