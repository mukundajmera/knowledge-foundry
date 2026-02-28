"""Knowledge Foundry — Graph API Routes.

Endpoints for knowledge graph operations (Task 2.7):
- /v1/graph/entities/search — search entities
- /v1/graph/traverse — traverse from entry entities
- /v1/graph/extract — extract entities from text
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/graph", tags=["graph"])


# =============================================================
# Request / Response Models
# =============================================================


class EntitySearchRequest(BaseModel):
    """Search for entities in the knowledge graph."""
    query: str
    tenant_id: str = "default"
    entity_types: list[str] | None = None
    limit: int = Field(default=10, ge=1, le=100)


class EntitySearchResponse(BaseModel):
    """Entity search results."""
    entities: list[dict[str, Any]]
    count: int


class TraverseRequest(BaseModel):
    """Traverse the knowledge graph from entry entities."""
    entry_entity_ids: list[str]
    tenant_id: str = "default"
    max_hops: int = Field(default=2, ge=1, le=5)
    relationship_types: list[str] | None = None
    entity_types: list[str] | None = None
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    max_results: int = Field(default=50, ge=1, le=500)


class TraverseResponse(BaseModel):
    """Graph traversal results."""
    entities: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    connected_document_ids: list[str]
    traversal_depth_reached: int
    nodes_explored: int
    latency_ms: int


class ExtractionRequest(BaseModel):
    """Extract entities and relationships from text."""
    text: str
    tenant_id: str = "default"
    document_title: str = ""
    source_system: str = "manual"
    content_type: str = "documentation"
    persist: bool = Field(default=False, description="Persist extracted entities to graph")


class ExtractionResponse(BaseModel):
    """Extraction results."""
    entities: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    persisted: bool = False


# =============================================================
# Routes
# =============================================================


@router.post("/entities/search", response_model=EntitySearchResponse)
async def search_entities(req: EntitySearchRequest, request: Request):
    """Search for entities in the knowledge graph."""
    container = getattr(request.app.state, "services", None)
    if not container or not container.graph_store:
        raise HTTPException(status_code=503, detail="Graph store not available")

    entities = await container.graph_store.search_entities(
        query=req.query,
        tenant_id=req.tenant_id,
        entity_types=req.entity_types,
        limit=req.limit,
    )

    return EntitySearchResponse(
        entities=[e.model_dump() for e in entities],
        count=len(entities),
    )


@router.post("/traverse", response_model=TraverseResponse)
async def traverse_graph(req: TraverseRequest, request: Request):
    """Traverse the knowledge graph from entry entities."""
    container = getattr(request.app.state, "services", None)
    if not container or not container.graph_store:
        raise HTTPException(status_code=503, detail="Graph store not available")

    result = await container.graph_store.traverse(
        entry_entity_ids=req.entry_entity_ids,
        tenant_id=req.tenant_id,
        max_hops=req.max_hops,
        relationship_types=req.relationship_types,
        entity_types=req.entity_types,
        min_confidence=req.min_confidence,
        max_results=req.max_results,
    )

    return TraverseResponse(
        entities=[e.model_dump() for e in result.entities],
        relationships=[r.model_dump() for r in result.relationships],
        connected_document_ids=result.connected_document_ids,
        traversal_depth_reached=result.traversal_depth_reached,
        nodes_explored=result.nodes_explored,
        latency_ms=result.latency_ms,
    )


@router.post("/extract", response_model=ExtractionResponse)
async def extract_entities(req: ExtractionRequest, request: Request):
    """Extract entities and relationships from text using LLM."""
    container = getattr(request.app.state, "services", None)
    if not container or not container.entity_extractor:
        raise HTTPException(status_code=503, detail="Entity extractor not available")

    result = await container.entity_extractor.extract_from_chunk(
        chunk_text=req.text,
        document_title=req.document_title,
        source_system=req.source_system,
        content_type=req.content_type,
    )

    persisted = False
    if req.persist and container.graph_store:
        entities, relationships = container.entity_extractor.to_graph_models(
            result, req.tenant_id,
        )
        await container.graph_store.add_entities(entities, relationships)
        persisted = True

    return ExtractionResponse(
        entities=[e.model_dump() for e in result.entities],
        relationships=[r.model_dump() for r in result.relationships],
        persisted=persisted,
    )


@router.get("/health")
async def graph_health(request: Request):
    """Check graph store health."""
    container = getattr(request.app.state, "services", None)
    if not container or not container.graph_store:
        return {"status": "unavailable", "detail": "Graph store not configured"}

    healthy = await container.graph_store.health_check()
    return {"status": "ok" if healthy else "unhealthy"}
