"""Data Drift Monitor — Detects distribution shift between production queries and reference data.

Uses KL divergence and Population Stability Index (PSI) to detect semantic
drift in user queries. When drift exceeds thresholds, alerts are generated
so the team can update the golden dataset and retrieval strategy.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class DriftSeverity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class DriftReport:
    """Result of a drift detection run."""

    kl_divergence: float
    psi: float
    drift_detected: bool
    severity: DriftSeverity
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    recommendation: str = ""
    details: dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────────
# Thresholds (from Phase 6 spec)
# ──────────────────────────────────────────────────
_KL_THRESHOLD = 0.15
_PSI_LOW = 0.1
_PSI_MEDIUM = 0.2
_PSI_HIGH = 0.25


def _to_distribution(values: list[float], n_bins: int = 50) -> np.ndarray:
    """Convert raw values into a normalised probability distribution."""
    hist, _ = np.histogram(values, bins=n_bins, density=False)
    hist = hist.astype(np.float64) + 1e-10  # Laplace smoothing
    return hist / hist.sum()


def calculate_kl_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """Compute KL(P || Q) between two discrete distributions.

    Both arrays must be the same length and sum to ~1.
    """
    if len(p) != len(q):
        raise ValueError(f"Distribution lengths differ: {len(p)} vs {len(q)}")

    kl = 0.0
    for pi, qi in zip(p, q):
        if pi > 0:
            kl += pi * math.log(pi / qi)
    return kl


def calculate_psi(expected: np.ndarray, actual: np.ndarray) -> float:
    """Population Stability Index — symmetric divergence measure.

    PSI < 0.10 → no significant change
    PSI 0.10–0.25 → moderate change
    PSI > 0.25 → significant change
    """
    if len(expected) != len(actual):
        raise ValueError(
            f"Distribution lengths differ: {len(expected)} vs {len(actual)}",
        )
    psi = 0.0
    for e, a in zip(expected, actual):
        psi += (a - e) * math.log(a / e)
    return psi


def _severity_from_metrics(kl: float, psi: float) -> DriftSeverity:
    """Map KL + PSI to a human-readable severity level."""
    if kl > _KL_THRESHOLD and psi > _PSI_HIGH:
        return DriftSeverity.HIGH
    if kl > _KL_THRESHOLD or psi > _PSI_MEDIUM:
        return DriftSeverity.MEDIUM
    if psi > _PSI_LOW:
        return DriftSeverity.LOW
    return DriftSeverity.NONE


def _recommendation(severity: DriftSeverity) -> str:
    """Generate actionable recommendation based on drift severity."""
    recommendations = {
        DriftSeverity.NONE: "No action needed — distributions are stable.",
        DriftSeverity.LOW: "Monitor closely. Consider reviewing edge queries.",
        DriftSeverity.MEDIUM: (
            "Review golden dataset and update retrieval strategy. "
            "Check for new topic clusters in production queries."
        ),
        DriftSeverity.HIGH: (
            "URGENT: Significant drift detected. "
            "Immediately review golden dataset, update embeddings, "
            "and consider re-indexing documents."
        ),
    }
    return recommendations[severity]


class DataDriftMonitor:
    """Detects semantic drift between production queries and reference data.

    Usage::

        monitor = DataDriftMonitor()
        report = monitor.detect_drift(
            production_embeddings=[...],   # recent query embedding norms
            reference_embeddings=[...],    # golden dataset embedding norms
        )
        if report.drift_detected:
            alert_team(report)
    """

    def __init__(
        self,
        *,
        kl_threshold: float = _KL_THRESHOLD,
        psi_threshold: float = _PSI_MEDIUM,
        n_bins: int = 50,
    ) -> None:
        self._kl_threshold = kl_threshold
        self._psi_threshold = psi_threshold
        self._n_bins = n_bins
        self._history: list[DriftReport] = []

    @property
    def history(self) -> list[DriftReport]:
        """Return past drift detection results."""
        return list(self._history)

    def detect_drift(
        self,
        production_values: list[float],
        reference_values: list[float],
    ) -> DriftReport:
        """Run drift detection on two sets of scalar values.

        Typically these are embedding norms, cosine similarities to centroid,
        or other scalar projections of high-dimensional embedding vectors.

        Args:
            production_values: Recent production query metrics.
            reference_values: Reference (golden dataset) metrics.

        Returns:
            DriftReport with KL divergence, PSI, severity, and recommendation.
        """
        if len(production_values) < 2 or len(reference_values) < 2:
            raise ValueError("Need at least 2 values in each distribution")

        prod_dist = _to_distribution(production_values, self._n_bins)
        ref_dist = _to_distribution(reference_values, self._n_bins)

        kl = calculate_kl_divergence(ref_dist, prod_dist)
        psi = calculate_psi(ref_dist, prod_dist)

        drift_detected = kl > self._kl_threshold or psi > self._psi_threshold
        severity = _severity_from_metrics(kl, psi)

        report = DriftReport(
            kl_divergence=kl,
            psi=psi,
            drift_detected=drift_detected,
            severity=severity,
            recommendation=_recommendation(severity),
            details={
                "production_count": len(production_values),
                "reference_count": len(reference_values),
                "n_bins": self._n_bins,
                "kl_threshold": self._kl_threshold,
                "psi_threshold": self._psi_threshold,
            },
        )

        self._history.append(report)

        if drift_detected:
            logger.warning(
                "Drift detected: KL=%.4f PSI=%.4f severity=%s",
                kl,
                psi,
                severity.value,
            )
        else:
            logger.info("No drift: KL=%.4f PSI=%.4f", kl, psi)

        return report
