"""Anomaly Detector — Z-score based metric anomaly detection.

Maintains a sliding window of historical metric values and flags anomalies
using z-score thresholds. Severity is HIGH for |z| > 4, MEDIUM for |z| > 3.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AnomalySeverity(str, Enum):
    NONE = "none"
    MEDIUM = "medium"  # |z| > 3
    HIGH = "high"  # |z| > 4


@dataclass(frozen=True)
class AnomalyAlert:
    """Record of a detected anomaly."""

    metric_name: str
    current_value: float
    z_score: float
    severity: AnomalySeverity
    mean: float
    std_dev: float
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    recommendation: str = ""


@dataclass
class MetricWindow:
    """Sliding window of historical values for a single metric."""

    values: list[float] = field(default_factory=list)
    max_size: int = 1000

    def add(self, value: float) -> None:
        """Add a value, evicting oldest if at capacity."""
        self.values.append(value)
        if len(self.values) > self.max_size:
            self.values = self.values[-self.max_size :]

    @property
    def count(self) -> int:
        return len(self.values)

    @property
    def mean(self) -> float:
        if not self.values:
            return 0.0
        return sum(self.values) / len(self.values)

    @property
    def std_dev(self) -> float:
        if len(self.values) < 2:
            return 0.0
        m = self.mean
        variance = sum((v - m) ** 2 for v in self.values) / (len(self.values) - 1)
        return math.sqrt(variance)


# ──────────────────────────────────────────────────
# Thresholds (from Phase 6 spec §5.3)
# ──────────────────────────────────────────────────
_Z_MEDIUM_THRESHOLD = 3.0
_Z_HIGH_THRESHOLD = 4.0
_MIN_DATA_POINTS = 10


def _severity_from_zscore(z: float) -> AnomalySeverity:
    """Map absolute z-score to severity."""
    abs_z = abs(z)
    if abs_z > _Z_HIGH_THRESHOLD:
        return AnomalySeverity.HIGH
    if abs_z > _Z_MEDIUM_THRESHOLD:
        return AnomalySeverity.MEDIUM
    return AnomalySeverity.NONE


_METRIC_RECOMMENDATIONS: dict[str, str] = {
    "error_rate": "Check service logs, investigate upstream failures.",
    "latency_p95": "Review slow queries, check database performance.",
    "cache_hit_rate": "Cache may have been flushed or TTLs changed.",
    "cost_per_query": "Check model tier distribution, look for Opus over-routing.",
    "ragas_faithfulness": "Check retrieval quality, review recent document changes.",
    "qps": "Traffic spike or drop — correlate with external events.",
}


class AnomalyDetector:
    """Z-score based anomaly detector for application metrics.

    Usage::

        detector = AnomalyDetector()

        # Feed historical data
        for value in historical_error_rates:
            detector.record("error_rate", value)

        # Check new value
        alert = detector.detect("error_rate", 0.15)
        if alert and alert.severity != AnomalySeverity.NONE:
            notify_oncall(alert)
    """

    def __init__(
        self,
        *,
        z_medium: float = _Z_MEDIUM_THRESHOLD,
        z_high: float = _Z_HIGH_THRESHOLD,
        min_data_points: int = _MIN_DATA_POINTS,
        window_size: int = 1000,
    ) -> None:
        self._z_medium = z_medium
        self._z_high = z_high
        self._min_data_points = min_data_points
        self._window_size = window_size
        self._metrics: dict[str, MetricWindow] = defaultdict(
            lambda: MetricWindow(max_size=self._window_size),
        )
        self._alerts: list[AnomalyAlert] = []

    @property
    def alerts(self) -> list[AnomalyAlert]:
        return list(self._alerts)

    @property
    def tracked_metrics(self) -> list[str]:
        return list(self._metrics.keys())

    def record(self, metric_name: str, value: float) -> None:
        """Record a metric value into the sliding window."""
        self._metrics[metric_name].add(value)

    def record_batch(self, metric_name: str, values: list[float]) -> None:
        """Record multiple values at once."""
        for v in values:
            self._metrics[metric_name].add(v)

    def get_stats(self, metric_name: str) -> dict[str, Any]:
        """Get current statistics for a metric."""
        window = self._metrics.get(metric_name)
        if window is None:
            return {"count": 0, "mean": 0.0, "std_dev": 0.0}
        return {
            "count": window.count,
            "mean": window.mean,
            "std_dev": window.std_dev,
            "min": min(window.values) if window.values else 0.0,
            "max": max(window.values) if window.values else 0.0,
        }

    def detect(self, metric_name: str, current_value: float) -> AnomalyAlert | None:
        """Check if a current metric value is anomalous.

        Computes z-score against the historical window. Returns an alert
        if the z-score exceeds thresholds, or None if normal.

        The value is always recorded into the window after detection.

        Args:
            metric_name: Name of the metric to check.
            current_value: The current observed value.

        Returns:
            AnomalyAlert if anomalous, None otherwise.
        """
        window = self._metrics[metric_name]

        # Not enough data to detect anomalies
        if window.count < self._min_data_points:
            window.add(current_value)
            return None

        mean = window.mean
        std = window.std_dev

        # Avoid division by zero for constant metrics
        if std < 1e-10:
            window.add(current_value)
            if abs(current_value - mean) < 1e-10:
                return None
            # Any deviation from a constant is anomalous
            z_score = float("inf") if current_value != mean else 0.0
        else:
            z_score = (current_value - mean) / std

        severity = _severity_from_zscore(z_score)

        # Record the value after detection
        window.add(current_value)

        if severity == AnomalySeverity.NONE:
            return None

        recommendation = _METRIC_RECOMMENDATIONS.get(
            metric_name,
            f"Investigate metric '{metric_name}' — unusual value detected.",
        )

        alert = AnomalyAlert(
            metric_name=metric_name,
            current_value=current_value,
            z_score=z_score,
            severity=severity,
            mean=mean,
            std_dev=std,
            recommendation=recommendation,
        )
        self._alerts.append(alert)

        logger.warning(
            "Anomaly: %s=%.4f z=%.2f severity=%s",
            metric_name,
            current_value,
            z_score,
            severity.value,
        )
        return alert

    def detect_batch(
        self,
        metrics: dict[str, float],
    ) -> list[AnomalyAlert]:
        """Check multiple metrics at once, returning any alerts."""
        alerts = []
        for name, value in metrics.items():
            alert = self.detect(name, value)
            if alert is not None:
                alerts.append(alert)
        return alerts
