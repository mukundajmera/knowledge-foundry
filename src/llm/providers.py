"""Knowledge Foundry — LLM Providers.

Async wrappers around LLM provider APIs:
- AnthropicProvider: Anthropic Claude (Opus / Sonnet / Haiku)
- OracleCodeAssistProvider: Oracle Code Assist (OpenAI-compatible)
- LMStudioProvider: LM Studio (local, OpenAI-compatible)
- OllamaProvider: Ollama (local, native API)
"""

from __future__ import annotations

import time
from typing import Any

import anthropic
import httpx

from src.core.config import (
    LMStudioSettings,
    OllamaSettings,
    OracleCodeAssistSettings,
    Settings,
    get_settings,
)
from src.core.exceptions import (
    LLMContentFilterError,
    LLMProviderError,
    LLMRateLimitError,
)
from src.core.interfaces import LLMConfig, LLMProvider, LLMResponse, ModelTier


# Cost per token (input, output) — USD per individual token
MODEL_COSTS: dict[str, tuple[float, float]] = {
    "claude-opus-4-20250514": (15.0 / 1_000_000, 75.0 / 1_000_000),
    "claude-sonnet-4-20250514": (3.0 / 1_000_000, 15.0 / 1_000_000),
    "claude-3-5-haiku-20241022": (0.25 / 1_000_000, 1.25 / 1_000_000),
    # Oracle Code Assist — estimated pricing
    "oracle-code-assist-v1": (2.0 / 1_000_000, 8.0 / 1_000_000),
}

# Fallback for unknown models
DEFAULT_COST = (3.0 / 1_000_000, 15.0 / 1_000_000)

# Local provider cost (free)
LOCAL_COST = (0.0, 0.0)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude LLM provider with async support.

    Supports Opus, Sonnet, and Haiku tiers. Handles retries internally
    via the anthropic SDK and provides cost tracking per request.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = anthropic.AsyncAnthropic(
            api_key=self._settings.anthropic.api_key,
            max_retries=self._settings.anthropic.max_retries,
            timeout=self._settings.anthropic.timeout,
        )
        self._model_map: dict[ModelTier, str] = {
            ModelTier.OPUS: self._settings.anthropic.model_opus,
            ModelTier.SONNET: self._settings.anthropic.model_sonnet,
            ModelTier.HAIKU: self._settings.anthropic.model_haiku,
        }

    def resolve_model(self, config: LLMConfig) -> str:
        """Resolve the model identifier from config or tier."""
        if config.model:
            return config.model
        return self._model_map.get(config.tier, self._settings.anthropic.model_sonnet)

    async def generate(self, prompt: str, config: LLMConfig) -> LLMResponse:
        """Generate a completion using the Anthropic Messages API.

        Args:
            prompt: The user prompt text.
            config: LLM configuration (model, temperature, etc.).

        Returns:
            LLMResponse with the generated text, token counts, and cost.

        Raises:
            LLMRateLimitError: If the API rate limit is exceeded.
            LLMContentFilterError: If the model refuses on safety grounds.
            LLMProviderError: For all other API errors.
        """
        model = self.resolve_model(config)
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

        start_time = time.monotonic()
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "top_p": config.top_p,
            }
            if config.system_prompt:
                kwargs["system"] = config.system_prompt
            if config.stop_sequences:
                kwargs["stop_sequences"] = config.stop_sequences

            response = await self._client.messages.create(**kwargs)

        except anthropic.RateLimitError as exc:
            raise LLMRateLimitError(
                message=f"Anthropic rate limit exceeded for model {model}",
                retry_after_seconds=60.0,
                details={"model": model},
            ) from exc

        except anthropic.BadRequestError as exc:
            # Safety filter or content policy refusal
            if "safety" in str(exc).lower() or "content" in str(exc).lower():
                raise LLMContentFilterError(
                    f"Content filtered by Anthropic safety policy: {exc}",
                    details={"model": model},
                ) from exc
            raise LLMProviderError(
                message=f"Anthropic bad request: {exc}",
                provider="anthropic",
                model=model,
                status_code=400,
            ) from exc

        except anthropic.APIError as exc:
            raise LLMProviderError(
                message=f"Anthropic API error: {exc}",
                provider="anthropic",
                model=model,
                status_code=getattr(exc, "status_code", None),
            ) from exc

        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Extract text from response content blocks
        text_parts: list[str] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)

        response_text = "\n".join(text_parts)
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        # Calculate cost
        input_cost, output_cost = self.get_cost_per_token(model)
        cost_usd = (input_tokens * input_cost) + (output_tokens * output_cost)

        return LLMResponse(
            text=response_text,
            model=model,
            tier=config.tier,
            confidence=0.0,  # Set by router based on response quality
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=round(cost_usd, 6),
        )

    async def health_check(self) -> bool:
        """Quick health check using Haiku with minimal tokens."""
        try:
            config = LLMConfig(
                model=self._model_map[ModelTier.HAIKU],
                tier=ModelTier.HAIKU,
                max_tokens=10,
                temperature=0.0,
            )
            response = await self.generate("Say OK", config)
            return len(response.text) > 0
        except Exception:
            return False

    def get_cost_per_token(self, model: str) -> tuple[float, float]:
        """Return (input_cost_per_token, output_cost_per_token) for a model."""
        return MODEL_COSTS.get(model, DEFAULT_COST)


# =============================================================
# OPENAI-COMPATIBLE BASE (shared by Oracle Code Assist & LM Studio)
# =============================================================


class _OpenAICompatibleProvider(LLMProvider):
    """Base class for providers with OpenAI-compatible chat/completions API.

    Subclasses must set ``_provider_name``, ``_base_url``, ``_default_model``,
    ``_headers``, and ``_timeout`` in their ``__init__``.
    """

    _provider_name: str = "openai_compatible"
    _base_url: str = ""
    _default_model: str = ""
    _headers: dict[str, str] = {}
    _timeout: int = 30
    _client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Lazily create the httpx client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    def _resolve_model(self, config: LLMConfig) -> str:
        """Return the model from config or the provider default."""
        return config.model if config.model else self._default_model

    async def generate(self, prompt: str, config: LLMConfig) -> LLMResponse:
        """Generate a completion via the OpenAI-compatible chat API.

        Args:
            prompt: The user prompt text.
            config: LLM configuration.

        Returns:
            LLMResponse with generated text, token counts, and cost.

        Raises:
            LLMRateLimitError: On HTTP 429.
            LLMProviderError: On all other HTTP errors or connection failures.
        """
        model = self._resolve_model(config)
        client = self._get_client()

        messages: list[dict[str, str]] = []
        if config.system_prompt:
            messages.append({"role": "system", "content": config.system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
        }
        if config.stop_sequences:
            payload["stop"] = config.stop_sequences

        start_time = time.monotonic()
        try:
            resp = await client.post("/chat/completions", json=payload)
        except httpx.ConnectError as exc:
            raise LLMProviderError(
                message=f"{self._provider_name} connection failed: {exc}",
                provider=self._provider_name,
                model=model,
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMProviderError(
                message=f"{self._provider_name} request timed out: {exc}",
                provider=self._provider_name,
                model=model,
            ) from exc

        latency_ms = int((time.monotonic() - start_time) * 1000)

        if resp.status_code == 429:
            raise LLMRateLimitError(
                message=f"{self._provider_name} rate limit exceeded for {model}",
                retry_after_seconds=60.0,
                details={"model": model},
            )

        if resp.status_code >= 400:
            raise LLMProviderError(
                message=f"{self._provider_name} API error ({resp.status_code}): {resp.text}",
                provider=self._provider_name,
                model=model,
                status_code=resp.status_code,
            )

        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        input_cost, output_cost = self.get_cost_per_token(model)
        cost_usd = (input_tokens * input_cost) + (output_tokens * output_cost)

        return LLMResponse(
            text=text,
            model=model,
            tier=config.tier,
            confidence=0.0,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=round(cost_usd, 6),
        )

    async def health_check(self) -> bool:
        """Ping the models endpoint to verify connectivity."""
        try:
            client = self._get_client()
            resp = await client.get("/models")
            return resp.status_code == 200
        except Exception:
            return False

    def get_cost_per_token(self, model: str) -> tuple[float, float]:
        """Return (input_cost, output_cost) per token."""
        return MODEL_COSTS.get(model, LOCAL_COST)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# =============================================================
# ORACLE CODE ASSIST
# =============================================================


class OracleCodeAssistProvider(_OpenAICompatibleProvider):
    """Oracle Code Assist LLM provider.

    Connects to Oracle's cloud-hosted, OpenAI-compatible
    ``/v1/chat/completions`` endpoint with API key auth.
    """

    def __init__(self, settings: OracleCodeAssistSettings | None = None) -> None:
        s = settings or get_settings().oracle
        self._provider_name = "oracle_code_assist"
        self._base_url = s.endpoint.rstrip("/")
        self._default_model = s.model
        self._headers = {
            "Authorization": f"Bearer {s.api_key}",
            "Content-Type": "application/json",
        }
        self._timeout = s.timeout
        self._client = None

    def get_cost_per_token(self, model: str) -> tuple[float, float]:
        """Oracle models have tracked costs."""
        return MODEL_COSTS.get(model, DEFAULT_COST)


# =============================================================
# LM STUDIO
# =============================================================


class LMStudioProvider(_OpenAICompatibleProvider):
    """LM Studio LLM provider.

    Connects to a local LM Studio server's OpenAI-compatible API
    (default ``http://localhost:1234/v1``). No API key required.
    All inference is local — zero cost.
    """

    def __init__(self, settings: LMStudioSettings | None = None) -> None:
        s = settings or get_settings().lmstudio
        self._provider_name = "lmstudio"
        self._base_url = s.base_url
        self._default_model = s.model or "local-model"
        self._headers = {"Content-Type": "application/json"}
        self._timeout = s.timeout
        self._client = None

    def get_cost_per_token(self, model: str) -> tuple[float, float]:
        """Local inference is free."""
        return LOCAL_COST


# =============================================================
# OLLAMA
# =============================================================


class OllamaProvider(LLMProvider):
    """Ollama LLM provider.

    Connects to a local Ollama server (default ``http://localhost:11434``)
    using Ollama's native ``/api/chat`` endpoint.
    All inference is local — zero cost.
    """

    def __init__(self, settings: OllamaSettings | None = None) -> None:
        s = settings or get_settings().ollama
        self._provider_name = "ollama"
        self._base_url = s.base_url
        self._default_model = s.model
        self._timeout = s.timeout
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Lazily create the httpx client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def generate(self, prompt: str, config: LLMConfig) -> LLMResponse:
        """Generate a completion using Ollama's native chat API.

        Args:
            prompt: The user prompt text.
            config: LLM configuration.

        Returns:
            LLMResponse with the generated text.

        Raises:
            LLMProviderError: On connection or API failures.
        """
        model = config.model if config.model else self._default_model
        client = self._get_client()

        messages: list[dict[str, str]] = []
        if config.system_prompt:
            messages.append({"role": "system", "content": config.system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": config.temperature,
                "top_p": config.top_p,
                "num_predict": config.max_tokens,
            },
        }
        if config.stop_sequences:
            payload["options"]["stop"] = config.stop_sequences

        start_time = time.monotonic()
        try:
            resp = await client.post("/api/chat", json=payload)
        except httpx.ConnectError as exc:
            raise LLMProviderError(
                message=f"Ollama connection failed: {exc}",
                provider="ollama",
                model=model,
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMProviderError(
                message=f"Ollama request timed out: {exc}",
                provider="ollama",
                model=model,
            ) from exc

        latency_ms = int((time.monotonic() - start_time) * 1000)

        if resp.status_code >= 400:
            raise LLMProviderError(
                message=f"Ollama API error ({resp.status_code}): {resp.text}",
                provider="ollama",
                model=model,
                status_code=resp.status_code,
            )

        data = resp.json()
        text = data.get("message", {}).get("content", "")

        # Ollama provides token counts in some versions
        input_tokens = data.get("prompt_eval_count", 0)
        output_tokens = data.get("eval_count", 0)

        return LLMResponse(
            text=text,
            model=model,
            tier=config.tier,
            confidence=0.0,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=0.0,  # Local inference is free
        )

    async def health_check(self) -> bool:
        """Check if Ollama is running by hitting the tags endpoint."""
        try:
            client = self._get_client()
            resp = await client.get("/api/tags")
            return resp.status_code == 200
        except Exception:
            return False

    def get_cost_per_token(self, model: str) -> tuple[float, float]:
        """Local inference is free."""
        return LOCAL_COST

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

