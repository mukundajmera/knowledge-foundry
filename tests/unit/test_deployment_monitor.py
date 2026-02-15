"""Tests for DeploymentMonitor + FeatureFlagManager — src/mlops/deployment_monitor.py."""

from __future__ import annotations

import pytest

from src.mlops.deployment_monitor import (
    DeploymentMetrics,
    DeploymentMonitor,
    DeploymentStatus,
    FeatureFlag,
    FeatureFlagManager,
    MonitorResult,
    RollbackEvent,
    RollbackReason,
)


# ──────────────────────────────────────────────────
# DeploymentMonitor: check_metrics
# ──────────────────────────────────────────────────
class TestCheckMetrics:
    def _monitor(self):
        return DeploymentMonitor()

    def test_healthy_metrics_returns_none(self):
        m = DeploymentMetrics(error_rate=0.01, latency_p95=200, ragas_faithfulness=0.95)
        assert self._monitor().check_metrics(m) is None

    def test_high_error_rate(self):
        m = DeploymentMetrics(error_rate=0.10)
        assert self._monitor().check_metrics(m) == RollbackReason.HIGH_ERROR_RATE

    def test_high_latency(self):
        m = DeploymentMetrics(latency_p95=1500)
        assert self._monitor().check_metrics(m) == RollbackReason.HIGH_LATENCY

    def test_low_faithfulness(self):
        m = DeploymentMetrics(ragas_faithfulness=0.80)
        assert self._monitor().check_metrics(m) == RollbackReason.QUALITY_REGRESSION

    def test_borderline_error_rate_ok(self):
        m = DeploymentMetrics(error_rate=0.05)  # Exactly at threshold — not exceeded
        assert self._monitor().check_metrics(m) is None

    def test_borderline_latency_ok(self):
        m = DeploymentMetrics(latency_p95=1000)
        assert self._monitor().check_metrics(m) is None

    def test_borderline_faithfulness_ok(self):
        m = DeploymentMetrics(ragas_faithfulness=0.90)
        assert self._monitor().check_metrics(m) is None


# ──────────────────────────────────────────────────
# DeploymentMonitor: trigger_rollback
# ──────────────────────────────────────────────────
class TestTriggerRollback:
    def test_rollback_records_event(self):
        rollback_called = []
        monitor = DeploymentMonitor(
            rollback_fn=lambda v: rollback_called.append(v),
        )
        m = DeploymentMetrics(error_rate=0.10)
        event = monitor.trigger_rollback("v1.3", RollbackReason.HIGH_ERROR_RATE, m, previous_version="v1.2")
        assert event.version == "v1.3"
        assert event.reason == RollbackReason.HIGH_ERROR_RATE
        assert event.previous_version == "v1.2"
        assert rollback_called == ["v1.2"]

    def test_rollback_history_accumulates(self):
        monitor = DeploymentMonitor()
        m = DeploymentMetrics(error_rate=0.15)
        monitor.trigger_rollback("v1.3", RollbackReason.HIGH_ERROR_RATE, m)
        monitor.trigger_rollback("v1.4", RollbackReason.HIGH_LATENCY, m)
        assert len(monitor.rollback_history) == 2


# ──────────────────────────────────────────────────
# DeploymentMonitor: monitor_deployment
# ──────────────────────────────────────────────────
class TestMonitorDeployment:
    def test_stable_deployment(self):
        healthy = DeploymentMetrics(error_rate=0.01, latency_p95=200, ragas_faithfulness=0.95)
        call_count = 0

        def mock_metrics(_version):
            nonlocal call_count
            call_count += 1
            return healthy

        monitor = DeploymentMonitor(metrics_fn=mock_metrics)
        result = monitor.monitor_deployment("v1.3", duration_seconds=0, check_interval=1)
        assert result.status == DeploymentStatus.STABLE

    def test_rollback_on_error(self):
        bad = DeploymentMetrics(error_rate=0.10)

        monitor = DeploymentMonitor(metrics_fn=lambda _v: bad)
        result = monitor.monitor_deployment("v1.3", duration_seconds=60, check_interval=1)
        assert result.status == DeploymentStatus.ROLLED_BACK
        assert result.rollback_event is not None
        assert result.rollback_event.reason == RollbackReason.HIGH_ERROR_RATE

    def test_no_metrics_fn_raises(self):
        monitor = DeploymentMonitor()
        with pytest.raises(RuntimeError, match="No metrics_fn"):
            monitor.monitor_deployment("v1.3")


# ──────────────────────────────────────────────────
# FeatureFlagManager
# ──────────────────────────────────────────────────
class TestFeatureFlagManager:
    def test_register_flag(self):
        mgr = FeatureFlagManager()
        flag = mgr.register("hybrid_rag", description="Use hybrid retrieval")
        assert flag.name == "hybrid_rag"
        assert "hybrid_rag" in mgr.flags

    def test_unknown_flag_returns_false(self):
        mgr = FeatureFlagManager()
        assert mgr.is_enabled("nonexistent") is False

    def test_global_enable(self):
        mgr = FeatureFlagManager()
        mgr.register("feature_x")
        mgr.set_global("feature_x", enabled=True)
        assert mgr.is_enabled("feature_x") is True
        assert mgr.is_enabled("feature_x", tenant_id="any") is True

    def test_tenant_enable(self):
        mgr = FeatureFlagManager()
        mgr.register("feature_x")
        mgr.enable_for_tenant("feature_x", "tenant-42")
        assert mgr.is_enabled("feature_x", tenant_id="tenant-42") is True
        assert mgr.is_enabled("feature_x", tenant_id="tenant-99") is False

    def test_tenant_disable(self):
        mgr = FeatureFlagManager()
        mgr.register("feature_x")
        mgr.enable_for_tenant("feature_x", "tenant-42")
        mgr.disable_for_tenant("feature_x", "tenant-42")
        assert mgr.is_enabled("feature_x", tenant_id="tenant-42") is False

    def test_unknown_flag_enable_raises(self):
        mgr = FeatureFlagManager()
        with pytest.raises(KeyError, match="Unknown flag"):
            mgr.enable_for_tenant("nonexistent", "tenant-1")

    def test_unknown_flag_set_global_raises(self):
        mgr = FeatureFlagManager()
        with pytest.raises(KeyError, match="Unknown flag"):
            mgr.set_global("nonexistent", enabled=True)

    def test_rollout_percentage(self):
        mgr = FeatureFlagManager()
        mgr.register("gradual_feature", rollout_percentage=1.0)  # 100%
        # All tenants should be enabled at 100%
        assert mgr.is_enabled("gradual_feature", tenant_id="tenant-1") is True
        assert mgr.is_enabled("gradual_feature", tenant_id="tenant-99") is True

    def test_zero_rollout(self):
        mgr = FeatureFlagManager()
        mgr.register("off_feature", rollout_percentage=0.0)
        assert mgr.is_enabled("off_feature", tenant_id="tenant-1") is False
