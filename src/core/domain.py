"""Knowledge Foundry — Core Domain Entities.

Defines the foundational domain model for Knowledge Foundry:
KnowledgeBase, Source, Connector, IngestionJob, Index, Policy, and ClientApp.

These entities form the backbone of the unified knowledge layer, enabling
reusable topic-centric knowledge bases, automatic ingestion/indexing/vectorization,
and multi-agent retrieval.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# =============================================================
# ENUMS
# =============================================================


class ConnectorType(str, Enum):
    """Supported connector types for data ingestion."""

    FILE_SHARE = "file_share"
    GIT_REPO = "git_repo"
    S3_BUCKET = "s3_bucket"
    DATABASE = "database"
    CONFLUENCE = "confluence"
    JIRA = "jira"
    WEB_CRAWLER = "web_crawler"
    API = "api"


class SourceStatus(str, Enum):
    """Status of a data source."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING = "pending"


class IngestionJobStatus(str, Enum):
    """Status of an ingestion job."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class IndexType(str, Enum):
    """Type of search index."""

    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class PolicyType(str, Enum):
    """Type of policy attached to a knowledge base."""

    ACCESS_CONTROL = "access_control"
    DATA_RETENTION = "data_retention"
    SAFETY = "safety"
    PII_FILTER = "pii_filter"
    CONTENT_FILTER = "content_filter"


class ChunkingStrategy(str, Enum):
    """Strategy for document chunking."""

    FIXED_SIZE = "fixed_size"
    SEMANTIC = "semantic"
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"


# =============================================================
# DOMAIN ENTITIES
# =============================================================


class Connector(BaseModel):
    """A reusable connector definition for a data source type.

    Connectors encapsulate the logic and credentials needed to pull data
    from external systems (file shares, Git repos, databases, SaaS APIs).
    """

    connector_id: UUID = Field(default_factory=uuid4)
    name: str
    connector_type: ConnectorType
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Connector-specific configuration (e.g., base URL, auth method)",
    )
    credentials_ref: str | None = Field(
        default=None,
        description="Reference to encrypted credentials in the secrets store",
    )
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Source(BaseModel):
    """A specific data source within a knowledge base.

    A Source binds a Connector to a particular location/path/query
    and belongs to exactly one KnowledgeBase.
    """

    source_id: UUID = Field(default_factory=uuid4)
    knowledge_base_id: UUID
    connector_id: UUID
    name: str
    description: str = ""
    location: str = Field(
        description="Source-specific path: file path, repo URL, DB table, etc.",
    )
    file_patterns: list[str] = Field(
        default_factory=list,
        description="Glob patterns for file-based sources (e.g., ['*.md', '*.pdf'])",
    )
    status: SourceStatus = SourceStatus.PENDING
    last_synced_at: datetime | None = None
    document_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IngestionJob(BaseModel):
    """Tracks a single ingestion run for a Source.

    Captures the full lifecycle: queued → running → completed/failed.
    Stores per-run statistics for observability.
    """

    job_id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    knowledge_base_id: UUID
    status: IngestionJobStatus = IngestionJobStatus.QUEUED
    started_at: datetime | None = None
    completed_at: datetime | None = None
    documents_processed: int = 0
    documents_failed: int = 0
    chunks_created: int = 0
    embeddings_generated: int = 0
    error_message: str | None = None
    error_details: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Index(BaseModel):
    """A search index associated with a KnowledgeBase.

    Each KB can have multiple index types (vector, keyword, hybrid)
    to support different retrieval strategies.
    """

    index_id: UUID = Field(default_factory=uuid4)
    knowledge_base_id: UUID
    name: str
    index_type: IndexType
    embedding_model: str = Field(
        default="text-embedding-3-large",
        description="Model used for vector embeddings",
    )
    dimensions: int = Field(default=3072, description="Vector embedding dimensions")
    distance_metric: str = Field(default="cosine", description="Vector distance metric")
    chunk_size: int = Field(default=512, description="Target chunk size in tokens")
    chunk_overlap: int = Field(default=64, description="Chunk overlap in tokens")
    chunking_strategy: ChunkingStrategy = ChunkingStrategy.SEMANTIC
    total_chunks: int = 0
    total_documents: int = 0
    status: str = "ready"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Policy(BaseModel):
    """A policy attached to a KnowledgeBase governing data handling and access.

    Policies control access, retention, safety filtering, and content rules.
    """

    policy_id: UUID = Field(default_factory=uuid4)
    knowledge_base_id: UUID
    name: str
    policy_type: PolicyType
    description: str = ""
    rules: dict[str, Any] = Field(
        default_factory=dict,
        description="Policy-specific rules (e.g., allowed roles, retention days)",
    )
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClientApp(BaseModel):
    """An application or agent registered to consume knowledge bases.

    ClientApps authenticate via API keys and can be scoped to specific
    knowledge bases with rate limits and policies.
    """

    client_id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    api_key_hash: str = Field(
        default="",
        description="Hashed API key for authentication",
    )
    allowed_knowledge_base_ids: list[UUID] = Field(
        default_factory=list,
        description="KBs this client can access; empty means all",
    )
    rate_limit_rpm: int = Field(default=60, description="Requests per minute limit")
    rate_limit_tpm: int = Field(default=100000, description="Tokens per minute limit")
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeBase(BaseModel):
    """A reusable, topic-centric knowledge base.

    The top-level aggregate that groups sources, indices, and policies.
    Multiple agents and applications can share a single KnowledgeBase
    through the retrieval API.
    """

    kb_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    name: str
    description: str = ""
    sources: list[Source] = Field(default_factory=list)
    indices: list[Index] = Field(default_factory=list)
    policies: list[Policy] = Field(default_factory=list)
    embedding_model: str = Field(
        default="text-embedding-3-large",
        description="Default embedding model for this KB",
    )
    chunking_strategy: ChunkingStrategy = ChunkingStrategy.SEMANTIC
    default_chunk_size: int = 512
    default_chunk_overlap: int = 64
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================
# INGESTION LIFECYCLE EVENTS
# =============================================================


class IngestionEvent(BaseModel):
    """An event emitted during the ingestion lifecycle.

    Supports observability and debugging of the ingestion pipeline.
    """

    event_id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    event_type: str  # e.g., "document_discovered", "chunk_created", "embedding_generated"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
