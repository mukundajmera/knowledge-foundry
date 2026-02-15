"""Knowledge Foundry — Weekly Automated Analysis.

Aggregates metrics, detects trends and anomalies, segments users into
cohorts, identifies improvement opportunities, and generates reports.
Per Phase 8.1 §3.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.improvement.metrics_collector import MetricsCollector, QueryEvent, KPISnapshot

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────────────────────

@dataclass
class Trend:
    """A detected metric trend."""

    metric: str
    direction: str  # "improving" | "declining" | "stable"
    current: float
    previous: float
    change_pct: float


@dataclass
class Anomaly:
    """A detected anomaly in a metric."""

    metric: str
    severity: str  # "info" | "warning" | "critical"
    value: float
    threshold: float
    message: str


@dataclass
class Opportunity:
    """An improvement opportunity."""

    area: str
    priority: str  # "HIGH" | "MEDIUM" | "LOW"
    description: str
    expected_impact: str


@dataclass
class UserCohort:
    """A user cohort segment."""

    name: str
    definition: str
    user_ids: list[str] = field(default_factory=list)
    count: int = 0
    avg_queries: float = 0.0
    avg_satisfaction: float = 0.0


@dataclass
class WeeklyReport:
    """Structured weekly analysis report."""

    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kpi_snapshot: KPISnapshot | None = None
    kpi_targets_met: dict[str, bool] = field(default_factory=dict)
    trends: list[Trend] = field(default_factory=list)
    anomalies: list[Anomaly] = field(default_factory=list)
    opportunities: list[Opportunity] = field(default_factory=list)
    cohorts: list[UserCohort] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# Analyzer
# ──────────────────────────────────────────────────────────────

class WeeklyAnalyzer:
    """Runs automated weekly analysis on collected metrics."""

    # Thresholds for anomaly detection
    ANOMALY_THRESHOLDS: dict[str, dict[str, Any]] = {
        "latency_p95_ms": {"warn": 400, "critical": 500},
        "error_rate": {"warn": 0.01, "critical": 0.05},
        "avg_cost_per_query": {"warn": 0.08, "critical": 0.10},
        "thumbs_up_rate": {"warn": 0.70, "critical": 0.60},
        "avg_ragas_faithfulness": {"warn": 0.90, "critical": 0.85},
    }

    def __init__(self, collector: MetricsCollector) -> None:
        self._collector = collector

    def run(self, *, previous_snapshot: KPISnapshot | None = None) -> WeeklyReport:
        """Execute the full weekly analysis pipeline."""
        snapshot = self._collector.compute_kpi_snapshot(window_hours=168)  # 7 days
        targets_met = snapshot.meets_targets()
        trends = self._identify_trends(snapshot, previous_snapshot) if previous_snapshot else []
        anomalies = self._detect_anomalies(snapshot)
        opportunities = self._identify_opportunities(snapshot, anomalies)
        cohorts = self._segment_users()

        report = WeeklyReport(
            kpi_snapshot=snapshot,
            kpi_targets_met=targets_met,
            trends=trends,
            anomalies=anomalies,
            opportunities=opportunities,
            cohorts=cohorts,
        )

        logger.info(
            "Weekly report: %d events, %d trends, %d anomalies, %d opportunities",
            snapshot.event_count,
            len(trends),
            len(anomalies),
            len(opportunities),
        )
        return report

    def _identify_trends(
        self, current: KPISnapshot, previous: KPISnapshot
    ) -> list[Trend]:
        """Compare current vs previous period KPIs."""
        trends: list[Trend] = []
        metrics = [
            ("avg_ragas_faithfulness", "higher_better"),
            ("latency_p95_ms", "lower_better"),
            ("avg_cost_per_query", "lower_better"),
            ("thumbs_up_rate", "higher_better"),
        ]

        for metric_name, direction_pref in metrics:
            curr_val = getattr(current, metric_name, 0)
            prev_val = getattr(previous, metric_name, 0)

            if prev_val == 0:
                continue

            change_pct = ((curr_val - prev_val) / prev_val) * 100

            if direction_pref == "higher_better":
                direction = "improving" if change_pct > 2 else ("declining" if change_pct < -2 else "stable")
            else:
                direction = "improving" if change_pct < -2 else ("declining" if change_pct > 2 else "stable")

            trends.append(Trend(
                metric=metric_name,
                direction=direction,
                current=curr_val,
                previous=prev_val,
                change_pct=round(change_pct, 2),
            ))

        return trends

    def _detect_anomalies(self, snapshot: KPISnapshot) -> list[Anomaly]:
        """Flag metrics that breach thresholds."""
        anomalies: list[Anomaly] = []

        checks = {
            "latency_p95_ms": (snapshot.latency_p95_ms, "above"),
            "error_rate": (snapshot.error_rate, "above"),
            "avg_cost_per_query": (snapshot.avg_cost_per_query, "above"),
            "thumbs_up_rate": (snapshot.thumbs_up_rate, "below"),
            "avg_ragas_faithfulness": (snapshot.avg_ragas_faithfulness, "below"),
        }

        for metric, (value, breach_type) in checks.items():
            thresholds = self.ANOMALY_THRESHOLDS.get(metric, {})

            critical_thresh = thresholds.get("critical", None)
            warn_thresh = thresholds.get("warn", None)

            if critical_thresh is not None:
                breached = (value > critical_thresh) if breach_type == "above" else (value < critical_thresh)
                if breached:
                    anomalies.append(Anomaly(
                        metric=metric,
                        severity="critical",
                        value=value,
                        threshold=critical_thresh,
                        message=f"{metric} is {value:.4f}, threshold: {critical_thresh}",
                    ))
                    continue

            if warn_thresh is not None:
                breached = (value > warn_thresh) if breach_type == "above" else (value < warn_thresh)
                if breached:
                    anomalies.append(Anomaly(
                        metric=metric,
                        severity="warning",
                        value=value,
                        threshold=warn_thresh,
                        message=f"{metric} is {value:.4f}, threshold: {warn_thresh}",
                    ))

        return anomalies

    def _identify_opportunities(
        self, snapshot: KPISnapshot, anomalies: list[Anomaly]
    ) -> list[Opportunity]:
        """Map anomalies and KPIs into actionable opportunities."""
        opportunities: list[Opportunity] = []

        # Low satisfaction → review prompts
        if snapshot.thumbs_up_rate > 0 and snapshot.thumbs_up_rate < 0.70:
            opportunities.append(Opportunity(
                area="Quality",
                priority="HIGH",
                description="User satisfaction below 70% — review prompts and retrieval quality",
                expected_impact="+10-15% satisfaction",
            ))

        # High cost → optimize routing
        if snapshot.avg_cost_per_query > 0.08:
            opportunities.append(Opportunity(
                area="Cost",
                priority="MEDIUM",
                description="Average cost > $0.08/query — optimize model routing, increase Haiku usage",
                expected_impact="-20% cost",
            ))

        # Low RAGAS → improve retrieval
        if snapshot.avg_ragas_faithfulness > 0 and snapshot.avg_ragas_faithfulness < 0.90:
            opportunities.append(Opportunity(
                area="Quality",
                priority="HIGH",
                description="RAGAS faithfulness below 0.90 — review retrieval pipeline and chunking",
                expected_impact="+5% faithfulness",
            ))

        # High latency → scale or cache
        if snapshot.latency_p95_ms > 400:
            opportunities.append(Opportunity(
                area="Performance",
                priority="MEDIUM",
                description="p95 latency approaching threshold — consider scaling or cache tuning",
                expected_impact="-30% latency",
            ))

        return opportunities

    def _segment_users(self) -> list[UserCohort]:
        """Segment users into cohorts based on usage patterns."""
        events = self._collector.get_events()

        # Count queries per user
        user_queries: dict[str, list[QueryEvent]] = {}
        for e in events:
            if e.user_id:
                user_queries.setdefault(e.user_id, []).append(e)

        cohorts: list[UserCohort] = []

        power_users: list[str] = []
        casual_users: list[str] = []
        at_risk: list[str] = []

        for uid, user_events in user_queries.items():
            count = len(user_events)
            rated = [e for e in user_events if e.user_satisfaction is not None]
            avg_sat = (
                sum(e.user_satisfaction for e in rated) / len(rated)  # type: ignore[arg-type]
                if rated else 0.5
            )

            if count >= 50:
                power_users.append(uid)
            elif count >= 5:
                casual_users.append(uid)

            if avg_sat < 0.3:
                at_risk.append(uid)

        cohorts.append(UserCohort(
            name="Power Users",
            definition=">= 50 queries",
            user_ids=power_users,
            count=len(power_users),
        ))
        cohorts.append(UserCohort(
            name="Casual Users",
            definition="5-49 queries",
            user_ids=casual_users,
            count=len(casual_users),
        ))
        cohorts.append(UserCohort(
            name="At Risk",
            definition="Avg satisfaction < 0.3",
            user_ids=at_risk,
            count=len(at_risk),
        ))

        return cohorts
