"""Tests for Observability Metrics — src/observability/metrics.py."""

from __future__ import annotations

import pytest

from src.observability.metrics import (
    api_errors_total,
    api_request_duration_seconds,
    api_requests_total,
    get_metrics_text,
    registry,
    router_requests_total,
    security_injection_attempts_total,
    security_pii_detections_total,
    security_rate_limit_triggers_total,
)


class TestMetricsDefinitions:
    def test_api_requests_counter_exists(self) -> None:
        api_requests_total.labels(
            method="POST", endpoint="/v1/query",
            status_code="200", tenant_id="t1",
        ).inc()
        # No error means the metric is defined correctly

    def test_api_duration_histogram(self) -> None:
        api_request_duration_seconds.labels(
            method="GET", endpoint="/health", tenant_id="t1",
        ).observe(0.05)

    def test_api_errors_counter(self) -> None:
        api_errors_total.labels(
            endpoint="/v1/query", error_type="server_error", tenant_id="t1",
        ).inc()

    def test_router_requests(self) -> None:
        router_requests_total.labels(
            task_type="general", initial_tier="sonnet",
            final_tier="sonnet", tenant_id="t1",
        ).inc()

    def test_security_injection_counter(self) -> None:
        security_injection_attempts_total.labels(
            pattern_type="ignore_instructions", action="block", tenant_id="t1",
        ).inc()

    def test_security_pii_counter(self) -> None:
        security_pii_detections_total.labels(
            pii_type="email", action="redacted", tenant_id="t1",
        ).inc()

    def test_security_rate_limit_counter(self) -> None:
        security_rate_limit_triggers_total.labels(
            tier="free", tenant_id="t1", window="minute",
        ).inc()


class TestMetricsOutput:
    def test_get_metrics_text_returns_bytes(self) -> None:
        output = get_metrics_text()
        assert isinstance(output, bytes)
        assert len(output) > 0

    def test_metrics_text_contains_api_counter(self) -> None:
        output = get_metrics_text().decode()
        assert "api_requests_total" in output

    def test_metrics_text_contains_security_counter(self) -> None:
        output = get_metrics_text().decode()
        assert "security_injection_attempts_total" in output
