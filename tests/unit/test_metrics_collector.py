"""Tests for MetricsCollector — per-query event recording and KPI snapshots."""

from __future__ import annotations

import pytest

from src.improvement.metrics_collector import MetricsCollector, QueryEvent, KPISnapshot


class TestQueryEvent:
    def test_has_auto_id_and_timestamp(self) -> None:
        event = QueryEvent()
        assert event.event_id
        assert "T" in event.timestamp

    def test_to_dict(self) -> None:
        event = QueryEvent(total_latency_ms=100, cost_usd=0.05)
        d = event.to_dict()
        assert d["total_latency_ms"] == 100
        assert d["cost_usd"] == 0.05


class TestKPISnapshot:
    def test_meets_targets_all_good(self) -> None:
        snap = KPISnapshot(
            avg_ragas_faithfulness=0.96,
            avg_ragas_precision=0.92,
            latency_p95_ms=300,
            error_rate=0.005,
            thumbs_up_rate=0.85,
            avg_cost_per_query=0.08,
        )
        targets = snap.meets_targets()
        assert all(targets.values())

    def test_meets_targets_some_fail(self) -> None:
        snap = KPISnapshot(
            avg_ragas_faithfulness=0.80,  # below 0.95
            latency_p95_ms=600,  # above 500
        )
        targets = snap.meets_targets()
        assert targets["ragas_faithfulness"] is False
        assert targets["latency_p95"] is False


class TestMetricsCollector:
    def test_record_and_count(self) -> None:
        c = MetricsCollector()
        c.record(QueryEvent(total_latency_ms=100))
        c.record(QueryEvent(total_latency_ms=200))
        assert c.event_count == 2

    def test_filter_by_tenant(self) -> None:
        c = MetricsCollector()
        c.record(QueryEvent(tenant_id="alpha"))
        c.record(QueryEvent(tenant_id="beta"))
        c.record(QueryEvent(tenant_id="alpha"))
        assert len(c.get_events(tenant_id="alpha")) == 2

    def test_filter_by_user(self) -> None:
        c = MetricsCollector()
        c.record(QueryEvent(user_id="u1"))
        c.record(QueryEvent(user_id="u2"))
        assert len(c.get_events(user_id="u1")) == 1

    def test_last_n(self) -> None:
        c = MetricsCollector()
        for i in range(10):
            c.record(QueryEvent(total_latency_ms=i * 10.0))
        assert len(c.get_events(last_n=3)) == 3

    def test_kpi_snapshot_empty(self) -> None:
        c = MetricsCollector()
        snap = c.compute_kpi_snapshot()
        assert snap.event_count == 0

    def test_kpi_snapshot_aggregation(self) -> None:
        c = MetricsCollector()
        for i in range(20):
            c.record(QueryEvent(
                total_latency_ms=100 + i * 10,
                ragas_faithfulness=0.90 + i * 0.005,
                ragas_precision=0.85 + i * 0.005,
                cost_usd=0.05,
                user_id=f"user-{i % 5}",
                user_satisfaction=1.0 if i % 3 != 0 else 0.0,
            ))

        snap = c.compute_kpi_snapshot()
        assert snap.event_count == 20
        assert snap.unique_users == 5
        assert snap.avg_cost_per_query == pytest.approx(0.05)
        assert snap.latency_p50_ms > 0
        assert snap.latency_p95_ms > snap.latency_p50_ms

    def test_kpi_snapshot_per_tenant(self) -> None:
        c = MetricsCollector()
        c.record(QueryEvent(tenant_id="alpha", cost_usd=0.10))
        c.record(QueryEvent(tenant_id="beta", cost_usd=0.20))
        snap = c.compute_kpi_snapshot(tenant_id="beta")
        assert snap.event_count == 1
        assert snap.avg_cost_per_query == pytest.approx(0.20)
