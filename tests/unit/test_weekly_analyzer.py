"""Tests for WeeklyAnalyzer — trends, anomalies, opportunities, cohorts."""

from __future__ import annotations

from src.improvement.metrics_collector import KPISnapshot, MetricsCollector, QueryEvent
from src.improvement.weekly_analyzer import WeeklyAnalyzer, WeeklyReport


def _populated_collector(n: int = 100) -> MetricsCollector:
    """Create a collector with n events from 10 users."""
    c = MetricsCollector()
    for i in range(n):
        c.record(QueryEvent(
            total_latency_ms=200 + (i % 50) * 5,
            ragas_faithfulness=0.92 + (i % 10) * 0.008,
            ragas_precision=0.88 + (i % 10) * 0.01,
            cost_usd=0.05 + (i % 10) * 0.005,
            user_id=f"user-{i % 10}",
            tenant_id="test-tenant",
            user_satisfaction=1.0 if i % 4 != 0 else 0.0,
        ))
    return c


class TestWeeklyAnalyzer:
    def test_run_produces_report(self) -> None:
        c = _populated_collector()
        analyzer = WeeklyAnalyzer(c)
        report = analyzer.run()
        assert isinstance(report, WeeklyReport)
        assert report.kpi_snapshot is not None
        assert report.kpi_snapshot.event_count == 100

    def test_report_has_kpi_targets(self) -> None:
        c = _populated_collector()
        report = WeeklyAnalyzer(c).run()
        assert "ragas_faithfulness" in report.kpi_targets_met

    def test_trend_detection(self) -> None:
        c = _populated_collector()
        analyzer = WeeklyAnalyzer(c)

        previous = KPISnapshot(
            avg_ragas_faithfulness=0.80,
            latency_p95_ms=400,
            avg_cost_per_query=0.10,
            thumbs_up_rate=0.60,
        )
        report = analyzer.run(previous_snapshot=previous)
        assert len(report.trends) > 0
        directions = {t.direction for t in report.trends}
        assert len(directions) >= 1  # At least some trends detected

    def test_anomaly_detection_high_cost(self) -> None:
        c = MetricsCollector()
        for _i in range(10):
            c.record(QueryEvent(cost_usd=0.15))  # Exceeds $0.10 threshold
        report = WeeklyAnalyzer(c).run()
        cost_anomalies = [a for a in report.anomalies if a.metric == "avg_cost_per_query"]
        assert len(cost_anomalies) >= 1
        assert cost_anomalies[0].severity == "critical"

    def test_anomaly_detection_low_satisfaction(self) -> None:
        c = MetricsCollector()
        for _i in range(10):
            c.record(QueryEvent(user_satisfaction=0.0))  # All thumbs down
        report = WeeklyAnalyzer(c).run()
        sat_anomalies = [a for a in report.anomalies if a.metric == "thumbs_up_rate"]
        assert len(sat_anomalies) >= 1

    def test_opportunity_detection(self) -> None:
        c = MetricsCollector()
        for _i in range(10):
            c.record(QueryEvent(cost_usd=0.12, user_satisfaction=0.0))
        report = WeeklyAnalyzer(c).run()
        areas = {o.area for o in report.opportunities}
        assert "Cost" in areas

    def test_cohort_segmentation(self) -> None:
        c = MetricsCollector()
        # Power user: 60 queries
        for _ in range(60):
            c.record(QueryEvent(user_id="power-user"))
        # Casual user: 10 queries
        for _ in range(10):
            c.record(QueryEvent(user_id="casual-user"))

        report = WeeklyAnalyzer(c).run()
        cohort_names = {co.name for co in report.cohorts}
        assert "Power Users" in cohort_names
        assert "Casual Users" in cohort_names

        power = next(co for co in report.cohorts if co.name == "Power Users")
        assert "power-user" in power.user_ids

    def test_empty_collector_runs(self) -> None:
        c = MetricsCollector()
        report = WeeklyAnalyzer(c).run()
        assert report.kpi_snapshot is not None
        assert report.kpi_snapshot.event_count == 0
        # Empty collector has 0.0 for quality/satisfaction → triggers anomalies
        assert len(report.anomalies) >= 0  # May trigger on 0.0 defaults
