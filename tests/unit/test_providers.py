"""Tests for src.llm.providers — AnthropicProvider, OracleCodeAssistProvider, LMStudioProvider, OllamaProvider."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.core.config import (
    LMStudioSettings,
    OllamaSettings,
    OracleCodeAssistSettings,
    Settings,
)
from src.core.exceptions import LLMProviderError, LLMRateLimitError
from src.core.interfaces import LLMConfig, LLMResponse, ModelTier
from src.llm.providers import (
    LOCAL_COST,
    MODEL_COSTS,
    AnthropicProvider,
    LMStudioProvider,
    OllamaProvider,
    OracleCodeAssistProvider,
)


class TestAnthropicProvider:
    @pytest.fixture
    def settings(self) -> Settings:
        return Settings()

    @pytest.fixture
    def provider(self, settings: Settings) -> AnthropicProvider:
        return AnthropicProvider(settings=settings)

    def test_resolve_model_by_tier(self, provider: AnthropicProvider) -> None:
        config = LLMConfig(model="", tier=ModelTier.OPUS)
        assert "opus" in provider.resolve_model(config).lower()

        config = LLMConfig(model="", tier=ModelTier.HAIKU)
        assert "haiku" in provider.resolve_model(config).lower()

    def test_resolve_model_explicit(self, provider: AnthropicProvider) -> None:
        config = LLMConfig(model="custom-model", tier=ModelTier.SONNET)
        assert provider.resolve_model(config) == "custom-model"

    def test_cost_per_token_known(self, provider: AnthropicProvider) -> None:
        input_cost, output_cost = provider.get_cost_per_token("claude-opus-4-20250514")
        assert input_cost > 0
        assert output_cost > input_cost

    def test_cost_per_token_unknown(self, provider: AnthropicProvider) -> None:
        input_cost, output_cost = provider.get_cost_per_token("unknown-model")
        assert input_cost > 0
        assert output_cost > 0

    @pytest.mark.asyncio
    async def test_generate_success(self, provider: AnthropicProvider) -> None:
        # Mock the internal Anthropic client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Hello!")]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)

        provider._client = AsyncMock()
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        config = LLMConfig(model="claude-sonnet-4-20250514", tier=ModelTier.SONNET)
        response = await provider.generate("Say hello", config)

        assert isinstance(response, LLMResponse)
        assert response.text == "Hello!"
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        assert response.cost_usd > 0

    @pytest.mark.asyncio
    async def test_generate_rate_limit(self, provider: AnthropicProvider) -> None:
        import anthropic

        provider._client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {}
        mock_response.text = "rate limit"
        mock_response.headers = {}
        provider._client.messages.create = AsyncMock(
            side_effect=anthropic.RateLimitError(
                message="rate limit",
                response=mock_response,
                body=None,
            )
        )

        config = LLMConfig(model="claude-sonnet-4-20250514", tier=ModelTier.SONNET)
        with pytest.raises(LLMRateLimitError):
            await provider.generate("test", config)

    @pytest.mark.asyncio
    async def test_generate_api_error(self, provider: AnthropicProvider) -> None:
        import anthropic

        provider._client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {}
        mock_response.text = "internal error"
        mock_response.headers = {}
        provider._client.messages.create = AsyncMock(
            side_effect=anthropic.APIError(
                message="internal error",
                request=MagicMock(),
                body=None,
            )
        )

        config = LLMConfig(model="claude-sonnet-4-20250514", tier=ModelTier.SONNET)
        with pytest.raises(LLMProviderError):
            await provider.generate("test", config)


class TestModelCosts:
    def test_all_models_have_costs(self) -> None:
        assert "claude-opus-4-20250514" in MODEL_COSTS
        assert "claude-sonnet-4-20250514" in MODEL_COSTS
        assert "claude-3-5-haiku-20241022" in MODEL_COSTS
        assert "oracle-code-assist-v1" in MODEL_COSTS

    def test_cost_ordering(self) -> None:
        opus = MODEL_COSTS["claude-opus-4-20250514"]
        sonnet = MODEL_COSTS["claude-sonnet-4-20250514"]
        haiku = MODEL_COSTS["claude-3-5-haiku-20241022"]
        # Opus > Sonnet > Haiku
        assert opus[0] > sonnet[0] > haiku[0]

    def test_local_cost_is_zero(self) -> None:
        assert LOCAL_COST == (0.0, 0.0)


# =============================================================
# Helper to create mock httpx transports
# =============================================================


def _openai_success_handler(request: httpx.Request) -> httpx.Response:
    """Mock transport handler simulating OpenAI-compatible success."""
    if request.url.path.endswith("/chat/completions"):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Hello from mock!"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8},
            },
        )
    if request.url.path.endswith("/models"):
        return httpx.Response(200, json={"data": []})
    return httpx.Response(404)


def _openai_rate_limit_handler(request: httpx.Request) -> httpx.Response:
    """Mock transport handler simulating 429 rate limit."""
    return httpx.Response(429, text="rate limit exceeded")


def _openai_error_handler(request: httpx.Request) -> httpx.Response:
    """Mock transport handler simulating 500 server error."""
    return httpx.Response(500, text="internal server error")


def _ollama_success_handler(request: httpx.Request) -> httpx.Response:
    """Mock transport handler simulating Ollama success."""
    if request.url.path.endswith("/api/chat"):
        return httpx.Response(
            200,
            json={
                "message": {"content": "Hello from Ollama!"},
                "prompt_eval_count": 15,
                "eval_count": 10,
            },
        )
    if request.url.path.endswith("/api/tags"):
        return httpx.Response(200, json={"models": []})
    return httpx.Response(404)


def _ollama_error_handler(request: httpx.Request) -> httpx.Response:
    """Mock transport handler simulating Ollama error."""
    return httpx.Response(500, text="model not found")


# =============================================================
# ORACLE CODE ASSIST TESTS
# =============================================================


class TestOracleCodeAssistProvider:
    @pytest.fixture
    def settings(self) -> OracleCodeAssistSettings:
        return OracleCodeAssistSettings(
            endpoint="https://mock-oracle.example.com/v1",
            api_key="test-key-123",
            model="oracle-code-assist-v1",
            timeout=10,
        )

    @pytest.fixture
    def provider(self, settings: OracleCodeAssistSettings) -> OracleCodeAssistProvider:
        p = OracleCodeAssistProvider(settings=settings)
        p._client = httpx.AsyncClient(
            transport=httpx.MockTransport(_openai_success_handler),
            base_url=settings.endpoint,
        )
        return p

    @pytest.mark.asyncio
    async def test_generate_success(self, provider: OracleCodeAssistProvider) -> None:
        config = LLMConfig(model="oracle-code-assist-v1", tier=ModelTier.SONNET)
        response = await provider.generate("Generate a function", config)
        assert isinstance(response, LLMResponse)
        assert response.text == "Hello from mock!"
        assert response.model == "oracle-code-assist-v1"
        assert response.input_tokens == 12
        assert response.output_tokens == 8

    @pytest.mark.asyncio
    async def test_generate_rate_limit(self, settings: OracleCodeAssistSettings) -> None:
        provider = OracleCodeAssistProvider(settings=settings)
        provider._client = httpx.AsyncClient(
            transport=httpx.MockTransport(_openai_rate_limit_handler),
            base_url=settings.endpoint,
        )
        config = LLMConfig(model="oracle-code-assist-v1", tier=ModelTier.SONNET)
        with pytest.raises(LLMRateLimitError):
            await provider.generate("test", config)

    @pytest.mark.asyncio
    async def test_generate_api_error(self, settings: OracleCodeAssistSettings) -> None:
        provider = OracleCodeAssistProvider(settings=settings)
        provider._client = httpx.AsyncClient(
            transport=httpx.MockTransport(_openai_error_handler),
            base_url=settings.endpoint,
        )
        config = LLMConfig(model="oracle-code-assist-v1", tier=ModelTier.SONNET)
        with pytest.raises(LLMProviderError):
            await provider.generate("test", config)

    @pytest.mark.asyncio
    async def test_health_check(self, provider: OracleCodeAssistProvider) -> None:
        assert await provider.health_check() is True

    def test_cost_per_token(self, provider: OracleCodeAssistProvider) -> None:
        cost = provider.get_cost_per_token("oracle-code-assist-v1")
        assert cost[0] > 0
        assert cost[1] > 0

    def test_unknown_model_falls_back_to_default(self, provider: OracleCodeAssistProvider) -> None:
        cost = provider.get_cost_per_token("unknown-oracle-model")
        # Oracle provider uses DEFAULT_COST for unknown models, not LOCAL_COST
        assert cost[0] > 0


# =============================================================
# LM STUDIO TESTS
# =============================================================


class TestLMStudioProvider:
    @pytest.fixture
    def settings(self) -> LMStudioSettings:
        return LMStudioSettings(host="localhost", port=1234, model="test-model", timeout=10)

    @pytest.fixture
    def provider(self, settings: LMStudioSettings) -> LMStudioProvider:
        p = LMStudioProvider(settings=settings)
        p._client = httpx.AsyncClient(
            transport=httpx.MockTransport(_openai_success_handler),
            base_url=settings.base_url,
        )
        return p

    @pytest.mark.asyncio
    async def test_generate_success(self, provider: LMStudioProvider) -> None:
        config = LLMConfig(model="test-model", tier=ModelTier.SONNET)
        response = await provider.generate("Hello", config)
        assert isinstance(response, LLMResponse)
        assert response.text == "Hello from mock!"
        assert response.cost_usd == 0.0  # Local is free

    @pytest.mark.asyncio
    async def test_generate_connection_error(self, settings: LMStudioSettings) -> None:
        def connection_error(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        provider = LMStudioProvider(settings=settings)
        provider._client = httpx.AsyncClient(
            transport=httpx.MockTransport(connection_error),
            base_url=settings.base_url,
        )
        config = LLMConfig(model="test-model", tier=ModelTier.SONNET)
        with pytest.raises(LLMProviderError, match="connection failed"):
            await provider.generate("test", config)

    @pytest.mark.asyncio
    async def test_health_check(self, provider: LMStudioProvider) -> None:
        assert await provider.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, settings: LMStudioSettings) -> None:
        def fail_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        provider = LMStudioProvider(settings=settings)
        provider._client = httpx.AsyncClient(
            transport=httpx.MockTransport(fail_handler),
            base_url=settings.base_url,
        )
        assert await provider.health_check() is False

    def test_zero_cost(self, provider: LMStudioProvider) -> None:
        assert provider.get_cost_per_token("any-model") == (0.0, 0.0)

    def test_base_url(self) -> None:
        s = LMStudioSettings(host="myhost", port=5678)
        assert s.base_url == "http://myhost:5678/v1"


# =============================================================
# OLLAMA TESTS
# =============================================================


class TestOllamaProvider:
    @pytest.fixture
    def settings(self) -> OllamaSettings:
        return OllamaSettings(host="localhost", port=11434, model="llama3", timeout=10)

    @pytest.fixture
    def provider(self, settings: OllamaSettings) -> OllamaProvider:
        p = OllamaProvider(settings=settings)
        p._client = httpx.AsyncClient(
            transport=httpx.MockTransport(_ollama_success_handler),
            base_url=settings.base_url,
        )
        return p

    @pytest.mark.asyncio
    async def test_generate_success(self, provider: OllamaProvider) -> None:
        config = LLMConfig(model="llama3", tier=ModelTier.SONNET)
        response = await provider.generate("Hello", config)
        assert isinstance(response, LLMResponse)
        assert response.text == "Hello from Ollama!"
        assert response.model == "llama3"
        assert response.input_tokens == 15
        assert response.output_tokens == 10
        assert response.cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_generate_with_system_prompt(self, provider: OllamaProvider) -> None:
        config = LLMConfig(
            model="llama3",
            tier=ModelTier.SONNET,
            system_prompt="You are a helpful assistant",
        )
        response = await provider.generate("Hello", config)
        assert response.text == "Hello from Ollama!"

    @pytest.mark.asyncio
    async def test_generate_connection_error(self, settings: OllamaSettings) -> None:
        def connection_error(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        provider = OllamaProvider(settings=settings)
        provider._client = httpx.AsyncClient(
            transport=httpx.MockTransport(connection_error),
            base_url=settings.base_url,
        )
        config = LLMConfig(model="llama3", tier=ModelTier.SONNET)
        with pytest.raises(LLMProviderError, match="connection failed"):
            await provider.generate("test", config)

    @pytest.mark.asyncio
    async def test_generate_api_error(self, settings: OllamaSettings) -> None:
        provider = OllamaProvider(settings=settings)
        provider._client = httpx.AsyncClient(
            transport=httpx.MockTransport(_ollama_error_handler),
            base_url=settings.base_url,
        )
        config = LLMConfig(model="nonexistent", tier=ModelTier.SONNET)
        with pytest.raises(LLMProviderError):
            await provider.generate("test", config)

    @pytest.mark.asyncio
    async def test_health_check(self, provider: OllamaProvider) -> None:
        assert await provider.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, settings: OllamaSettings) -> None:
        def fail_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        provider = OllamaProvider(settings=settings)
        provider._client = httpx.AsyncClient(
            transport=httpx.MockTransport(fail_handler),
            base_url=settings.base_url,
        )
        assert await provider.health_check() is False

    def test_zero_cost(self, provider: OllamaProvider) -> None:
        assert provider.get_cost_per_token("llama3") == (0.0, 0.0)

    def test_base_url(self) -> None:
        s = OllamaSettings(host="myhost", port=9999)
        assert s.base_url == "http://myhost:9999"

