"""Knowledge Foundry — Safety Enforcement Engine.

Evaluates requests and responses against attached SafetyPolicies,
recording violations and applying configured actions (block/flag/transform).
"""

from __future__ import annotations

import logging
from uuid import UUID

from src.governance.models import (
    BlockedCategory,
    SafetyAction,
    SafetyPolicy,
    SafetyRule,
    SafetyViolation,
    ViolationSeverity,
)

logger = logging.getLogger(__name__)

# Keyword-based detection patterns for each blocked category.
# In production these would be backed by ML classifiers.
_CATEGORY_KEYWORDS: dict[BlockedCategory, list[str]] = {
    BlockedCategory.TOXICITY: ["hate", "kill", "violent", "abuse"],
    BlockedCategory.PII_LEAK: ["ssn", "social security", "credit card", "passport number"],
    BlockedCategory.PROMPT_INJECTION: ["ignore previous", "disregard instructions", "system prompt"],
    BlockedCategory.DATA_EXFILTRATION: ["send to external", "exfiltrate", "upload data to"],
}

_SEVERITY_MAP: dict[SafetyAction, ViolationSeverity] = {
    SafetyAction.BLOCK: ViolationSeverity.HIGH,
    SafetyAction.FLAG: ViolationSeverity.MEDIUM,
    SafetyAction.TRANSFORM: ViolationSeverity.MEDIUM,
    SafetyAction.LOG_ONLY: ViolationSeverity.LOW,
}


class SafetyEngine:
    """Enforces safety policies on retrieval requests and responses.

    Typical usage::

        engine = SafetyEngine(policies=[my_policy])
        result = engine.check_request(query="some user query")
        if result.blocked:
            return "Request blocked due to safety policy."
    """

    def __init__(self, policies: list[SafetyPolicy] | None = None) -> None:
        self._policies: list[SafetyPolicy] = policies or []
        self._violations: list[SafetyViolation] = []

    @property
    def violations(self) -> list[SafetyViolation]:
        """Return all recorded violations."""
        return list(self._violations)

    def add_policy(self, policy: SafetyPolicy) -> None:
        """Register a safety policy."""
        self._policies.append(policy)

    def check_request(
        self,
        query: str,
        knowledge_base_id: UUID | None = None,
        client_id: UUID | None = None,
    ) -> SafetyCheckResult:
        """Check an incoming query against all active policies.

        Returns a result indicating whether the request should be blocked,
        flagged, or allowed through.
        """
        violations: list[SafetyViolation] = []
        should_block = False

        for policy in self._policies:
            if not policy.enabled:
                continue
            # Scope check: policy must match KB or client (or be global)
            if policy.knowledge_base_id and policy.knowledge_base_id != knowledge_base_id:
                continue
            if policy.client_id and policy.client_id != client_id:
                continue

            for rule in policy.get_active_rules():
                confidence = self._evaluate_rule(rule, query)
                if confidence >= rule.threshold:
                    violation = SafetyViolation(
                        policy_id=policy.policy_id,
                        rule_id=rule.rule_id,
                        category=rule.category,
                        severity=_SEVERITY_MAP.get(rule.action, ViolationSeverity.MEDIUM),
                        action_taken=rule.action,
                        query=query,
                        confidence=confidence,
                        blocked=rule.action == SafetyAction.BLOCK,
                        knowledge_base_id=knowledge_base_id,
                        client_id=client_id,
                    )
                    violations.append(violation)
                    if rule.action == SafetyAction.BLOCK:
                        should_block = True

        self._violations.extend(violations)
        return SafetyCheckResult(
            allowed=not should_block,
            blocked=should_block,
            violations=violations,
        )

    def check_response(
        self,
        response_text: str,
        query: str = "",
        knowledge_base_id: UUID | None = None,
        client_id: UUID | None = None,
    ) -> SafetyCheckResult:
        """Check a generated response against safety policies.

        Evaluates the response for content violations and applies
        configured actions (block, flag, transform).
        """
        violations: list[SafetyViolation] = []
        should_block = False

        for policy in self._policies:
            if not policy.enabled:
                continue
            if policy.knowledge_base_id and policy.knowledge_base_id != knowledge_base_id:
                continue
            if policy.client_id and policy.client_id != client_id:
                continue

            for rule in policy.get_active_rules():
                confidence = self._evaluate_rule(rule, response_text)
                if confidence >= rule.threshold:
                    violation = SafetyViolation(
                        policy_id=policy.policy_id,
                        rule_id=rule.rule_id,
                        category=rule.category,
                        severity=_SEVERITY_MAP.get(rule.action, ViolationSeverity.MEDIUM),
                        action_taken=rule.action,
                        query=query,
                        response_snippet=response_text[:200],
                        confidence=confidence,
                        blocked=rule.action == SafetyAction.BLOCK,
                        knowledge_base_id=knowledge_base_id,
                        client_id=client_id,
                    )
                    violations.append(violation)
                    if rule.action == SafetyAction.BLOCK:
                        should_block = True

        self._violations.extend(violations)
        return SafetyCheckResult(
            allowed=not should_block,
            blocked=should_block,
            violations=violations,
        )

    def _evaluate_rule(self, rule: SafetyRule, text: str) -> float:
        """Evaluate a safety rule against text content.

        Uses keyword matching as a baseline; in production this would
        delegate to ML classifiers per category.
        """
        text_lower = text.lower()
        keywords = _CATEGORY_KEYWORDS.get(rule.category, [])
        if not keywords:
            return 0.0
        matches = sum(1 for kw in keywords if kw in text_lower)
        if matches == 0:
            return 0.0
        return min(1.0, matches / len(keywords) + 0.3)


class SafetyCheckResult:
    """Result of a safety check operation."""

    def __init__(
        self,
        allowed: bool = True,
        blocked: bool = False,
        violations: list[SafetyViolation] | None = None,
    ) -> None:
        self.allowed = allowed
        self.blocked = blocked
        self.violations = violations or []
