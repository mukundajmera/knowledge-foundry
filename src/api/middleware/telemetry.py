"""Knowledge Foundry — Request Telemetry Middleware.

FastAPI middleware for:
  - X-Request-ID / X-Trace-ID propagation
  - Request duration tracking → Prometheus histogram
  - Error counting
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.observability.metrics import (
    api_request_duration_seconds,
    api_requests_total,
    api_errors_total,
)

logger = logging.getLogger(__name__)


class TelemetryMiddleware(BaseHTTPMiddleware):
    """Middleware that tracks request metrics and propagates trace IDs."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        # Generate or propagate request/trace IDs
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())

        # Store in request state for downstream use
        request.state.request_id = request_id
        request.state.trace_id = trace_id

        # Extract routing metadata
        method = request.method
        path = request.url.path
        # Normalise path to avoid cardinality explosion
        # e.g. /v1/graph/entities/search → /v1/graph/entities/search
        endpoint = self._normalise_path(path)
        tenant_id = request.headers.get("X-Tenant-ID", "unknown")

        start = time.perf_counter()
        status_code = 500  # Default in case of unhandled exception

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start

            # Record metrics
            api_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=str(status_code),
                tenant_id=tenant_id,
            ).inc()

            api_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint,
                tenant_id=tenant_id,
            ).observe(duration)

            if status_code >= 500:
                api_errors_total.labels(
                    endpoint=endpoint,
                    error_type="server_error",
                    tenant_id=tenant_id,
                ).inc()
            elif status_code >= 400:
                api_errors_total.labels(
                    endpoint=endpoint,
                    error_type="client_error",
                    tenant_id=tenant_id,
                ).inc()

            logger.debug(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": int(duration * 1000),
                    "tenant_id": tenant_id,
                },
            )

    @staticmethod
    def _normalise_path(path: str) -> str:
        """Collapse UUID-like path segments to `{id}` to prevent label cardinality explosion."""
        import re
        # Match UUID pattern and replace with {id}
        return re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "{id}",
            path,
        )
