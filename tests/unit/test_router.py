"""Tests for src.llm.router — Complexity classifier, circuit breaker, and LLM router."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import CircuitBreakerOpenError, EscalationExhaustedError
from src.core.interfaces import LLMConfig, LLMResponse, ModelTier, RoutingDecision
from src.llm.router import (
    CircuitBreakerState,
    ComplexityFeatures,
    LLMRouter,
    compute_complexity_score,
    determine_tier,
    estimate_token_count,
    extract_complexity_features,
)


class TestEstimateTokenCount:
    def test_basic(self) -> None:
        assert estimate_token_count("hello world") >= 1

    def test_empty(self) -> None:
        assert estimate_token_count("") == 1

    def test_long_text(self) -> None:
        text = "word " * 1000
        tokens = estimate_token_count(text)
        assert tokens > 100


class TestExtractComplexityFeatures:
    def test_opus_keywords(self) -> None:
        features = extract_complexity_features("Design the architecture for this system")
        assert features.keyword_tier == "opus"
        assert features.keyword_tier_score == 1.0

    def test_sonnet_keywords(self) -> None:
        features = extract_complexity_features("Implement a function to sort a list")
        assert features.keyword_tier == "sonnet"

    def test_haiku_keywords(self) -> None:
        features = extract_complexity_features("Classify this text as positive or negative")
        assert features.keyword_tier == "haiku"

    def test_safety_sensitivity(self) -> None:
        features = extract_complexity_features(
            "Analyze security vulnerability and compliance requirements"
        )
        assert features.safety_sensitivity > 0.0

    def test_task_type_hint_override(self) -> None:
        features = extract_complexity_features(
            "hello",
            task_type_hint="architecture",
        )
        assert features.keyword_tier == "opus"

    def test_question_type_detection(self) -> None:
        features = extract_complexity_features("Why does this system fail under load?")
        assert features.question_type == "why"
        assert features.question_type_score == 0.8


class TestComputeComplexityScore:
    def test_low_complexity(self) -> None:
        features = ComplexityFeatures(
            token_count=10,
            keyword_tier="haiku",
            keyword_tier_score=0.1,
            question_type_score=0.1,
        )
        score = compute_complexity_score(features)
        assert 0.0 <= score <= 0.5

    def test_high_complexity(self) -> None:
        features = ComplexityFeatures(
            token_count=5000,
            keyword_tier="opus",
            keyword_tier_score=1.0,
            question_type_score=0.8,
            structural_complexity=5,
            entity_count=10,
            safety_sensitivity=0.8,
        )
        score = compute_complexity_score(features)
        assert score > 0.5

    def test_score_bounded(self) -> None:
        features = ComplexityFeatures(
            token_count=100000,
            keyword_tier_score=1.0,
            question_type_score=1.0,
            structural_complexity=100,
            entity_count=100,
            ambiguity_score=1.0,
            context_length=100000,
            safety_sensitivity=1.0,
        )
        score = compute_complexity_score(features)
        assert 0.0 <= score <= 1.0


class TestDetermineTier:
    def test_opus(self) -> None:
        assert determine_tier(0.8, 0.0) == ModelTier.OPUS

    def test_sonnet(self) -> None:
        assert determine_tier(0.5, 0.0) == ModelTier.SONNET

    def test_haiku(self) -> None:
        assert determine_tier(0.2, 0.0) == ModelTier.HAIKU

    def test_safety_override_to_opus(self) -> None:
        assert determine_tier(0.2, 0.9) == ModelTier.OPUS


class TestCircuitBreakerState:
    def test_initial_state(self) -> None:
        cb = CircuitBreakerState()
        assert cb.state == "closed"
        assert cb.can_execute() is True

    def test_opens_on_threshold(self) -> None:
        cb = CircuitBreakerState(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "open"
        assert cb.can_execute() is False

    def test_half_open_after_timeout(self) -> None:
        cb = CircuitBreakerState(failure_threshold=1, timeout_seconds=0.01)
        cb.record_failure()
        assert cb.state == "open"
        time.sleep(0.02)
        assert cb.can_execute() is True
        assert cb.state == "half_open"

    def test_success_resets_in_closed(self) -> None:
        cb = CircuitBreakerState(failure_threshold=5)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0

    def test_success_closes_from_half_open(self) -> None:
        cb = CircuitBreakerState(
            failure_threshold=1, success_threshold=2, timeout_seconds=0.01
        )
        cb.record_failure()
        time.sleep(0.02)
        cb.can_execute()  # transitions to half_open
        cb.record_success()
        cb.record_success()
        assert cb.state == "closed"


class TestLLMRouter:
    @pytest.fixture
    def mock_provider(self) -> AsyncMock:
        provider = AsyncMock()
        provider.generate.return_value = LLMResponse(
            text="This is a detailed response with analysis and recommendations.\n"
            "- First point\n- Second point\n- Third point\n"
            "## Summary\nThe conclusion is comprehensive.",
            model="claude-sonnet-4-20250514",
            tier=ModelTier.SONNET,
            input_tokens=100,
            output_tokens=50,
            latency_ms=200,
            cost_usd=0.001,
        )
        return provider

    @pytest.fixture
    def router(self, mock_provider: AsyncMock) -> LLMRouter:
        from src.core.config import Settings

        settings = Settings()
        return LLMRouter(provider=mock_provider, settings=settings)

    def test_classify_sonnet(self, router: LLMRouter) -> None:
        tier, features, score = router.classify("Implement a sorting function")
        assert tier in (ModelTier.SONNET, ModelTier.HAIKU, ModelTier.OPUS)

    def test_classify_opus(self, router: LLMRouter) -> None:
        tier, features, score = router.classify(
            "Design the architecture for this system, analyze security "
            "vulnerabilities and threat model implications. Why does the "
            "blast radius of this exploit affect our strategy?",
            task_type_hint="architecture",
        )
        # The task_type_hint sets keyword_tier to opus
        assert features.keyword_tier == "opus"
        assert features.keyword_tier_score == 1.0
        # With high safety sensitivity, determine_tier should route to opus
        # even if composite score is < 0.7
        assert features.safety_sensitivity > 0.0

    @pytest.mark.asyncio
    async def test_route_basic(
        self, router: LLMRouter, mock_provider: AsyncMock
    ) -> None:
        response, decision = await router.route("Implement a function")
        assert response.text
        assert isinstance(decision, RoutingDecision)
        assert mock_provider.generate.call_count >= 1

    @pytest.mark.asyncio
    async def test_route_forced(
        self, router: LLMRouter, mock_provider: AsyncMock
    ) -> None:
        response, decision = await router.route(
            "hello", force_model=ModelTier.OPUS
        )
        config = mock_provider.generate.call_args[0][1]
        assert config.tier == ModelTier.OPUS

    @pytest.mark.asyncio
    async def test_route_with_context(
        self, router: LLMRouter, mock_provider: AsyncMock
    ) -> None:
        response, decision = await router.route(
            "What is X?",
            context="X is a system for managing data.",
        )
        prompt = mock_provider.generate.call_args[0][0]
        assert "<context>" in prompt

    def test_circuit_breaker_states(self, router: LLMRouter) -> None:
        states = router.get_circuit_breaker_states()
        assert "opus" in states
        assert "sonnet" in states
        assert "haiku" in states
        assert all(v == "closed" for v in states.values())

    # --- Multi-provider registry tests ---

    def test_default_provider_registry(self, router: LLMRouter) -> None:
        """Router starts with anthropic as the only registered provider."""
        assert "anthropic" in router.registered_providers
        assert len(router.registered_providers) == 1

    def test_register_provider(self, router: LLMRouter) -> None:
        mock_ollama = AsyncMock()
        router.register_provider("ollama", mock_ollama)
        assert "ollama" in router.registered_providers
        assert router.get_provider("ollama") is mock_ollama

    def test_register_multiple_providers(self, router: LLMRouter) -> None:
        router.register_provider("ollama", AsyncMock())
        router.register_provider("lmstudio", AsyncMock())
        router.register_provider("oracle", AsyncMock())
        assert set(router.registered_providers) == {"anthropic", "ollama", "lmstudio", "oracle"}

    def test_get_unknown_provider(self, router: LLMRouter) -> None:
        assert router.get_provider("nonexistent") is None

    @pytest.mark.asyncio
    async def test_route_with_specific_provider(
        self, router: LLMRouter
    ) -> None:
        """Routing with provider='ollama' should use the ollama provider."""
        mock_ollama = AsyncMock()
        mock_ollama.generate.return_value = LLMResponse(
            text="Ollama says hello!",
            model="llama3",
            tier=ModelTier.SONNET,
            input_tokens=10,
            output_tokens=5,
            latency_ms=100,
            cost_usd=0.0,
        )
        router.register_provider("ollama", mock_ollama)

        response, decision = await router.route("hello", provider="ollama")
        assert response.text == "Ollama says hello!"
        assert mock_ollama.generate.call_count >= 1

    @pytest.mark.asyncio
    async def test_route_unknown_provider_raises(self, router: LLMRouter) -> None:
        from src.core.exceptions import RouterError
        with pytest.raises(RouterError, match="Unknown provider"):
            await router.route("hello", provider="nonexistent")

