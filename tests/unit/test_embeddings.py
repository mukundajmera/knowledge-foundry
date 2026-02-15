"""Tests for src.retrieval.embeddings — EmbeddingService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.config import OpenAISettings, RedisSettings
from src.core.exceptions import EmbeddingError
from src.retrieval.embeddings import EmbeddingService


class TestEmbeddingService:
    @pytest.fixture
    def mock_openai(self) -> AsyncMock:
        client = AsyncMock()
        # Mock embedding response
        emb_data = MagicMock()
        emb_data.embedding = [0.1] * 3072
        response = MagicMock()
        response.data = [emb_data]
        client.embeddings.create = AsyncMock(return_value=response)
        return client

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock()
        return redis

    @pytest.fixture
    def service(self, mock_openai: AsyncMock, mock_redis: AsyncMock) -> EmbeddingService:
        return EmbeddingService(
            openai_client=mock_openai,
            redis_client=mock_redis,
        )

    @pytest.fixture
    def service_no_cache(self, mock_openai: AsyncMock) -> EmbeddingService:
        return EmbeddingService(
            openai_client=mock_openai,
            redis_client=None,
        )

    @pytest.mark.asyncio
    async def test_embed_query(self, service: EmbeddingService, mock_openai: AsyncMock) -> None:
        result = await service.embed_query("test query")
        assert len(result) == 3072
        mock_openai.embeddings.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_query_cache_hit(
        self, service: EmbeddingService, mock_openai: AsyncMock, mock_redis: AsyncMock
    ) -> None:
        import json
        cached_embedding = [0.2] * 3072
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_embedding))

        result = await service.embed_query("cached query")
        assert result == cached_embedding
        mock_openai.embeddings.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_embed_query_caches_result(
        self, service: EmbeddingService, mock_redis: AsyncMock
    ) -> None:
        await service.embed_query("new query")
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_batch(self, service: EmbeddingService, mock_openai: AsyncMock) -> None:
        # Mock batch response
        emb_data1 = MagicMock()
        emb_data1.embedding = [0.1] * 3072
        emb_data2 = MagicMock()
        emb_data2.embedding = [0.2] * 3072
        response = MagicMock()
        response.data = [emb_data1, emb_data2]
        mock_openai.embeddings.create = AsyncMock(return_value=response)

        results = await service.embed(["text 1", "text 2"])
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_embed_empty(self, service: EmbeddingService) -> None:
        results = await service.embed([])
        assert results == []

    @pytest.mark.asyncio
    async def test_embed_query_without_cache(
        self, service_no_cache: EmbeddingService, mock_openai: AsyncMock
    ) -> None:
        # Should work without Redis
        result = await service_no_cache.embed_query("test")
        assert len(result) == 3072

    @pytest.mark.asyncio
    async def test_cache_failure_graceful(
        self, service: EmbeddingService, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get = AsyncMock(side_effect=Exception("Redis down"))
        # Should still work, just skip cache
        result = await service.embed_query("test")
        assert len(result) == 3072
