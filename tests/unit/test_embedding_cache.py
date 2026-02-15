"""Tests for src.cache.embedding_cache — L2 embedding cache."""

from __future__ import annotations

import pytest

from src.cache.embedding_cache import EmbeddingCache, create_embedding_cache


class TestEmbeddingCache:
    """Tests for EmbeddingCache."""

    @pytest.fixture
    def cache(self) -> EmbeddingCache:
        return EmbeddingCache(ttl_seconds=60.0, max_entries=100)

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache: EmbeddingCache):
        """Set an embedding and retrieve it."""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        await cache.set("hello world", embedding)
        result = await cache.get("hello world")
        assert result == embedding

    @pytest.mark.asyncio
    async def test_miss_returns_none(self, cache: EmbeddingCache):
        """Cache miss should return None."""
        result = await cache.get("not_in_cache")
        assert result is None

    @pytest.mark.asyncio
    async def test_different_models_different_keys(self, cache: EmbeddingCache):
        """Same text with different models should have separate cache entries."""
        emb_a = [0.1, 0.2]
        emb_b = [0.9, 0.8]
        await cache.set("hello", emb_a, model="model_a")
        await cache.set("hello", emb_b, model="model_b")

        result_a = await cache.get("hello", model="model_a")
        result_b = await cache.get("hello", model="model_b")
        assert result_a == emb_a
        assert result_b == emb_b

    @pytest.mark.asyncio
    async def test_invalidate(self, cache: EmbeddingCache):
        """Invalidate should remove the cached embedding."""
        await cache.set("to_delete", [1.0, 2.0])
        assert await cache.get("to_delete") is not None
        removed = await cache.invalidate("to_delete")
        assert removed is True
        assert await cache.get("to_delete") is None

    @pytest.mark.asyncio
    async def test_clear(self, cache: EmbeddingCache):
        """Clear should remove all entries."""
        await cache.set("a", [0.1])
        await cache.set("b", [0.2])
        assert cache.size == 2
        await cache.clear()
        assert cache.size == 0

    @pytest.mark.asyncio
    async def test_stats(self, cache: EmbeddingCache):
        """Stats should track hits and misses."""
        await cache.set("exists", [0.1])
        await cache.get("exists")  # hit
        await cache.get("missing")  # miss

        stats = cache.stats
        assert stats.hits == 1
        assert stats.misses == 1

    def test_make_key_deterministic(self):
        """Same inputs should produce the same key."""
        key1 = EmbeddingCache.make_key("hello", "model_a")
        key2 = EmbeddingCache.make_key("hello", "model_a")
        assert key1 == key2

    def test_make_key_different_texts(self):
        """Different texts should produce different keys."""
        key1 = EmbeddingCache.make_key("hello", "model_a")
        key2 = EmbeddingCache.make_key("world", "model_a")
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_health_check(self, cache: EmbeddingCache):
        """Health check should include cache level."""
        health = await cache.health_check()
        assert health["status"] == "ok"
        assert health["cache_level"] == "L2_embedding"

    def test_create_embedding_cache_factory(self):
        """Factory function should create a properly configured cache."""
        cache = create_embedding_cache()
        assert isinstance(cache, EmbeddingCache)
        assert cache.size == 0
