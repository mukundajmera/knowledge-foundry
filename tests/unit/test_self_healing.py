"""Tests for SelfHealingSystem — issue detection, remediation, status."""

from __future__ import annotations

from src.improvement.self_healing import (
    HealthIssue,
    HealthSignal,
    RemediationAction,
    SelfHealingSystem,
)


class TestHealthSignal:
    def test_no_issue_when_healthy(self) -> None:
        signal = HealthSignal(
            latency_p95_ms=200,
            error_rate=0.001,
            avg_ragas_faithfulness=0.96,
            avg_cost_per_query=0.05,
            cache_hit_rate=0.80,
        )
        assert signal.detect_issue() == HealthIssue.NONE

    def test_detects_high_error_rate(self) -> None:
        signal = HealthSignal(error_rate=0.10)
        assert signal.detect_issue() == HealthIssue.HIGH_ERROR_RATE

    def test_detects_high_latency(self) -> None:
        signal = HealthSignal(latency_p95_ms=700)
        assert signal.detect_issue() == HealthIssue.HIGH_LATENCY

    def test_detects_low_quality(self) -> None:
        signal = HealthSignal(avg_ragas_faithfulness=0.70)
        assert signal.detect_issue() == HealthIssue.LOW_QUALITY

    def test_detects_high_cost(self) -> None:
        signal = HealthSignal(avg_cost_per_query=0.15)
        assert signal.detect_issue() == HealthIssue.HIGH_COST

    def test_detects_low_cache(self) -> None:
        signal = HealthSignal(cache_hit_rate=0.10)
        assert signal.detect_issue() == HealthIssue.LOW_CACHE_HIT

    def test_priority_error_over_latency(self) -> None:
        """Errors have higher priority than latency."""
        signal = HealthSignal(error_rate=0.10, latency_p95_ms=700)
        assert signal.detect_issue() == HealthIssue.HIGH_ERROR_RATE


class TestSelfHealingSystem:
    def test_healthy_no_action(self) -> None:
        sys = SelfHealingSystem()
        signal = HealthSignal()  # All defaults are healthy
        record = sys.monitor_and_heal(signal)
        assert record.resolved is True
        assert RemediationAction.NO_ACTION in record.actions_taken

    def test_high_latency_scales_up(self) -> None:
        sys = SelfHealingSystem()
        signal = HealthSignal(latency_p95_ms=700)
        record = sys.monitor_and_heal(signal)
        assert RemediationAction.SCALE_UP in record.actions_taken
        assert sys.scale_factor == 2

    def test_high_latency_increases_cache(self) -> None:
        sys = SelfHealingSystem()
        signal = HealthSignal(latency_p95_ms=700)
        sys.monitor_and_heal(signal)
        assert sys.cache_ttl_multiplier > 1.0

    def test_low_quality_conservative_mode(self) -> None:
        sys = SelfHealingSystem()
        signal = HealthSignal(avg_ragas_faithfulness=0.70)
        sys.monitor_and_heal(signal)
        assert sys.model_routing_mode == "conservative"

    def test_high_cost_routes_to_haiku(self) -> None:
        sys = SelfHealingSystem()
        signal = HealthSignal(avg_cost_per_query=0.15)
        sys.monitor_and_heal(signal)
        assert sys.model_routing_mode == "haiku_first"

    def test_records_remediation(self) -> None:
        sys = SelfHealingSystem()
        signal = HealthSignal(error_rate=0.10)
        sys.monitor_and_heal(signal)
        assert len(sys.records) == 1
        assert sys.records[0].issue == HealthIssue.HIGH_ERROR_RATE

    def test_custom_handler(self) -> None:
        sys = SelfHealingSystem()
        called = []
        sys.register_handler(
            RemediationAction.SCALE_UP,
            lambda: called.append("scaled"),
        )
        signal = HealthSignal(latency_p95_ms=700)
        sys.monitor_and_heal(signal)
        assert "scaled" in called

    def test_reset(self) -> None:
        sys = SelfHealingSystem()
        signal = HealthSignal(latency_p95_ms=700)
        sys.monitor_and_heal(signal)
        sys.reset()
        assert sys.cache_ttl_multiplier == 1.0
        assert sys.model_routing_mode == "balanced"
        assert sys.scale_factor == 1

    def test_get_status(self) -> None:
        sys = SelfHealingSystem()
        status = sys.get_status()
        assert status["cache_ttl_multiplier"] == 1.0
        assert status["model_routing_mode"] == "balanced"
        assert status["total_remediations"] == 0
