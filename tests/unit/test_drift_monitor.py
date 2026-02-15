"""Tests for DataDriftMonitor — src/mlops/drift_monitor.py."""

from __future__ import annotations

import math
import random

import numpy as np
import pytest

from src.mlops.drift_monitor import (
    DataDriftMonitor,
    DriftReport,
    DriftSeverity,
    _to_distribution,
    calculate_kl_divergence,
    calculate_psi,
)


# ──────────────────────────────────────────────────
# Helper: deterministic seeds
# ──────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _seed():
    random.seed(42)
    np.random.seed(42)


# ──────────────────────────────────────────────────
# Unit: distribution conversion
# ──────────────────────────────────────────────────
class TestToDistribution:
    def test_sums_to_one(self):
        dist = _to_distribution([1.0, 2.0, 3.0, 4.0, 5.0], n_bins=5)
        assert abs(dist.sum() - 1.0) < 1e-6

    def test_all_positive(self):
        dist = _to_distribution([0.0, 0.0, 0.0], n_bins=3)
        assert all(v > 0 for v in dist)  # Laplace smoothing


# ──────────────────────────────────────────────────
# Unit: KL divergence
# ──────────────────────────────────────────────────
class TestKLDivergence:
    def test_identical_distributions_is_zero(self):
        p = np.array([0.25, 0.25, 0.25, 0.25])
        kl = calculate_kl_divergence(p, p)
        assert abs(kl) < 1e-10

    def test_different_distributions_positive(self):
        p = np.array([0.5, 0.3, 0.1, 0.1])
        q = np.array([0.25, 0.25, 0.25, 0.25])
        kl = calculate_kl_divergence(p, q)
        assert kl > 0

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError, match="lengths differ"):
            calculate_kl_divergence(np.array([0.5, 0.5]), np.array([1.0]))


# ──────────────────────────────────────────────────
# Unit: PSI
# ──────────────────────────────────────────────────
class TestPSI:
    def test_identical_distributions_is_zero(self):
        p = np.array([0.25, 0.25, 0.25, 0.25])
        psi = calculate_psi(p, p)
        assert abs(psi) < 1e-10

    def test_different_distributions_positive(self):
        p = np.array([0.5, 0.3, 0.1, 0.1])
        q = np.array([0.25, 0.25, 0.25, 0.25])
        psi = calculate_psi(p, q)
        assert psi != 0

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError, match="lengths differ"):
            calculate_psi(np.array([0.5, 0.5]), np.array([1.0]))


# ──────────────────────────────────────────────────
# Integration: DataDriftMonitor
# ──────────────────────────────────────────────────
class TestDataDriftMonitor:
    def test_no_drift_same_distribution(self):
        monitor = DataDriftMonitor()
        data = list(np.random.normal(0.5, 0.1, 500))
        report = monitor.detect_drift(data, data)
        assert not report.drift_detected
        assert report.severity == DriftSeverity.NONE

    def test_drift_detected_shifted_distribution(self):
        monitor = DataDriftMonitor()
        ref = list(np.random.normal(0.5, 0.1, 500))
        prod = list(np.random.normal(2.0, 0.3, 500))  # Big shift
        report = monitor.detect_drift(prod, ref)
        assert report.drift_detected
        assert report.severity in (DriftSeverity.MEDIUM, DriftSeverity.HIGH)

    def test_report_fields(self):
        monitor = DataDriftMonitor()
        ref = list(np.random.normal(0.5, 0.1, 100))
        prod = list(np.random.normal(0.5, 0.1, 100))
        report = monitor.detect_drift(prod, ref)
        assert isinstance(report, DriftReport)
        assert report.kl_divergence >= 0
        assert report.timestamp  # non-empty
        assert "production_count" in report.details

    def test_history_accumulates(self):
        monitor = DataDriftMonitor()
        data = list(np.random.normal(0.5, 0.1, 100))
        monitor.detect_drift(data, data)
        monitor.detect_drift(data, data)
        assert len(monitor.history) == 2

    def test_too_few_values_raises(self):
        monitor = DataDriftMonitor()
        with pytest.raises(ValueError, match="at least 2"):
            monitor.detect_drift([1.0], [2.0, 3.0])

    def test_recommendation_non_empty(self):
        monitor = DataDriftMonitor()
        data = list(np.random.normal(0.5, 0.1, 100))
        report = monitor.detect_drift(data, data)
        assert len(report.recommendation) > 0

    def test_custom_thresholds(self):
        monitor = DataDriftMonitor(kl_threshold=100.0, psi_threshold=100.0)
        ref = list(np.random.normal(0.5, 0.1, 200))
        prod = list(np.random.normal(2.0, 0.5, 200))
        report = monitor.detect_drift(prod, ref)
        # Very high thresholds → no drift detected
        assert not report.drift_detected
