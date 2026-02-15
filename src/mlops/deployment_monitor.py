"""Deployment Monitor — Automated rollback and feature flag management.

Watches error rate, p95 latency, and RAGAS faithfulness after a deployment.
If any metric breaches its threshold during the observation window, triggers
an automatic rollback. Includes a tenant-scoped feature flag manager for
canary and gradual rollouts.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────────


class DeploymentStatus(str, Enum):
    MONITORING = "monitoring"
    STABLE = "stable"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class RollbackReason(str, Enum):
    HIGH_ERROR_RATE = "High error rate (>5%)"
    HIGH_LATENCY = "High p95 latency (>1000ms)"
    QUALITY_REGRESSION = "RAGAS faithfulness below 0.90"
    MANUAL = "Manual rollback"


@dataclass(frozen=True)
class DeploymentMetrics:
    """Snapshot of deployment health metrics."""

    error_rate: float = 0.0
    latency_p95: float = 0.0
    ragas_faithfulness: float = 1.0
    requests_total: int = 0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


@dataclass(frozen=True)
class RollbackEvent:
    """Record of a rollback action."""

    version: str
    reason: RollbackReason
    metrics_at_rollback: DeploymentMetrics
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    previous_version: str = ""


@dataclass
class MonitorResult:
    """Result of a deployment monitoring session."""

    version: str
    status: DeploymentStatus
    checks_performed: int = 0
    duration_seconds: float = 0.0
    rollback_event: RollbackEvent | None = None
    metrics_history: list[DeploymentMetrics] = field(default_factory=list)


# ──────────────────────────────────────────────────
# Rollback thresholds (from Phase 6 spec §4.3)
# ──────────────────────────────────────────────────
_ERROR_RATE_THRESHOLD = 0.05
_LATENCY_P95_THRESHOLD = 1000  # ms
_RAGAS_FAITHFULNESS_MIN = 0.90


class DeploymentMonitor:
    """Watches deployment metrics and triggers rollback if thresholds breached.

    Usage::

        monitor = DeploymentMonitor(
            metrics_fn=get_current_metrics,
            rollback_fn=kubectl_switch_version,
        )
        result = monitor.monitor_deployment("v1.3.0", duration_seconds=600)
        if result.status == DeploymentStatus.ROLLED_BACK:
            alert_team(result.rollback_event)
    """

    def __init__(
        self,
        *,
        metrics_fn: Any = None,
        rollback_fn: Any = None,
        error_rate_threshold: float = _ERROR_RATE_THRESHOLD,
        latency_p95_threshold: float = _LATENCY_P95_THRESHOLD,
        ragas_min: float = _RAGAS_FAITHFULNESS_MIN,
    ) -> None:
        self._metrics_fn = metrics_fn
        self._rollback_fn = rollback_fn
        self._error_threshold = error_rate_threshold
        self._latency_threshold = latency_p95_threshold
        self._ragas_min = ragas_min
        self._rollback_history: list[RollbackEvent] = []

    @property
    def rollback_history(self) -> list[RollbackEvent]:
        return list(self._rollback_history)

    def check_metrics(self, metrics: DeploymentMetrics) -> RollbackReason | None:
        """Check a metrics snapshot against thresholds.

        Returns the reason for rollback, or None if all metrics are healthy.
        """
        if metrics.error_rate > self._error_threshold:
            return RollbackReason.HIGH_ERROR_RATE
        if metrics.latency_p95 > self._latency_threshold:
            return RollbackReason.HIGH_LATENCY
        if metrics.ragas_faithfulness < self._ragas_min:
            return RollbackReason.QUALITY_REGRESSION
        return None

    def trigger_rollback(
        self,
        version: str,
        reason: RollbackReason,
        metrics: DeploymentMetrics,
        *,
        previous_version: str = "",
    ) -> RollbackEvent:
        """Execute rollback and record the event."""
        event = RollbackEvent(
            version=version,
            reason=reason,
            metrics_at_rollback=metrics,
            previous_version=previous_version,
        )
        self._rollback_history.append(event)

        if self._rollback_fn is not None:
            self._rollback_fn(previous_version)

        logger.warning(
            "ROLLBACK triggered for %s: %s (error=%.3f, p95=%.0fms, faith=%.3f)",
            version,
            reason.value,
            metrics.error_rate,
            metrics.latency_p95,
            metrics.ragas_faithfulness,
        )
        return event

    def monitor_deployment(
        self,
        version: str,
        *,
        duration_seconds: int = 600,
        check_interval: int = 60,
        previous_version: str = "",
    ) -> MonitorResult:
        """Monitor a deployment for the specified duration.

        Polls metrics at each interval. If any threshold is breached,
        triggers rollback and returns immediately.

        Args:
            version: The newly deployed version string.
            duration_seconds: How long to monitor (default 10 min).
            check_interval: Seconds between metric checks.
            previous_version: Version to roll back to if needed.

        Returns:
            MonitorResult with status, metrics history, and rollback event if any.
        """
        if self._metrics_fn is None:
            raise RuntimeError("No metrics_fn configured")

        result = MonitorResult(version=version, status=DeploymentStatus.MONITORING)
        start = time.monotonic()
        elapsed = 0.0

        while elapsed < duration_seconds:
            metrics = self._metrics_fn(version)
            result.metrics_history.append(metrics)
            result.checks_performed += 1

            reason = self.check_metrics(metrics)
            if reason is not None:
                event = self.trigger_rollback(
                    version,
                    reason,
                    metrics,
                    previous_version=previous_version,
                )
                result.status = DeploymentStatus.ROLLED_BACK
                result.rollback_event = event
                result.duration_seconds = time.monotonic() - start
                return result

            time.sleep(check_interval)
            elapsed = time.monotonic() - start

        result.status = DeploymentStatus.STABLE
        result.duration_seconds = time.monotonic() - start
        logger.info("Deployment %s stable after %.0fs", version, result.duration_seconds)
        return result


# ──────────────────────────────────────────────────
# Feature Flags
# ──────────────────────────────────────────────────


@dataclass
class FeatureFlag:
    """A feature flag scoped to tenants."""

    name: str
    enabled_tenants: set[str] = field(default_factory=set)
    global_enabled: bool = False
    rollout_percentage: float = 0.0  # 0.0–1.0
    description: str = ""


class FeatureFlagManager:
    """Tenant-scoped feature flag management for canary/gradual rollouts.

    Usage::

        flags = FeatureFlagManager()
        flags.register("hybrid_vectorcypher", description="Use hybrid retrieval")
        flags.enable_for_tenant("hybrid_vectorcypher", "tenant-42")

        if flags.is_enabled("hybrid_vectorcypher", tenant_id="tenant-42"):
            strategy = "hybrid"
    """

    def __init__(self) -> None:
        self._flags: dict[str, FeatureFlag] = {}

    @property
    def flags(self) -> dict[str, FeatureFlag]:
        return dict(self._flags)

    def register(
        self,
        name: str,
        *,
        description: str = "",
        global_enabled: bool = False,
        rollout_percentage: float = 0.0,
    ) -> FeatureFlag:
        """Register a new feature flag."""
        flag = FeatureFlag(
            name=name,
            description=description,
            global_enabled=global_enabled,
            rollout_percentage=rollout_percentage,
        )
        self._flags[name] = flag
        return flag

    def enable_for_tenant(self, flag_name: str, tenant_id: str) -> None:
        """Enable a feature for a specific tenant."""
        if flag_name not in self._flags:
            raise KeyError(f"Unknown flag: {flag_name}")
        self._flags[flag_name].enabled_tenants.add(tenant_id)

    def disable_for_tenant(self, flag_name: str, tenant_id: str) -> None:
        """Disable a feature for a specific tenant."""
        if flag_name not in self._flags:
            raise KeyError(f"Unknown flag: {flag_name}")
        self._flags[flag_name].enabled_tenants.discard(tenant_id)

    def set_global(self, flag_name: str, *, enabled: bool) -> None:
        """Enable or disable a feature globally."""
        if flag_name not in self._flags:
            raise KeyError(f"Unknown flag: {flag_name}")
        self._flags[flag_name].global_enabled = enabled

    def is_enabled(
        self,
        flag_name: str,
        *,
        tenant_id: str = "",
    ) -> bool:
        """Check if a feature is enabled for the given tenant.

        Priority: global_enabled > tenant whitelist > rollout_percentage.
        """
        if flag_name not in self._flags:
            return False

        flag = self._flags[flag_name]
        if flag.global_enabled:
            return True
        if tenant_id and tenant_id in flag.enabled_tenants:
            return True
        # Rollout percentage — deterministic hash based on tenant_id
        if flag.rollout_percentage > 0 and tenant_id:
            bucket = hash(f"{flag_name}:{tenant_id}") % 100
            return bucket < (flag.rollout_percentage * 100)
        return False
