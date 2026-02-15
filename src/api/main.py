"""Knowledge Foundry — FastAPI Application.

Entry point for the Knowledge Foundry API server.
Sets up the FastAPI app with lifespan, middleware, and route registration.
Services are initialized via the DI container in ``core.dependencies``.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from src.api.middleware.telemetry import TelemetryMiddleware
from src.api.routes import documents, health, orchestrator, query, graph_routes, compliance_health, feedback, models
from src.compliance.audit import AuditTrail
from src.improvement.feedback_processor import FeedbackProcessor
from src.core.config import get_settings
from src.core.dependencies import close_services, create_services
from src.observability.metrics import get_metrics_text

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — init and cleanup of shared resources.

    Creates the service container at startup and stores it on ``app.state.services``.
    Routes access services via ``request.app.state.services``.
    """
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.app_log_level, logging.INFO))

    await logger.ainfo(
        "Starting Knowledge Foundry",
        env=settings.app_env,
        debug=settings.app_debug,
    )

    # Initialize all services
    container = await create_services(settings)
    app.state.services = container

    # Initialize compliance audit trail
    audit_trail = AuditTrail()
    app.state.audit_trail = audit_trail
    compliance_health.set_audit_trail(audit_trail)

    # Initialize feedback processor
    feedback_processor = FeedbackProcessor()
    app.state.feedback_processor = feedback_processor
    feedback.set_feedback_processor(feedback_processor)

    if container.is_ready:
        await logger.ainfo("All services initialized — API fully operational")
    else:
        await logger.awarning(
            "Some services unavailable — API running in degraded mode"
        )

    yield  # App runs here

    # Shutdown
    await logger.ainfo("Shutting down Knowledge Foundry")
    await close_services(container)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Knowledge Foundry",
        description="Enterprise AI Knowledge Management Platform",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.app_debug else None,
        redoc_url="/redoc" if settings.app_debug else None,
    )

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_env == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Telemetry middleware (request ID + metrics) ---
    app.add_middleware(TelemetryMiddleware)

    # --- Metrics endpoint ---
    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics() -> Response:
        return PlainTextResponse(
            content=get_metrics_text(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    # --- Routes ---
    app.include_router(health.router)
    app.include_router(query.router)
    app.include_router(orchestrator.router)
    app.include_router(documents.router)
    app.include_router(graph_routes.router)
    app.include_router(compliance_health.router)
    app.include_router(feedback.router)
    app.include_router(models.router)

    return app


# Module-level app instance for uvicorn
app = create_app()
