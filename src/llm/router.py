"""Knowledge Foundry — Tiered Intelligence Router.

Heuristic-based complexity classifier that routes requests to the
optimal model tier (Opus / Sonnet / Haiku) based on query features.
Supports forced model override, escalation on low confidence, and
circuit breaker per provider.

Implements the routing policy from phase-1.1 spec §2.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from src.core.config import Settings, get_settings
from src.core.exceptions import (
    CircuitBreakerOpenError,
    EscalationExhaustedError,
    RouterError,
)
from src.core.interfaces import (
    LLMConfig,
    LLMProvider,
    LLMResponse,
    ModelTier,
    RoutingDecision,
)


# =============================================================
# COMPLEXITY CLASSIFIER
# =============================================================

# Keywords signaling Opus-tier complexity
OPUS_KEYWORDS = {
    "design", "architect", "adr", "tradeoff", "trade-off",
    "vulnerability", "exploit", "injection", "owasp",
    "implications", "impact", "blast radius", "strategy",
    "threat model", "security analysis",
}

# Keywords signaling Sonnet-tier
SONNET_KEYWORDS = {
    "implement", "create", "write", "build", "generate",
    "review", "check", "audit", "refactor",
    "summarize", "overview", "brief", "explain",
    "document", "docstring", "readme",
    "what is", "how to", "find", "search",
}

# Keywords signaling Haiku-tier
HAIKU_KEYWORDS = {
    "classify", "categorize", "extract", "ner",
    "format", "convert", "translate",
    "list", "enumerate",
}

# Question type scores
QUESTION_TYPE_SCORES = {
    "why": 0.8,
    "how should": 0.7,
    "how": 0.5,
    "what": 0.3,
    "format": 0.1,
    "list": 0.1,
}


@dataclass
class ComplexityFeatures:
    """Features extracted from a request for routing decisions."""

    token_count: int = 0
    keyword_tier: str = "sonnet"
    keyword_tier_score: float = 0.5
    question_type: str = "what"
    question_type_score: float = 0.3
    structural_complexity: int = 0
    entity_count: int = 0
    ambiguity_score: float = 0.0
    context_length: int = 0
    safety_sensitivity: float = 0.0


def estimate_token_count(text: str) -> int:
    """Rough token count estimate (1 token ≈ 4 chars for English)."""
    return max(1, len(text) // 4)


def extract_complexity_features(
    prompt: str,
    context: str | None = None,
    task_type_hint: str | None = None,
) -> ComplexityFeatures:
    """Extract routing features from a prompt.

    Uses the heuristic feature extraction from phase-1.1 spec §2.2.
    """
    prompt_lower = prompt.lower()
    features = ComplexityFeatures()

    # Token count
    features.token_count = estimate_token_count(prompt)
    features.context_length = estimate_token_count(context) if context else 0

    # Keyword detection — check from highest tier down
    opus_found = any(kw in prompt_lower for kw in OPUS_KEYWORDS)
    sonnet_found = any(kw in prompt_lower for kw in SONNET_KEYWORDS)
    haiku_found = any(kw in prompt_lower for kw in HAIKU_KEYWORDS)

    if opus_found:
        features.keyword_tier = "opus"
        features.keyword_tier_score = 1.0
    elif sonnet_found:
        features.keyword_tier = "sonnet"
        features.keyword_tier_score = 0.5
    elif haiku_found:
        features.keyword_tier = "haiku"
        features.keyword_tier_score = 0.1
    else:
        features.keyword_tier = "sonnet"
        features.keyword_tier_score = 0.5

    # Question type detection
    for qt, score in QUESTION_TYPE_SCORES.items():
        if qt in prompt_lower:
            features.question_type = qt
            features.question_type_score = score
            break

    # Structural complexity: code blocks, nested lists, tables
    code_blocks = len(re.findall(r"```", prompt))
    nested_lists = len(re.findall(r"^\s{2,}[-*]", prompt, re.MULTILINE))
    tables = len(re.findall(r"\|.*\|", prompt))
    features.structural_complexity = min(10, code_blocks + nested_lists + tables)

    # Entity count (rough: capitalized multi-word sequences)
    entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", prompt)
    features.entity_count = len(set(entities))

    # Safety sensitivity
    safety_keywords = {
        "security", "vulnerability", "exploit", "injection", "compliance",
        "regulation", "gdpr", "hipaa", "pii", "confidential",
    }
    safety_count = sum(1 for kw in safety_keywords if kw in prompt_lower)
    features.safety_sensitivity = min(1.0, safety_count / 3.0)

    # Ambiguity (heuristic: questions without specific terms)
    if "?" in prompt and features.entity_count == 0 and features.token_count < 20:
        features.ambiguity_score = 0.7
    else:
        features.ambiguity_score = 0.1

    # Override with task_type_hint if provided
    if task_type_hint:
        hint_lower = task_type_hint.lower()
        if hint_lower in ("architecture", "security_analysis", "complex_reasoning"):
            features.keyword_tier = "opus"
            features.keyword_tier_score = 1.0
        elif hint_lower in ("code_generation", "summarization", "rag_qa", "documentation"):
            features.keyword_tier = "sonnet"
            features.keyword_tier_score = 0.5
        elif hint_lower in ("classification", "entity_extraction", "formatting"):
            features.keyword_tier = "haiku"
            features.keyword_tier_score = 0.1

    return features


def compute_complexity_score(features: ComplexityFeatures) -> float:
    """Compute the complexity score using the formula from phase-1.1 spec §2.2.

    Returns a float between 0.0 and 1.0 where:
    - > 0.7 → Opus
    - 0.3 – 0.7 → Sonnet
    - < 0.3 → Haiku
    """
    score = (
        0.20 * min(1.0, features.token_count / 10000.0)
        + 0.25 * features.keyword_tier_score
        + 0.15 * features.question_type_score
        + 0.10 * min(1.0, features.structural_complexity / 10.0)
        + 0.10 * min(1.0, features.entity_count / 20.0)
        + 0.10 * features.ambiguity_score
        + 0.05 * min(1.0, features.context_length / 50000.0)
        + 0.05 * features.safety_sensitivity
    )
    return round(min(1.0, max(0.0, score)), 4)


def determine_tier(complexity_score: float, safety_sensitivity: float) -> ModelTier:
    """Map complexity score to model tier."""
    if complexity_score > 0.7 or safety_sensitivity > 0.8:
        return ModelTier.OPUS
    elif complexity_score > 0.3:
        return ModelTier.SONNET
    else:
        return ModelTier.HAIKU


# =============================================================
# CIRCUIT BREAKER
# =============================================================


@dataclass
class CircuitBreakerState:
    """Per-provider circuit breaker state."""

    failure_count: int = 0
    success_count: int = 0
    state: str = "closed"  # closed, open, half_open
    last_failure_time: float = 0.0
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: float = 30.0

    def record_failure(self) -> None:
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"

    def record_success(self) -> None:
        """Record a successful call."""
        if self.state == "half_open":
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._reset()
        else:
            # Reset failure count on success in closed state
            self.failure_count = 0

    def can_execute(self) -> bool:
        """Check if a call is allowed."""
        if self.state == "closed":
            return True
        if self.state == "open":
            elapsed = time.monotonic() - self.last_failure_time
            if elapsed >= self.timeout_seconds:
                self.state = "half_open"
                self.success_count = 0
                return True
            return False
        # half_open: allow one test request
        return True

    def _reset(self) -> None:
        """Reset to closed state."""
        self.failure_count = 0
        self.success_count = 0
        self.state = "closed"
        self.last_failure_time = 0.0


# =============================================================
# LLM ROUTER
# =============================================================

# Escalation chain: tier → next higher tier
ESCALATION_CHAIN: dict[ModelTier, ModelTier | None] = {
    ModelTier.HAIKU: ModelTier.SONNET,
    ModelTier.SONNET: ModelTier.OPUS,
    ModelTier.OPUS: None,
}

# Confidence thresholds per tier — below this triggers escalation
CONFIDENCE_THRESHOLDS: dict[ModelTier, float] = {
    ModelTier.HAIKU: 0.7,
    ModelTier.SONNET: 0.6,
    ModelTier.OPUS: 0.5,
}


class LLMRouter:
    """Tiered intelligence router.

    Routes requests to Haiku/Sonnet/Opus based on heuristic complexity
    classification. Supports forced model override, escalation on low
    confidence, circuit breakers per provider tier, and a multi-provider
    registry for targeting specific backends (Anthropic, Oracle, LM Studio, Ollama).
    """

    def __init__(
        self,
        provider: LLMProvider,
        settings: Settings | None = None,
    ) -> None:
        self._provider = provider
        self._settings = settings or get_settings()
        self._circuit_breakers: dict[ModelTier, CircuitBreakerState] = {
            ModelTier.OPUS: CircuitBreakerState(),
            ModelTier.SONNET: CircuitBreakerState(),
            ModelTier.HAIKU: CircuitBreakerState(),
        }
        self._model_map: dict[ModelTier, str] = {
            ModelTier.OPUS: self._settings.anthropic.model_opus,
            ModelTier.SONNET: self._settings.anthropic.model_sonnet,
            ModelTier.HAIKU: self._settings.anthropic.model_haiku,
        }
        # Multi-provider registry: name → LLMProvider instance
        self._provider_registry: dict[str, LLMProvider] = {
            "anthropic": provider,
        }

    def register_provider(self, name: str, provider: LLMProvider) -> None:
        """Register an additional LLM provider backend.

        Args:
            name: Provider identifier (e.g. 'ollama', 'lmstudio', 'oracle').
            provider: An LLMProvider implementation.
        """
        self._provider_registry[name] = provider

    def get_provider(self, name: str) -> LLMProvider | None:
        """Look up a registered provider by name."""
        return self._provider_registry.get(name)

    @property
    def registered_providers(self) -> list[str]:
        """Return the names of all registered providers."""
        return list(self._provider_registry.keys())

    def classify(
        self,
        prompt: str,
        context: str | None = None,
        task_type_hint: str | None = None,
    ) -> tuple[ModelTier, ComplexityFeatures, float]:
        """Classify a prompt and determine the routing tier.

        Returns:
            (tier, features, complexity_score)
        """
        features = extract_complexity_features(prompt, context, task_type_hint)
        complexity_score = compute_complexity_score(features)
        tier = determine_tier(complexity_score, features.safety_sensitivity)
        return tier, features, complexity_score

    async def route(
        self,
        prompt: str,
        context: str | None = None,
        task_type_hint: str | None = None,
        force_model: ModelTier | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        provider: str | None = None,
    ) -> tuple[LLMResponse, RoutingDecision]:
        """Route a request to the optimal model tier and return the response.

        Args:
            prompt: The user prompt.
            context: Additional context for the LLM.
            task_type_hint: Optional hint about the task type.
            force_model: Force routing to a specific tier.
            system_prompt: Override system prompt.
            max_tokens: Max tokens for response.
            temperature: Temperature for generation.
            provider: Target a specific registered provider by name
                      (e.g. 'ollama', 'lmstudio', 'oracle'). Falls back
                      to the default Anthropic provider if not specified.

        Returns:
            (LLMResponse, RoutingDecision) tuple.

        Raises:
            CircuitBreakerOpenError: If the target tier's circuit is open.
            EscalationExhaustedError: If all escalation tiers fail.
            RouterError: For other routing failures.
        """
        # Resolve target provider
        target_provider = self._provider
        if provider:
            target_provider = self._provider_registry.get(provider)
            if target_provider is None:
                raise RouterError(
                    f"Unknown provider: '{provider}'. "
                    f"Available: {', '.join(self._provider_registry.keys())}",
                    details={"requested_provider": provider},
                )
        start_time = time.monotonic()

        # Step 1: Classify
        if force_model:
            initial_tier = force_model
            complexity_score = 0.0
            task_type_detected = "forced"
        else:
            initial_tier, features, complexity_score = self.classify(
                prompt, context, task_type_hint
            )
            task_type_detected = features.keyword_tier

        # Step 2: Build full prompt with context
        full_prompt = prompt
        if context:
            full_prompt = f"<context>\n{context}\n</context>\n\n{prompt}"

        # Step 3: Execute with escalation support
        current_tier = initial_tier
        escalated = False
        escalation_reason: str | None = None
        max_escalations = 1

        for attempt in range(max_escalations + 1):
            # Check circuit breaker
            cb = self._circuit_breakers[current_tier]
            if not cb.can_execute():
                # Try escalation on circuit breaker open
                next_tier = ESCALATION_CHAIN.get(current_tier)
                if next_tier:
                    current_tier = next_tier
                    escalated = True
                    escalation_reason = f"circuit_breaker_open_{current_tier.value}"
                    continue
                raise CircuitBreakerOpenError(
                    f"Circuit breaker open for {current_tier.value} and no fallback available",
                    service=current_tier.value,
                )

            # Build config for this tier
            config = LLMConfig(
                model=self._model_map[current_tier],
                tier=current_tier,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
            )

            try:
                response = await target_provider.generate(full_prompt, config)
                cb.record_success()

                # Check confidence threshold for escalation
                # For now, use a simple heuristic: short responses suggest low confidence
                estimated_confidence = self._estimate_confidence(response)
                response.confidence = estimated_confidence

                threshold = CONFIDENCE_THRESHOLDS.get(current_tier, 0.5)
                if estimated_confidence < threshold and attempt < max_escalations:
                    next_tier = ESCALATION_CHAIN.get(current_tier)
                    if next_tier:
                        current_tier = next_tier
                        escalated = True
                        escalation_reason = (
                            f"low_confidence_{estimated_confidence:.2f}_below_{threshold}"
                        )
                        continue

                # Success — return response
                total_latency = int((time.monotonic() - start_time) * 1000)

                routing_decision = RoutingDecision(
                    initial_tier=initial_tier,
                    final_tier=current_tier,
                    escalated=escalated,
                    escalation_reason=escalation_reason,
                    complexity_score=complexity_score,
                    task_type_detected=task_type_detected,
                )

                return response, routing_decision

            except CircuitBreakerOpenError:
                raise
            except Exception as exc:
                cb.record_failure()
                # Try escalation on failure
                next_tier = ESCALATION_CHAIN.get(current_tier)
                if next_tier and attempt < max_escalations:
                    current_tier = next_tier
                    escalated = True
                    escalation_reason = f"provider_error_{type(exc).__name__}"
                    continue
                raise RouterError(
                    f"All routing attempts failed: {exc}",
                    details={"initial_tier": initial_tier.value, "last_error": str(exc)},
                ) from exc

        # Should not reach here, but safety net
        raise EscalationExhaustedError(
            "All escalation tiers exhausted",
            details={"initial_tier": initial_tier.value},
        )

    def _estimate_confidence(self, response: LLMResponse) -> float:
        """Estimate confidence from response characteristics.

        Simple heuristic: longer, more detailed responses suggest higher confidence.
        This will be replaced with ML-based confidence in Phase 5.
        """
        text = response.text
        if not text:
            return 0.0

        # Base confidence from response length
        length_score = min(1.0, len(text) / 500.0)

        # Bonus for structured content (lists, headers, code blocks)
        structure_bonus = 0.0
        if re.search(r"^\s*[-*]\s", text, re.MULTILINE):
            structure_bonus += 0.1
        if re.search(r"^#+\s", text, re.MULTILINE):
            structure_bonus += 0.1
        if "```" in text:
            structure_bonus += 0.1

        # Penalty for uncertainty markers
        uncertainty_penalty = 0.0
        uncertainty_phrases = [
            "i'm not sure", "i don't know", "it's unclear",
            "i cannot determine", "insufficient information",
        ]
        for phrase in uncertainty_phrases:
            if phrase in text.lower():
                uncertainty_penalty += 0.15

        confidence = min(1.0, max(0.0, length_score + structure_bonus - uncertainty_penalty))
        return round(confidence, 2)

    def get_circuit_breaker_states(self) -> dict[str, str]:
        """Return current circuit breaker states for monitoring."""
        return {
            tier.value: cb.state
            for tier, cb in self._circuit_breakers.items()
        }
