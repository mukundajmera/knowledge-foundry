"""Knowledge Foundry — Retrieval API.

Exposes basic and agentic retrieval endpoints through a single API surface.
Supports simple top-K retrieval and advanced multi-hop agentic retrieval.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.retrieval.agentic import (
    AgenticReasoningEffort,
    AgenticRetrievalRequest,
    BasicRetrievalRequest,
    RetrievalMode,
    RetrievalResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/retrieve", tags=["Retrieval"])


# =============================================================
# REQUEST SCHEMAS
# =============================================================


class BasicRetrievalAPIRequest(BaseModel):
    """API request for simple top-K retrieval."""

    kb_id: UUID
    query: str
    tenant_id: str
    top_k: int = Field(default=10, ge=1, le=100)
    mode: RetrievalMode = RetrievalMode.VECTOR
    filters: dict[str, Any] = Field(default_factory=dict)
    similarity_threshold: float = Field(default=0.65, ge=0.0, le=1.0)


class AgenticRetrievalAPIRequest(BaseModel):
    """API request for agentic multi-hop retrieval."""

    query: str
    tenant_id: str
    kb_ids: list[UUID] = Field(default_factory=list)
    max_steps: int = Field(default=5, ge=1, le=20)
    reasoning_effort: AgenticReasoningEffort = AgenticReasoningEffort.MEDIUM
    top_k_per_step: int = Field(default=5, ge=1, le=50)
    token_budget: int = Field(default=8000, ge=100, le=100000)
    max_latency_ms: int = Field(default=30000, ge=1000, le=120000)
    mode: RetrievalMode = RetrievalMode.HYBRID
    filters: dict[str, Any] = Field(default_factory=dict)


# =============================================================
# RESPONSE HELPERS
# =============================================================


def _format_response(resp: RetrievalResponse) -> dict[str, Any]:
    """Convert a RetrievalResponse to a JSON-serializable dict."""
    return {
        "request_id": str(resp.request_id),
        "answer": resp.answer,
        "results": [
            {
                "chunk_id": r.chunk_id,
                "document_id": r.document_id,
                "text": r.text,
                "score": r.score,
                "metadata": r.metadata,
            }
            for r in resp.results
        ],
        "steps": [
            {
                "step_number": s.step_number,
                "action": s.action,
                "result_count": len(s.results),
                "tokens_used": s.tokens_used,
                "latency_ms": s.latency_ms,
                "sub_queries": [
                    {
                        "text": sq.text,
                        "kb_id": str(sq.kb_id) if sq.kb_id else None,
                        "rationale": sq.rationale,
                        "result_count": len(sq.results),
                        "token_count": sq.token_count,
                    }
                    for sq in s.sub_queries
                ] if s.sub_queries else [],
                "synthesis": s.synthesis or None,
            }
            for s in resp.steps
        ],
        "total_tokens_used": resp.total_tokens_used,
        "total_latency_ms": resp.total_latency_ms,
        "truncated": resp.truncated,
    }


# =============================================================
# ENDPOINTS
# =============================================================


@router.post("/basic")
async def basic_retrieval(req: BasicRetrievalAPIRequest, request: Request) -> dict[str, Any]:
    """Perform simple top-K retrieval from a single knowledge base.

    Returns ranked search results without LLM synthesis.
    """
    services = getattr(request.app.state, "services", None)
    if not services or not getattr(services, "vector_store", None):
        raise HTTPException(status_code=503, detail="Retrieval service not available")

    from src.retrieval.agentic import AgenticRetrievalEngine

    engine = AgenticRetrievalEngine(
        vector_store=services.vector_store,
        embedding_service=services.embedding_service,
        llm_provider=services.llm_provider,
    )

    internal_req = BasicRetrievalRequest(
        kb_id=req.kb_id,
        query=req.query,
        tenant_id=req.tenant_id,
        top_k=req.top_k,
        mode=req.mode,
        filters=req.filters,
        similarity_threshold=req.similarity_threshold,
    )

    response = await engine.basic_retrieve(internal_req)
    return _format_response(response)


@router.post("/agentic")
async def agentic_retrieval(req: AgenticRetrievalAPIRequest, request: Request) -> dict[str, Any]:
    """Perform agentic multi-hop retrieval across knowledge bases.

    Decomposes the query, plans sub-queries across KBs, iteratively
    retrieves, and synthesizes a final answer. Respects token budget
    and latency constraints.
    """
    services = getattr(request.app.state, "services", None)
    if not services or not getattr(services, "vector_store", None):
        raise HTTPException(status_code=503, detail="Retrieval service not available")

    from src.retrieval.agentic import AgenticRetrievalEngine

    engine = AgenticRetrievalEngine(
        vector_store=services.vector_store,
        embedding_service=services.embedding_service,
        llm_provider=services.llm_provider,
    )

    internal_req = AgenticRetrievalRequest(
        query=req.query,
        tenant_id=req.tenant_id,
        kb_ids=req.kb_ids,
        max_steps=req.max_steps,
        reasoning_effort=req.reasoning_effort,
        top_k_per_step=req.top_k_per_step,
        token_budget=req.token_budget,
        max_latency_ms=req.max_latency_ms,
        mode=req.mode,
        filters=req.filters,
    )

    response = await engine.agentic_retrieve(internal_req)
    return _format_response(response)
