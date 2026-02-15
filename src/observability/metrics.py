"""Knowledge Foundry — Prometheus Metrics Registry.

Defines all application metrics per phase-1.5 observability spec.
Exposes a `/metrics` endpoint for Prometheus scraping.
"""

from __future__ import annotations

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)


# ──────────────────────────────────────────────────────────────
# Shared registry (avoids global state pollution in tests)
# ──────────────────────────────────────────────────────────────

registry = CollectorRegistry()


# ──────────────────────────────────────────────────────────────
# API Gateway Metrics
# ──────────────────────────────────────────────────────────────

api_requests_total = Counter(
    "api_requests_total",
    "Total API requests",
    labelnames=["method", "endpoint", "status_code", "tenant_id"],
    registry=registry,
)

api_errors_total = Counter(
    "api_errors_total",
    "Total API errors",
    labelnames=["endpoint", "error_type", "tenant_id"],
    registry=registry,
)

api_request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "API request duration in seconds",
    labelnames=["method", "endpoint", "tenant_id"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=registry,
)

api_active_connections = Gauge(
    "api_active_connections",
    "Active API connections",
    labelnames=["tenant_id"],
    registry=registry,
)


# ──────────────────────────────────────────────────────────────
# LLM Router Metrics
# ──────────────────────────────────────────────────────────────

router_requests_total = Counter(
    "router_requests_total",
    "Total routing decisions",
    labelnames=["task_type", "initial_tier", "final_tier", "tenant_id"],
    registry=registry,
)

router_tokens_total = Counter(
    "router_tokens_total",
    "Total tokens consumed",
    labelnames=["model_tier", "direction", "tenant_id"],
    registry=registry,
)

router_model_duration_seconds = Histogram(
    "router_model_duration_seconds",
    "LLM model response time in seconds",
    labelnames=["model_tier", "tenant_id"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=registry,
)


# ──────────────────────────────────────────────────────────────
# Retrieval Metrics
# ──────────────────────────────────────────────────────────────

retrieval_duration_seconds = Histogram(
    "retrieval_duration_seconds",
    "Retrieval latency in seconds",
    labelnames=["strategy", "tenant_id"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=registry,
)

retrieval_cache_hits_total = Counter(
    "retrieval_cache_hits_total",
    "Cache hits",
    labelnames=["cache_type", "tenant_id"],
    registry=registry,
)


# ──────────────────────────────────────────────────────────────
# Security Metrics
# ──────────────────────────────────────────────────────────────

security_injection_attempts_total = Counter(
    "security_injection_attempts_total",
    "Prompt injection attempts detected",
    labelnames=["pattern_type", "action", "tenant_id"],
    registry=registry,
)

security_pii_detections_total = Counter(
    "security_pii_detections_total",
    "PII detections in output",
    labelnames=["pii_type", "action", "tenant_id"],
    registry=registry,
)

security_rate_limit_triggers_total = Counter(
    "security_rate_limit_triggers_total",
    "Rate limit activations",
    labelnames=["tier", "tenant_id", "window"],
    registry=registry,
)

security_auth_failures_total = Counter(
    "security_auth_failures_total",
    "Authentication failures",
    labelnames=["reason", "tenant_id"],
    registry=registry,
)


# ──────────────────────────────────────────────────────────────
# Agent Metrics
# ──────────────────────────────────────────────────────────────

agent_tasks_total = Counter(
    "agent_tasks_total",
    "Total agent tasks",
    labelnames=["persona", "status", "tenant_id"],
    registry=registry,
)

agent_task_duration_seconds = Histogram(
    "agent_task_duration_seconds",
    "Agent task completion time",
    labelnames=["persona", "tenant_id"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    registry=registry,
)


# ──────────────────────────────────────────────────────────────
# Convenience
# ──────────────────────────────────────────────────────────────

def get_metrics_text() -> bytes:
    """Render all metrics as Prometheus text exposition format."""
    return generate_latest(registry)
