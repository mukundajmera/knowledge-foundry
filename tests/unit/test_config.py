"""Tests for src.core.config — Settings loading and validation."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.core.config import (
    AnthropicSettings,
    OpenAISettings,
    PostgresSettings,
    QdrantSettings,
    RedisSettings,
    Settings,
    get_settings,
)


class TestAnthropicSettings:
    """Tests for AnthropicSettings."""

    def test_defaults(self) -> None:
        settings = AnthropicSettings()
        assert settings.model_opus == "claude-opus-4-20250514"
        assert settings.model_sonnet == "claude-sonnet-4-20250514"
        assert settings.model_haiku == "claude-3-5-haiku-20241022"
        assert settings.max_retries == 3
        assert settings.timeout == 30

    def test_env_override(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_MAX_RETRIES": "5"}):
            settings = AnthropicSettings()
            assert settings.max_retries == 5


class TestOpenAISettings:
    """Tests for OpenAISettings."""

    def test_defaults(self) -> None:
        settings = OpenAISettings()
        assert settings.embedding_model == "text-embedding-3-large"
        assert settings.embedding_dimensions == 3072


class TestQdrantSettings:
    """Tests for QdrantSettings."""

    def test_defaults(self) -> None:
        settings = QdrantSettings()
        assert settings.host == "localhost"
        assert settings.port == 6333
        assert settings.hnsw_m == 16
        assert settings.hnsw_ef_construct == 200
        assert settings.collection_prefix == "kf_tenant_"


class TestRedisSettings:
    """Tests for RedisSettings."""

    def test_defaults(self) -> None:
        settings = RedisSettings()
        assert settings.host == "localhost"
        assert settings.port == 6379
        assert settings.key_prefix == "kf:"


class TestPostgresSettings:
    """Tests for PostgresSettings."""

    def test_defaults(self) -> None:
        settings = PostgresSettings()
        assert settings.db == "knowledge_foundry"

    def test_dsn(self) -> None:
        settings = PostgresSettings()
        dsn = settings.dsn
        assert "postgresql+asyncpg://" in dsn
        assert "knowledge_foundry" in dsn


class TestSettings:
    """Tests for the root Settings."""

    def test_defaults(self) -> None:
        settings = Settings()
        assert settings.app_name == "knowledge-foundry"
        assert settings.app_env == "development"
        assert settings.app_debug is True
        assert settings.app_port == 8000
        assert isinstance(settings.anthropic, AnthropicSettings)
        assert isinstance(settings.openai, OpenAISettings)
        assert isinstance(settings.qdrant, QdrantSettings)
        assert isinstance(settings.redis, RedisSettings)
        assert isinstance(settings.postgres, PostgresSettings)

    def test_env_override(self) -> None:
        with patch.dict(os.environ, {"APP_ENV": "production", "APP_DEBUG": "false"}):
            settings = Settings()
            assert settings.app_env == "production"
            assert settings.app_debug is False


class TestGetSettings:
    """Tests for the singleton factory."""

    def test_returns_settings(self) -> None:
        get_settings.cache_clear()
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_cached(self) -> None:
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
