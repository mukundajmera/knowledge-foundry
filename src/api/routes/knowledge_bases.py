"""Knowledge Foundry — Knowledge Base Management API.

CRUD endpoints for managing knowledge bases, sources, connectors,
and ingestion jobs.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.core.domain import (
    ChunkingStrategy,
    ClientApp,
    Connector,
    ConnectorType,
    Index,
    IndexType,
    IngestionJob,
    IngestionJobStatus,
    KnowledgeBase,
    Policy,
    PolicyType,
    Source,
    SourceStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/kb", tags=["Knowledge Bases"])

# In-memory stores (replaced by DB in production)
_knowledge_bases: dict[UUID, KnowledgeBase] = {}
_connectors: dict[UUID, Connector] = {}
_ingestion_jobs: dict[UUID, IngestionJob] = {}
_client_apps: dict[UUID, ClientApp] = {}


# =============================================================
# REQUEST SCHEMAS
# =============================================================


class CreateKnowledgeBaseRequest(BaseModel):
    """Request to create a new knowledge base."""

    name: str
    description: str = ""
    tenant_id: UUID
    embedding_model: str = "text-embedding-3-large"
    chunking_strategy: ChunkingStrategy = ChunkingStrategy.SEMANTIC
    tags: list[str] = Field(default_factory=list)


class CreateConnectorRequest(BaseModel):
    """Request to register a new connector."""

    name: str
    connector_type: ConnectorType
    config: dict[str, Any] = Field(default_factory=dict)


class AddSourceRequest(BaseModel):
    """Request to add a source to a knowledge base."""

    name: str
    description: str = ""
    connector_id: UUID
    location: str
    file_patterns: list[str] = Field(default_factory=list)


class AttachPolicyRequest(BaseModel):
    """Request to attach a policy to a knowledge base."""

    name: str
    policy_type: PolicyType
    description: str = ""
    rules: dict[str, Any] = Field(default_factory=dict)


class RegisterClientRequest(BaseModel):
    """Request to register a client application."""

    name: str
    description: str = ""
    allowed_knowledge_base_ids: list[UUID] = Field(default_factory=list)
    rate_limit_rpm: int = 60


# =============================================================
# KNOWLEDGE BASE ENDPOINTS
# =============================================================


@router.post("/knowledge-bases", status_code=201)
async def create_knowledge_base(req: CreateKnowledgeBaseRequest) -> dict[str, Any]:
    """Create a new knowledge base."""
    kb = KnowledgeBase(
        tenant_id=req.tenant_id,
        name=req.name,
        description=req.description,
        embedding_model=req.embedding_model,
        chunking_strategy=req.chunking_strategy,
        tags=req.tags,
    )
    # Auto-create a default hybrid index
    default_index = Index(
        knowledge_base_id=kb.kb_id,
        name=f"{req.name}-default-index",
        index_type=IndexType.HYBRID,
        embedding_model=req.embedding_model,
    )
    kb.indices.append(default_index)
    _knowledge_bases[kb.kb_id] = kb

    logger.info("Created knowledge base: id=%s name=%s", kb.kb_id, kb.name)
    return {"kb_id": str(kb.kb_id), "name": kb.name, "status": "created"}


@router.get("/knowledge-bases")
async def list_knowledge_bases(tenant_id: UUID | None = None) -> list[dict[str, Any]]:
    """List all knowledge bases, optionally filtered by tenant."""
    results = []
    for kb in _knowledge_bases.values():
        if tenant_id and kb.tenant_id != tenant_id:
            continue
        results.append({
            "kb_id": str(kb.kb_id),
            "name": kb.name,
            "description": kb.description,
            "tenant_id": str(kb.tenant_id),
            "source_count": len(kb.sources),
            "index_count": len(kb.indices),
            "tags": kb.tags,
            "created_at": kb.created_at.isoformat(),
        })
    return results


@router.get("/knowledge-bases/{kb_id}")
async def get_knowledge_base(kb_id: UUID) -> dict[str, Any]:
    """Get details of a specific knowledge base."""
    kb = _knowledge_bases.get(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb.model_dump(mode="json")


@router.delete("/knowledge-bases/{kb_id}", status_code=204)
async def delete_knowledge_base(kb_id: UUID) -> None:
    """Delete a knowledge base."""
    if kb_id not in _knowledge_bases:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    del _knowledge_bases[kb_id]
    logger.info("Deleted knowledge base: id=%s", kb_id)


# =============================================================
# CONNECTOR ENDPOINTS
# =============================================================


@router.post("/connectors", status_code=201)
async def create_connector(req: CreateConnectorRequest) -> dict[str, Any]:
    """Register a new connector."""
    connector = Connector(
        name=req.name,
        connector_type=req.connector_type,
        config=req.config,
    )
    _connectors[connector.connector_id] = connector
    return {
        "connector_id": str(connector.connector_id),
        "name": connector.name,
        "type": connector.connector_type.value,
    }


@router.get("/connectors")
async def list_connectors() -> list[dict[str, Any]]:
    """List all registered connectors."""
    return [
        {
            "connector_id": str(c.connector_id),
            "name": c.name,
            "type": c.connector_type.value,
            "enabled": c.enabled,
        }
        for c in _connectors.values()
    ]


# =============================================================
# SOURCE ENDPOINTS
# =============================================================


@router.post("/knowledge-bases/{kb_id}/sources", status_code=201)
async def add_source(kb_id: UUID, req: AddSourceRequest) -> dict[str, Any]:
    """Add a data source to a knowledge base."""
    kb = _knowledge_bases.get(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    if req.connector_id not in _connectors:
        raise HTTPException(status_code=404, detail="Connector not found")

    source = Source(
        knowledge_base_id=kb_id,
        connector_id=req.connector_id,
        name=req.name,
        description=req.description,
        location=req.location,
        file_patterns=req.file_patterns,
    )
    kb.sources.append(source)
    kb.updated_at = source.created_at

    return {
        "source_id": str(source.source_id),
        "name": source.name,
        "status": source.status.value,
    }


@router.get("/knowledge-bases/{kb_id}/sources")
async def list_sources(kb_id: UUID) -> list[dict[str, Any]]:
    """List all sources in a knowledge base."""
    kb = _knowledge_bases.get(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return [
        {
            "source_id": str(s.source_id),
            "name": s.name,
            "status": s.status.value,
            "document_count": s.document_count,
            "connector_id": str(s.connector_id),
        }
        for s in kb.sources
    ]


# =============================================================
# POLICY ENDPOINTS
# =============================================================


@router.post("/knowledge-bases/{kb_id}/policies", status_code=201)
async def attach_policy(kb_id: UUID, req: AttachPolicyRequest) -> dict[str, Any]:
    """Attach a policy to a knowledge base."""
    kb = _knowledge_bases.get(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    policy = Policy(
        knowledge_base_id=kb_id,
        name=req.name,
        policy_type=req.policy_type,
        description=req.description,
        rules=req.rules,
    )
    kb.policies.append(policy)

    return {
        "policy_id": str(policy.policy_id),
        "name": policy.name,
        "type": policy.policy_type.value,
    }


# =============================================================
# INGESTION JOB ENDPOINTS
# =============================================================


@router.post("/knowledge-bases/{kb_id}/sources/{source_id}/ingest", status_code=202)
async def trigger_ingestion(kb_id: UUID, source_id: UUID) -> dict[str, Any]:
    """Trigger an ingestion job for a source."""
    kb = _knowledge_bases.get(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    source = next((s for s in kb.sources if s.source_id == source_id), None)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    job = IngestionJob(
        source_id=source_id,
        knowledge_base_id=kb_id,
        status=IngestionJobStatus.QUEUED,
    )
    _ingestion_jobs[job.job_id] = job
    source.status = SourceStatus.ACTIVE

    return {
        "job_id": str(job.job_id),
        "status": job.status.value,
    }


@router.get("/ingestion-jobs/{job_id}")
async def get_ingestion_job(job_id: UUID) -> dict[str, Any]:
    """Get the status of an ingestion job."""
    job = _ingestion_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return job.model_dump(mode="json")


# =============================================================
# CLIENT APP ENDPOINTS
# =============================================================


@router.post("/clients", status_code=201)
async def register_client(req: RegisterClientRequest) -> dict[str, Any]:
    """Register a new client application."""
    client = ClientApp(
        name=req.name,
        description=req.description,
        allowed_knowledge_base_ids=req.allowed_knowledge_base_ids,
        rate_limit_rpm=req.rate_limit_rpm,
    )
    _client_apps[client.client_id] = client

    return {
        "client_id": str(client.client_id),
        "name": client.name,
    }


@router.get("/clients")
async def list_clients() -> list[dict[str, Any]]:
    """List all registered client applications."""
    return [
        {
            "client_id": str(c.client_id),
            "name": c.name,
            "enabled": c.enabled,
            "rate_limit_rpm": c.rate_limit_rpm,
        }
        for c in _client_apps.values()
    ]
