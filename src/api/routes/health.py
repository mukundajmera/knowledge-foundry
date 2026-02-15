"""Knowledge Foundry — Health Check Routes.

GET /health — basic liveness check.
GET /ready — readiness check with dependency status.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

from src.core.dependencies import ServiceContainer, check_health

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


def _get_services(request: Request) -> ServiceContainer | None:
    """Safely get the service container from app state."""
    return getattr(request.app.state, "services", None)


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — returns OK if the process is running."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, Any]:
    """Readiness probe — checks dependency connectivity.

    Verifies Qdrant, Redis, LLM, embedding service, and RAG pipeline
    status via the service container.
    """
    container = _get_services(request)
    if not container:
        return {
            "status": "degraded",
            "checks": {"api": "ok", "services": "not_initialized"},
        }

    checks = await check_health(container)

    # Overall: "ready" if all critical services are ok, "degraded" otherwise
    critical = {"api", "qdrant", "llm", "embedding", "rag_pipeline"}
    all_critical_ok = all(
        checks.get(svc) == "ok" for svc in critical
    )

    return {
        "status": "ready" if all_critical_ok else "degraded",
        "checks": checks,
    }
