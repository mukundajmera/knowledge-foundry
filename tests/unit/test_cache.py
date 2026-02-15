"""Tests for Response Cache — src/cache/response_cache.py."""

from __future__ import annotations

import asyncio
import time

import pytest

from src.cache.response_cache import (
    CacheEntry,
    CacheStats,
    ResponseCache,
    create_response_cache,
    create_retrieval_cache,
)


# ──────────────────────────────────────────────────
# CacheEntry
# ──────────────────────────────────────────────────

class TestCacheEntry:
    def test_not_expired(self) -> None:
        entry = CacheEntry(value="data", created_at=time.monotonic(), ttl_seconds=300)
        assert not entry.is_expired

    def test_expired(self) -> None:
        entry = CacheEntry(value="data", created_at=time.monotonic() - 400, ttl_seconds=300)
        assert entry.is_expired


class TestCacheStats:
    def test_hit_rate_zero(self) -> None:
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self) -> None:
        stats = CacheStats(hits=3, misses=7)
        assert stats.hit_rate == pytest.approx(0.3)


# ──────────────────────────────────────────────────
# ResponseCache
# ──────────────────────────────────────────────────

class TestResponseCache:
    @pytest.fixture
    def cache(self) -> ResponseCache:
        return ResponseCache(default_ttl_seconds=10.0, max_entries=100)

    async def test_set_and_get(self, cache: ResponseCache) -> None:
        await cache.set("key1", {"data": "value"})
        result = await cache.get("key1")
        assert result == {"data": "value"}

    async def test_miss_returns_none(self, cache: ResponseCache) -> None:
        result = await cache.get("nonexistent")
        assert result is None

    async def test_expired_returns_none(self) -> None:
        cache = ResponseCache(default_ttl_seconds=0.01)
        await cache.set("key1", "value")
        await asyncio.sleep(0.02)
        result = await cache.get("key1")
        assert result is None

    async def test_invalidate_specific_key(self, cache: ResponseCache) -> None:
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        removed = await cache.invalidate("key1")
        assert removed
        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"

    async def test_clear_all(self, cache: ResponseCache) -> None:
        await cache.set("key1", "v1")
        await cache.set("key2", "v2")
        await cache.clear()
        assert cache.size == 0

    async def test_stats_tracking(self, cache: ResponseCache) -> None:
        await cache.set("key1", "value")
        await cache.get("key1")  # hit
        await cache.get("missing")  # miss
        assert cache.stats.hits == 1
        assert cache.stats.misses == 1
        assert cache.stats.sets == 1

    async def test_max_entries_eviction(self) -> None:
        cache = ResponseCache(default_ttl_seconds=300, max_entries=3)
        await cache.set("k1", "v1")
        await cache.set("k2", "v2")
        await cache.set("k3", "v3")
        await cache.set("k4", "v4")  # Should evict oldest
        assert cache.size == 3

    async def test_health_check(self, cache: ResponseCache) -> None:
        health = await cache.health_check()
        assert health["status"] == "ok"
        assert "entries" in health
        assert "hit_rate" in health


class TestMakeKey:
    def test_deterministic(self) -> None:
        k1 = ResponseCache.make_key("l1", "query text", "tenant-1")
        k2 = ResponseCache.make_key("l1", "query text", "tenant-1")
        assert k1 == k2

    def test_different_queries(self) -> None:
        k1 = ResponseCache.make_key("l1", "query A", "tenant-1")
        k2 = ResponseCache.make_key("l1", "query B", "tenant-1")
        assert k1 != k2

    def test_different_tenants(self) -> None:
        k1 = ResponseCache.make_key("l1", "query", "tenant-1")
        k2 = ResponseCache.make_key("l1", "query", "tenant-2")
        assert k1 != k2


class TestFactories:
    def test_create_response_cache(self) -> None:
        cache = create_response_cache()
        assert cache._default_ttl == 300.0  # 5 minutes

    def test_create_retrieval_cache(self) -> None:
        cache = create_retrieval_cache()
        assert cache._default_ttl == 120.0  # 2 minutes
