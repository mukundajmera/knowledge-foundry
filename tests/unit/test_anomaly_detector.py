"""Tests for AnomalyDetector — src/mlops/anomaly_detector.py."""

from __future__ import annotations

import pytest

from src.mlops.anomaly_detector import (
    AnomalyAlert,
    AnomalyDetector,
    AnomalySeverity,
    MetricWindow,
)


# ──────────────────────────────────────────────────
# MetricWindow
# ──────────────────────────────────────────────────
class TestMetricWindow:
    def test_add_and_count(self):
        w = MetricWindow()
        w.add(1.0)
        w.add(2.0)
        assert w.count == 2

    def test_mean(self):
        w = MetricWindow()
        for v in [10.0, 20.0, 30.0]:
            w.add(v)
        assert w.mean == pytest.approx(20.0)

    def test_std_dev(self):
        w = MetricWindow()
        for v in [10.0, 10.0, 10.0]:
            w.add(v)
        assert w.std_dev == pytest.approx(0.0)

    def test_max_size_eviction(self):
        w = MetricWindow(max_size=3)
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            w.add(v)
        assert w.count == 3
        assert w.values == [3.0, 4.0, 5.0]

    def test_empty_mean(self):
        w = MetricWindow()
        assert w.mean == 0.0

    def test_single_value_std(self):
        w = MetricWindow()
        w.add(5.0)
        assert w.std_dev == 0.0


# ──────────────────────────────────────────────────
# AnomalyDetector: record + detect
# ──────────────────────────────────────────────────
class TestAnomalyDetector:
    def test_normal_value_no_alert(self):
        det = AnomalyDetector(min_data_points=5)
        for v in [10.0] * 20:
            det.record("metric_a", v)
        alert = det.detect("metric_a", 10.0)
        assert alert is None

    def test_anomalous_value_returns_alert(self):
        det = AnomalyDetector(min_data_points=5)
        # Build history with normal values
        det.record_batch("error_rate", [0.01] * 50)
        # Now inject extreme value
        alert = det.detect("error_rate", 1.0)
        assert alert is not None
        assert alert.severity in (AnomalySeverity.MEDIUM, AnomalySeverity.HIGH)
        assert alert.metric_name == "error_rate"

    def test_too_few_data_points_no_alert(self):
        det = AnomalyDetector(min_data_points=10)
        # Only 5 data points
        det.record_batch("foo", [1.0] * 5)
        alert = det.detect("foo", 100.0)
        assert alert is None

    def test_alerts_accumulate(self):
        det = AnomalyDetector(min_data_points=5)
        det.record_batch("m", [1.0] * 50)
        det.detect("m", 100.0)
        det.detect("m", 200.0)
        # Both should be alerts
        assert len(det.alerts) >= 1

    def test_detect_batch(self):
        det = AnomalyDetector(min_data_points=5)
        det.record_batch("a", [1.0] * 50)
        det.record_batch("b", [100.0] * 50)
        alerts = det.detect_batch({"a": 1.0, "b": 100.0})
        # Normal values → no alerts
        assert len(alerts) == 0

    def test_detect_batch_with_anomaly(self):
        det = AnomalyDetector(min_data_points=5)
        det.record_batch("a", [1.0] * 50)
        det.record_batch("b", [100.0] * 50)
        alerts = det.detect_batch({"a": 1000.0, "b": 100.0})
        assert len(alerts) == 1
        assert alerts[0].metric_name == "a"

    def test_tracked_metrics(self):
        det = AnomalyDetector()
        det.record("latency", 50.0)
        det.record("error_rate", 0.01)
        assert sorted(det.tracked_metrics) == ["error_rate", "latency"]

    def test_get_stats(self):
        det = AnomalyDetector()
        det.record_batch("latency", [10.0, 20.0, 30.0])
        stats = det.get_stats("latency")
        assert stats["count"] == 3
        assert stats["mean"] == pytest.approx(20.0)
        assert stats["min"] == 10.0
        assert stats["max"] == 30.0

    def test_unknown_metric_stats(self):
        det = AnomalyDetector()
        stats = det.get_stats("nonexistent")
        assert stats["count"] == 0

    def test_high_severity_z4(self):
        det = AnomalyDetector(min_data_points=5)
        # Very tight distribution then huge outlier
        det.record_batch("m", [10.0] * 100)
        alert = det.detect("m", 100.0)
        assert alert is not None
        assert alert.severity == AnomalySeverity.HIGH
        assert abs(alert.z_score) > 4

    def test_recommendation_for_known_metric(self):
        det = AnomalyDetector(min_data_points=5)
        det.record_batch("error_rate", [0.01] * 50)
        alert = det.detect("error_rate", 1.0)
        assert alert is not None
        assert "logs" in alert.recommendation.lower() or "upstream" in alert.recommendation.lower()

    def test_recommendation_for_unknown_metric(self):
        det = AnomalyDetector(min_data_points=5)
        det.record_batch("custom_metric", [1.0] * 50)
        alert = det.detect("custom_metric", 100.0)
        assert alert is not None
        assert "custom_metric" in alert.recommendation

    def test_constant_metric_detects_deviation(self):
        det = AnomalyDetector(min_data_points=5)
        det.record_batch("constant", [5.0] * 50)
        alert = det.detect("constant", 5.0)
        assert alert is None
        # Any deviation from constant should be anomalous
        alert2 = det.detect("constant", 6.0)
        assert alert2 is not None
