"""Knowledge Foundry — Orchestrator Route.

POST /v1/orchestrate — delegates queries to the multi-agent LangGraph orchestrator.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.compliance.audit import AuditAction
from src.core.dependencies import ServiceContainer
from src.security.input_sanitizer import SanitizationAction, sanitize_input
from src.security.output_filter import filter_output

router = APIRouter(prefix="/v1", tags=["orchestrator"])
logger = logging.getLogger(__name__)


# --- Request / Response Schemas ---


class OrchestrationRequest(BaseModel):
    """Request body for POST /v1/orchestrate."""

    query: str = Field(..., min_length=1, max_length=10000, description="The user's question")
    tenant_id: UUID = Field(..., description="Tenant ID for data isolation")
    user_id: str = Field(default="", max_length=200, description="User identifier")
    deployment_context: str = Field(
        default="general",
        max_length=50,
        description="Deployment context (general, hr_screening, financial, etc.)",
    )
    max_iterations: int = Field(default=5, ge=1, le=20, description="Max agent iterations")


class AgentPerformance(BaseModel):
    """Performance metadata in an orchestration response."""

    iterations: int = 0
    cost_usd: float = 0.0
    trace_id: str = ""


class OrchestrationResponse(BaseModel):
    """Response body for POST /v1/orchestrate."""

    answer: str
    confidence: float = 0.0
    citations: list[dict[str, Any]] = Field(default_factory=list)
    agents_used: list[str] = Field(default_factory=list)
    orchestration_pattern: str = "supervisor"
    safety_verdict: dict[str, Any] | None = None
    hitl_required: bool = False
    hitl_reason: str | None = None
    performance: AgentPerformance | None = None


def _get_services(request: Request) -> ServiceContainer:
    """Get the service container from app state or raise 503."""
    container: ServiceContainer | None = getattr(request.app.state, "services", None)
    if not container or not container.agent_graph:
        raise HTTPException(
            status_code=503,
            detail="Agent orchestrator not initialized. Start infrastructure services first.",
        )
    return container


# --- Route ---


@router.post("/orchestrate", response_model=OrchestrationResponse)
async def orchestrate(request_body: OrchestrationRequest, request: Request) -> OrchestrationResponse:
    """Execute a multi-agent orchestration query.

    Security pipeline:
    1. Input sanitization (prompt injection, obfuscation, entropy)
    2. Multi-agent orchestration via LangGraph
    3. Output filtering (PII redaction, leakage, harmful content)
    4. Audit trail logging
    """
    container = _get_services(request)
    tenant_id_str = str(request_body.tenant_id)

    logger.info(
        "Orchestrate request: tenant=%s, context=%s, query=%s...",
        request_body.tenant_id,
        request_body.deployment_context,
        request_body.query[:80],
    )

    # ── Step 1: Input sanitization ──
    san_result = sanitize_input(request_body.query)
    if san_result.action == SanitizationAction.BLOCK:
        threat_labels = [t.pattern_label for t in san_result.threats]
        logger.warning(
            "Orchestrate BLOCKED (injection): tenant=%s threats=%s",
            tenant_id_str,
            threat_labels,
        )
        if container.audit_trail:
            container.audit_trail.log(
                AuditAction.INJECTION_BLOCKED,
                tenant_id=tenant_id_str,
                user_id=request_body.user_id,
                input_text=request_body.query[:200],
                metadata={"threats": threat_labels},
            )
        raise HTTPException(
            status_code=400,
            detail="Query rejected: potential prompt injection detected.",
        )

    try:
        from src.agents.graph_builder import run_orchestrator

        result = await run_orchestrator(
            compiled_graph=container.agent_graph,
            user_query=request_body.query,
            tenant_id=tenant_id_str,
            user_id=request_body.user_id,
            deployment_context=request_body.deployment_context,
            max_iterations=request_body.max_iterations,
        )

        # ── Step 2: Output filtering ──
        raw_answer = result.get("answer", "")
        filter_result = filter_output(raw_answer)
        answer_text = filter_result.filtered_text

        # Extract agent names from agent_outputs
        agents_used = list(result.get("agent_outputs", {}).keys())

        response = OrchestrationResponse(
            answer=answer_text,
            confidence=result.get("confidence", 0.0),
            citations=result.get("citations", []),
            agents_used=agents_used,
            orchestration_pattern=result.get("orchestration_pattern", "supervisor"),
            safety_verdict=result.get("safety_verdict"),
            hitl_required=result.get("hitl_required", False),
            hitl_reason=result.get("hitl_reason"),
            performance=AgentPerformance(
                iterations=result.get("iterations", 0),
                cost_usd=result.get("cost_usd", 0.0),
                trace_id=result.get("trace_id", ""),
            ),
        )

        # ── Step 3: Audit trail ──
        if container.audit_trail:
            container.audit_trail.log(
                AuditAction.QUERY,
                tenant_id=tenant_id_str,
                user_id=request_body.user_id,
                input_text=request_body.query[:500],
                output_text=answer_text[:500],
                metadata={
                    "agents_used": agents_used,
                    "deployment_context": request_body.deployment_context,
                },
            )

        return response

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Orchestration failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Orchestration failed: {type(exc).__name__}",
        ) from exc
