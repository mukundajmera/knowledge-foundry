"""Knowledge Foundry — Query Route.

POST /v1/query — accepts a query and returns a RAG-powered response.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.compliance.audit import AuditAction
from src.core.dependencies import ServiceContainer
from src.core.interfaces import ModelTier
from src.security.input_sanitizer import SanitizationAction, sanitize_input
from src.security.output_filter import filter_output

router = APIRouter(prefix="/v1", tags=["query"])
logger = logging.getLogger(__name__)


# --- Request / Response Schemas ---


class QueryRequest(BaseModel):
    """Request body for POST /v1/query."""

    query: str = Field(..., min_length=1, max_length=10000, description="The user's question")
    tenant_id: UUID = Field(..., description="Tenant ID for data isolation")
    top_k: int = Field(default=10, ge=1, le=100, description="Number of chunks to retrieve")
    similarity_threshold: float = Field(
        default=0.65, ge=0.0, le=1.0, description="Minimum similarity"
    )
    filters: dict[str, Any] | None = Field(
        default=None, description="Optional metadata filters"
    )
    model_tier: ModelTier = Field(
        default=ModelTier.SONNET, description="LLM tier to use"
    )
    max_tokens: int = Field(default=4096, ge=1, le=100000, description="Max response tokens")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0, description="LLM temperature")


class SourceCitation(BaseModel):
    """Citation in a query response."""

    document_id: str
    title: str
    chunk_id: str | None = None
    relevance_score: float = 0.0


class RoutingInfo(BaseModel):
    """Routing metadata in a query response."""

    initial_tier: str
    final_tier: str
    escalated: bool = False
    escalation_reason: str | None = None
    complexity_score: float = 0.0
    task_type_detected: str = "general"


class PerformanceInfo(BaseModel):
    """Performance metadata in a query response."""

    total_latency_ms: int = 0
    llm_latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class QueryResponse(BaseModel):
    """Response body for POST /v1/query."""

    answer: str
    citations: list[SourceCitation] = Field(default_factory=list)
    routing: RoutingInfo | None = None
    performance: PerformanceInfo | None = None
    result_count: int = 0
    cached: bool = False
    security: dict[str, Any] | None = None


def _get_services(request: Request) -> ServiceContainer:
    """Get the service container from app state or raise 503."""
    container: ServiceContainer | None = getattr(request.app.state, "services", None)
    if not container or not container.rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="RAG pipeline not initialized. Start infrastructure services first.",
        )
    return container


# --- Route ---


@router.post("/query", response_model=QueryResponse)
async def query(request_body: QueryRequest, request: Request) -> QueryResponse:
    """Execute a RAG query and return the response.

    Security pipeline:
    1. Input sanitization (prompt injection, obfuscation, entropy)
    2. Cache check (skip RAG on hit)
    3. RAG pipeline execution
    4. Output filtering (PII redaction, leakage, harmful content)
    5. Audit trail logging
    """
    container = _get_services(request)
    pipeline = container.rag_pipeline
    tenant_id_str = str(request_body.tenant_id)

    logger.info(
        "Query received: tenant=%s, query=%s...",
        request_body.tenant_id,
        request_body.query[:80],
    )

    # ── Step 1: Input sanitization ──
    san_result = sanitize_input(request_body.query)
    if san_result.action == SanitizationAction.BLOCK:
        threat_labels = [t.pattern_label for t in san_result.threats]
        logger.warning(
            "Query BLOCKED (injection): tenant=%s threats=%s",
            tenant_id_str,
            threat_labels,
        )
        # Audit the blocked attempt
        if container.audit_trail:
            container.audit_trail.log(
                AuditAction.INJECTION_BLOCKED,
                tenant_id=tenant_id_str,
                input_text=request_body.query[:200],
                metadata={"threats": threat_labels},
            )
        raise HTTPException(
            status_code=400,
            detail="Query rejected: potential prompt injection detected.",
        )

    # ── Step 2: Cache check ──
    cache = container.response_cache
    cache_key = None
    if cache:
        from src.cache.response_cache import ResponseCache
        cache_key = ResponseCache.make_key(
            "query", request_body.query, tenant_id_str,
            top_k=str(request_body.top_k),
            model=request_body.model_tier.value,
        )
        cached_response = await cache.get(cache_key)
        if cached_response is not None:
            logger.info("Cache HIT for query: tenant=%s", tenant_id_str)
            cached_response["cached"] = True
            return QueryResponse(**cached_response)

    try:
        # Ensure tenant collection exists
        if container.vector_store:
            await container.vector_store.ensure_collection(tenant_id_str)

        result = await pipeline.query(  # type: ignore[union-attr]
            query=request_body.query,
            tenant_id=tenant_id_str,
            top_k=request_body.top_k,
            similarity_threshold=request_body.similarity_threshold,
            filters=request_body.filters,
            model_tier=request_body.model_tier,
            max_tokens=request_body.max_tokens,
            temperature=request_body.temperature,
        )

        # ── Step 3: Output filtering ──
        answer_text = result.text
        security_meta: dict[str, Any] = {}

        filter_result = filter_output(answer_text)
        answer_text = filter_result.filtered_text
        if filter_result.pii_detected:
            security_meta["pii_redacted"] = len(filter_result.pii_detected)
        if filter_result.prompt_leakage_detected:
            security_meta["prompt_leakage_blocked"] = True
        if filter_result.harmful_content_score > 0:
            security_meta["harmful_score"] = filter_result.harmful_content_score

        # Map RAGResponse → QueryResponse
        citations = [
            SourceCitation(
                document_id=c.document_id,
                title=c.title,
                chunk_id=c.chunk_id,
                relevance_score=c.relevance_score,
            )
            for c in result.citations
        ]

        routing = None
        if result.routing_decision:
            rd = result.routing_decision
            routing = RoutingInfo(
                initial_tier=rd.initial_tier.value if hasattr(rd.initial_tier, "value") else str(rd.initial_tier),
                final_tier=rd.final_tier.value if hasattr(rd.final_tier, "value") else str(rd.final_tier),
                escalated=rd.escalated,
                escalation_reason=rd.escalation_reason,
                complexity_score=rd.complexity_score,
                task_type_detected=rd.task_type_detected or "general",
            )

        performance = None
        if result.llm_response:
            lr = result.llm_response
            performance = PerformanceInfo(
                total_latency_ms=result.total_latency_ms,
                llm_latency_ms=lr.latency_ms,
                input_tokens=lr.input_tokens,
                output_tokens=lr.output_tokens,
                cost_usd=lr.cost_usd,
            )

        response = QueryResponse(
            answer=answer_text,
            citations=citations,
            routing=routing,
            performance=performance,
            result_count=len(result.search_results),
            cached=False,
            security=security_meta if security_meta else None,
        )

        # ── Step 4: Cache store ──
        if cache and cache_key:
            await cache.set(cache_key, response.model_dump())

        # ── Step 5: Audit trail ──
        if container.audit_trail:
            container.audit_trail.log(
                AuditAction.QUERY,
                tenant_id=tenant_id_str,
                input_text=request_body.query[:500],
                output_text=answer_text[:500],
                model_used=request_body.model_tier.value,
                confidence=result.routing_decision.complexity_score if result.routing_decision else 0.0,
                latency_ms=result.total_latency_ms,
                cost_usd=result.llm_response.cost_usd if result.llm_response else 0.0,
            )

        return response

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Query processing failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {type(exc).__name__}",
        ) from exc
