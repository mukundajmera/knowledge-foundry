"""Knowledge Foundry — Self-Healing System.

Monitors system health signals and applies automated remediations.
Per Phase 8.1 §6.2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────────────────────

class HealthIssue(str, Enum):
    HIGH_LATENCY = "high_latency"
    LOW_QUALITY = "low_quality"
    HIGH_COST = "high_cost"
    HIGH_ERROR_RATE = "high_error_rate"
    LOW_CACHE_HIT = "low_cache_hit"
    NONE = "none"


class RemediationAction(str, Enum):
    SCALE_UP = "scale_up_instances"
    INCREASE_CACHE_TTL = "increase_cache_ttl"
    CONSERVATIVE_MODE = "switch_to_conservative_mode"  # More Opus
    AGGRESSIVE_CACHE = "enable_aggressive_caching"
    ROUTE_TO_HAIKU = "route_more_to_haiku"
    ALERT_TEAM = "alert_team"
    NO_ACTION = "no_action"


@dataclass
class HealthSignal:
    """Current system health snapshot."""

    latency_p95_ms: float = 0.0
    error_rate: float = 0.0
    avg_ragas_faithfulness: float = 1.0
    avg_cost_per_query: float = 0.0
    cache_hit_rate: float = 1.0

    def detect_issue(self) -> HealthIssue:
        """Identify the most critical issue."""
        # Priority order: errors > latency > quality > cost > cache
        if self.error_rate > 0.05:
            return HealthIssue.HIGH_ERROR_RATE
        if self.latency_p95_ms > 500:
            return HealthIssue.HIGH_LATENCY
        if self.avg_ragas_faithfulness < 0.85:
            return HealthIssue.LOW_QUALITY
        if self.avg_cost_per_query > 0.10:
            return HealthIssue.HIGH_COST
        if self.cache_hit_rate < 0.30:
            return HealthIssue.LOW_CACHE_HIT
        return HealthIssue.NONE


@dataclass
class RemediationRecord:
    """Record of an applied remediation."""

    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    issue: HealthIssue = HealthIssue.NONE
    actions_taken: list[RemediationAction] = field(default_factory=list)
    resolved: bool = False
    details: str = ""


# ──────────────────────────────────────────────────────────────
# Self-Healing Engine
# ──────────────────────────────────────────────────────────────

class SelfHealingSystem:
    """Monitors health signals and applies automated fixes.

    Strategies:
    - high_latency → scale up + increase cache TTL
    - low_quality → conservative mode (more Opus) + alert team
    - high_cost → aggressive caching + route to Haiku
    - high_error_rate → scale up + alert team
    - low_cache_hit → increase cache TTL + aggressive caching
    """

    # Map issues to remediation strategies
    STRATEGIES: dict[HealthIssue, list[RemediationAction]] = {
        HealthIssue.HIGH_LATENCY: [
            RemediationAction.SCALE_UP,
            RemediationAction.INCREASE_CACHE_TTL,
        ],
        HealthIssue.LOW_QUALITY: [
            RemediationAction.CONSERVATIVE_MODE,
            RemediationAction.ALERT_TEAM,
        ],
        HealthIssue.HIGH_COST: [
            RemediationAction.AGGRESSIVE_CACHE,
            RemediationAction.ROUTE_TO_HAIKU,
        ],
        HealthIssue.HIGH_ERROR_RATE: [
            RemediationAction.SCALE_UP,
            RemediationAction.ALERT_TEAM,
        ],
        HealthIssue.LOW_CACHE_HIT: [
            RemediationAction.INCREASE_CACHE_TTL,
            RemediationAction.AGGRESSIVE_CACHE,
        ],
    }

    # Thresholds for issue detection
    THRESHOLDS = {
        "latency_p95_ms": 500,
        "error_rate": 0.05,
        "avg_ragas_faithfulness": 0.85,
        "avg_cost_per_query": 0.10,
        "cache_hit_rate": 0.30,
    }

    def __init__(self) -> None:
        self._records: list[RemediationRecord] = []
        self._action_handlers: dict[RemediationAction, Callable[[], None]] = {}

        # Internal state for model routing and caching
        self._cache_ttl_multiplier: float = 1.0
        self._model_routing_mode: str = "balanced"  # balanced / conservative / haiku_first
        self._scale_factor: int = 1  # Number of scale-up actions taken

    @property
    def records(self) -> list[RemediationRecord]:
        return list(self._records)

    @property
    def cache_ttl_multiplier(self) -> float:
        return self._cache_ttl_multiplier

    @property
    def model_routing_mode(self) -> str:
        return self._model_routing_mode

    @property
    def scale_factor(self) -> int:
        return self._scale_factor

    def register_handler(
        self, action: RemediationAction, handler: Callable[[], None]
    ) -> None:
        """Register a custom handler for a remediation action."""
        self._action_handlers[action] = handler

    def monitor_and_heal(self, signal: HealthSignal) -> RemediationRecord:
        """Analyze health signal and apply remediation if needed."""
        issue = signal.detect_issue()

        if issue == HealthIssue.NONE:
            return RemediationRecord(
                issue=HealthIssue.NONE,
                actions_taken=[RemediationAction.NO_ACTION],
                resolved=True,
                details="All systems healthy",
            )

        actions = self.STRATEGIES.get(issue, [])
        record = RemediationRecord(issue=issue, actions_taken=actions)

        logger.warning(
            "Health issue detected: %s — applying %d remediations",
            issue.value,
            len(actions),
        )

        for action in actions:
            self._apply_action(action)

        record.resolved = True
        record.details = f"Applied {len(actions)} actions for {issue.value}"
        self._records.append(record)

        return record

    def _apply_action(self, action: RemediationAction) -> None:
        """Apply a single remediation action."""
        # Use custom handler if registered
        if action in self._action_handlers:
            self._action_handlers[action]()
            logger.info("Applied custom handler for %s", action.value)
            return

        # Built-in handlers
        if action == RemediationAction.SCALE_UP:
            self._scale_factor += 1
            logger.info("Scale-up requested (factor: %d)", self._scale_factor)

        elif action == RemediationAction.INCREASE_CACHE_TTL:
            self._cache_ttl_multiplier = min(self._cache_ttl_multiplier * 1.5, 5.0)
            logger.info("Cache TTL multiplier: %.1f", self._cache_ttl_multiplier)

        elif action == RemediationAction.CONSERVATIVE_MODE:
            self._model_routing_mode = "conservative"
            logger.info("Switched to conservative mode (more Opus)")

        elif action == RemediationAction.AGGRESSIVE_CACHE:
            self._cache_ttl_multiplier = min(self._cache_ttl_multiplier * 2.0, 10.0)
            logger.info("Aggressive caching enabled (TTL multiplier: %.1f)", self._cache_ttl_multiplier)

        elif action == RemediationAction.ROUTE_TO_HAIKU:
            self._model_routing_mode = "haiku_first"
            logger.info("Route-to-Haiku mode enabled")

        elif action == RemediationAction.ALERT_TEAM:
            logger.warning("ALERT: Team notification triggered")

    def get_status(self) -> dict[str, Any]:
        """Return current self-healing system status."""
        return {
            "cache_ttl_multiplier": self._cache_ttl_multiplier,
            "model_routing_mode": self._model_routing_mode,
            "scale_factor": self._scale_factor,
            "total_remediations": len(self._records),
            "last_issue": self._records[-1].issue.value if self._records else "none",
        }

    def reset(self) -> None:
        """Reset all tuning knobs to defaults."""
        self._cache_ttl_multiplier = 1.0
        self._model_routing_mode = "balanced"
        self._scale_factor = 1
        logger.info("Self-healing system reset to defaults")
