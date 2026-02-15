"""Knowledge Foundry — Per-Query Metrics Collector.

Collects performance, quality, cost, and user behavior data for every query.
Computes KPI snapshots per Phase 8.1 §2.1 spec.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class QueryEvent:
    """A single query event with all measurable dimensions."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # ── Performance ──
    total_latency_ms: float = 0.0
    retrieval_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0

    # ── Quality ──
    ragas_faithfulness: float = 0.0
    ragas_precision: float = 0.0
    confidence_score: float = 0.0

    # ── Cost ──
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    model_used: str = ""

    # ── User Behavior ──
    user_satisfaction: float | None = None  # None = no rating yet
    reformulated: bool = False
    clicked_citations: int = 0

    # ── Context ──
    query_complexity: str = "simple"  # simple / medium / complex
    query_category: str = ""
    tenant_id: str = ""
    user_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KPISnapshot:
    """Aggregated KPI values over a time window."""

    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    window_hours: float = 24.0
    event_count: int = 0

    # Quality
    avg_ragas_faithfulness: float = 0.0
    avg_ragas_precision: float = 0.0
    avg_confidence: float = 0.0

    # Performance
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    error_rate: float = 0.0

    # Satisfaction
    thumbs_up_rate: float = 0.0
    avg_satisfaction: float = 0.0

    # Cost
    avg_cost_per_query: float = 0.0
    total_cost: float = 0.0

    # Engagement
    unique_users: int = 0
    avg_queries_per_user: float = 0.0

    def meets_targets(self) -> dict[str, bool]:
        """Check KPIs against Phase 8.1 §2.1 targets."""
        return {
            "ragas_faithfulness": self.avg_ragas_faithfulness >= 0.95,
            "ragas_precision": self.avg_ragas_precision >= 0.90,
            "latency_p95": self.latency_p95_ms <= 500,
            "error_rate": self.error_rate <= 0.01,
            "thumbs_up_rate": self.thumbs_up_rate >= 0.80,
            "cost_per_query": self.avg_cost_per_query <= 0.10,
        }


class MetricsCollector:
    """Collects per-query events and computes KPI snapshots.

    In-memory store for simplicity — production would back with PostgreSQL.
    """

    def __init__(self) -> None:
        self._events: list[QueryEvent] = []

    @property
    def event_count(self) -> int:
        return len(self._events)

    def record(self, event: QueryEvent) -> None:
        """Record a query event."""
        self._events.append(event)
        logger.debug(
            "Recorded event %s: latency=%.1fms cost=$%.4f",
            event.event_id[:8],
            event.total_latency_ms,
            event.cost_usd,
        )

    def get_events(
        self,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
        last_n: int | None = None,
    ) -> list[QueryEvent]:
        """Filter events by tenant, user, or count."""
        events = self._events
        if tenant_id:
            events = [e for e in events if e.tenant_id == tenant_id]
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        if last_n:
            events = events[-last_n:]
        return events

    def compute_kpi_snapshot(
        self,
        *,
        tenant_id: str | None = None,
        window_hours: float = 24.0,
    ) -> KPISnapshot:
        """Compute KPIs over the given time window."""
        events = self.get_events(tenant_id=tenant_id) if tenant_id else self._events

        if not events:
            return KPISnapshot(event_count=0, window_hours=window_hours)

        n = len(events)

        # ── Performance ──
        latencies = sorted(e.total_latency_ms for e in events)
        p50_idx = int(n * 0.50)
        p95_idx = min(int(n * 0.95), n - 1)
        p99_idx = min(int(n * 0.99), n - 1)

        # ── Quality ──
        avg_faith = sum(e.ragas_faithfulness for e in events) / n
        avg_prec = sum(e.ragas_precision for e in events) / n
        avg_conf = sum(e.confidence_score for e in events) / n

        # ── Cost ──
        total_cost = sum(e.cost_usd for e in events)
        avg_cost = total_cost / n

        # ── Satisfaction ──
        rated = [e for e in events if e.user_satisfaction is not None]
        if rated:
            avg_sat = sum(e.user_satisfaction for e in rated) / len(rated)  # type: ignore[arg-type]
            thumbs_up = sum(1 for e in rated if (e.user_satisfaction or 0) >= 0.5)
            thumbs_up_rate = thumbs_up / len(rated)
        else:
            avg_sat = 0.0
            thumbs_up_rate = 0.0

        # ── Engagement ──
        unique_users = len({e.user_id for e in events if e.user_id})
        avg_per_user = n / max(unique_users, 1)

        return KPISnapshot(
            window_hours=window_hours,
            event_count=n,
            avg_ragas_faithfulness=avg_faith,
            avg_ragas_precision=avg_prec,
            avg_confidence=avg_conf,
            latency_p50_ms=latencies[p50_idx],
            latency_p95_ms=latencies[p95_idx],
            latency_p99_ms=latencies[p99_idx],
            avg_cost_per_query=avg_cost,
            total_cost=total_cost,
            avg_satisfaction=avg_sat,
            thumbs_up_rate=thumbs_up_rate,
            unique_users=unique_users,
            avg_queries_per_user=avg_per_user,
        )
