"""Knowledge Foundry — 3-Level Response & Retrieval Cache.

Provides in-memory cache (Redis-ready interface) for:
  L1: Full RAG responses (query hash → response, TTL 5min)
  L3: Retrieval results  (query hash → search results, TTL 2min)

L2 (embedding cache) already exists in EmbeddingService via Redis.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A single cache entry with TTL."""
    value: Any
    created_at: float
    ttl_seconds: float

    @property
    def is_expired(self) -> bool:
        return (time.monotonic() - self.created_at) > self.ttl_seconds


@dataclass
class CacheStats:
    """Cache performance statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    sets: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class ResponseCache:
    """In-memory cache with TTL eviction.

    Thread-safe for asyncio (single-threaded event loop).
    In production, swap to aioredis for distributed caching.
    """

    def __init__(
        self,
        *,
        default_ttl_seconds: float = 300.0,  # 5 minutes
        max_entries: int = 10_000,
    ) -> None:
        self._store: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl_seconds
        self._max_entries = max_entries
        self._stats = CacheStats()

    @staticmethod
    def make_key(prefix: str, query: str, tenant_id: str, **extra: str) -> str:
        """Generate a deterministic cache key from query parameters."""
        parts = [prefix, tenant_id, query]
        for k in sorted(extra.keys()):
            parts.append(f"{k}={extra[k]}")
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()

    async def get(self, key: str) -> Any | None:
        """Get a cached value by key. Returns None on miss or expiry."""
        entry = self._store.get(key)
        if entry is None:
            self._stats.misses += 1
            return None
        if entry.is_expired:
            del self._store[key]
            self._stats.misses += 1
            self._stats.evictions += 1
            return None
        self._stats.hits += 1
        return entry.value

    async def set(
        self, key: str, value: Any, ttl_seconds: float | None = None,
    ) -> None:
        """Store a value with TTL."""
        # Evict expired entries if at capacity
        if len(self._store) >= self._max_entries:
            self._evict_expired()
        # Still at capacity → evict oldest
        if len(self._store) >= self._max_entries:
            oldest_key = min(self._store, key=lambda k: self._store[k].created_at)
            del self._store[oldest_key]
            self._stats.evictions += 1

        self._store[key] = CacheEntry(
            value=value,
            created_at=time.monotonic(),
            ttl_seconds=ttl_seconds or self._default_ttl,
        )
        self._stats.sets += 1

    async def invalidate(self, key: str) -> bool:
        """Remove a specific key."""
        if key in self._store:
            del self._store[key]
            return True
        return False

    async def invalidate_pattern(self, prefix: str) -> int:
        """Remove all keys matching a prefix."""
        to_remove = [k for k in self._store if k.startswith(prefix)]
        for k in to_remove:
            del self._store[k]
        return len(to_remove)

    async def clear(self) -> None:
        """Clear all entries."""
        self._store.clear()

    @property
    def stats(self) -> CacheStats:
        """Return current cache statistics."""
        return self._stats

    @property
    def size(self) -> int:
        """Number of entries (including possibly expired)."""
        return len(self._store)

    def _evict_expired(self) -> None:
        """Remove all expired entries."""
        expired = [k for k, v in self._store.items() if v.is_expired]
        for k in expired:
            del self._store[k]
            self._stats.evictions += 1

    async def health_check(self) -> dict[str, Any]:
        """Return cache health info."""
        return {
            "status": "ok",
            "entries": self.size,
            "hit_rate": f"{self._stats.hit_rate:.2%}",
            "hits": self._stats.hits,
            "misses": self._stats.misses,
            "evictions": self._stats.evictions,
        }


# ──────────────────────────────────────────────────────────────
# Pre-configured cache instances
# ──────────────────────────────────────────────────────────────

def create_response_cache() -> ResponseCache:
    """L1 Response cache — full RAG responses, 5-minute TTL."""
    return ResponseCache(default_ttl_seconds=300.0, max_entries=5_000)


def create_retrieval_cache() -> ResponseCache:
    """L3 Retrieval cache — vector search results, 2-minute TTL."""
    return ResponseCache(default_ttl_seconds=120.0, max_entries=10_000)
