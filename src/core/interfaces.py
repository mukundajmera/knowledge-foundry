"""Knowledge Foundry — Abstract Interfaces & Data Models.

All subsystem contracts are defined here. Implementations live in their respective modules.
Data models used across module boundaries are also defined here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================
# DATA MODELS
# =============================================================


class ModelTier(str, Enum):
    """LLM model tier for tiered intelligence routing."""

    OPUS = "opus"
    SONNET = "sonnet"
    HAIKU = "haiku"


class LLMConfig(BaseModel):
    """Configuration for a single LLM request."""

    model: str
    tier: ModelTier = ModelTier.SONNET
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=100000)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    system_prompt: str | None = None
    stop_sequences: list[str] | None = None


class LLMResponse(BaseModel):
    """Response from an LLM provider."""

    text: str
    model: str
    tier: ModelTier
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0


class SearchResult(BaseModel):
    """A single result from vector search."""

    chunk_id: str
    document_id: str
    text: str
    score: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    """A document to be ingested into the knowledge base."""

    document_id: UUID
    tenant_id: UUID
    title: str
    content: str
    source_system: str = "manual"
    source_url: str | None = None
    author: str | None = None
    content_type: str = "documentation"
    tags: list[str] = Field(default_factory=list)
    visibility: Literal["public", "internal", "confidential", "restricted"] = "internal"
    created_date: datetime | None = None
    updated_date: datetime | None = None


class Chunk(BaseModel):
    """A chunk produced by the chunking engine."""

    chunk_id: str
    document_id: str
    tenant_id: str
    text: str
    text_hash: str
    chunk_index: int
    total_chunks: int
    title: str
    source_system: str
    source_url: str | None = None
    content_type: str
    tags: list[str] = Field(default_factory=list)
    visibility: str = "internal"
    created_date: datetime | None = None
    updated_date: datetime | None = None
    embedding: list[float] | None = None


class Entity(BaseModel):
    """A knowledge graph entity."""

    entity_id: str
    entity_type: str
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str | None = None


class Relationship(BaseModel):
    """A knowledge graph relationship."""

    source_id: str
    target_id: str
    relationship_type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class RoutingDecision(BaseModel):
    """Metadata about how a request was routed."""

    initial_tier: ModelTier
    final_tier: ModelTier
    escalated: bool = False
    escalation_reason: str | None = None
    complexity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    task_type_detected: str = "general"


class Citation(BaseModel):
    """A source citation for a generated response."""

    document_id: str
    title: str
    chunk_id: str | None = None
    section: str | None = None
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)


class RAGResponse(BaseModel):
    """Complete response from the RAG pipeline."""

    text: str
    citations: list[Citation] = Field(default_factory=list)
    routing_decision: RoutingDecision | None = None
    llm_response: LLMResponse | None = None
    search_results: list[SearchResult] = Field(default_factory=list)
    total_latency_ms: int = 0


class AgentTask(BaseModel):
    """A task delegated to a specialist agent."""

    task_id: UUID
    task_type: str
    query: str
    context: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Result returned by a specialist agent."""

    task_id: UUID
    agent_name: str
    response: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    citations: list[Citation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentContext(BaseModel):
    """Shared context for agent execution."""

    conversation_id: UUID | None = None
    user_id: UUID | None = None
    tenant_id: UUID | None = None
    history: list[dict[str, str]] = Field(default_factory=list)


class PluginManifest(BaseModel):
    """Description of a plugin's capabilities."""

    name: str
    version: str
    description: str
    actions: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class PluginResult(BaseModel):
    """Result from a plugin execution."""

    success: bool
    data: Any = None
    error: str | None = None


class GraphEntity(BaseModel):
    """An entity node returned from graph queries."""

    id: str
    type: str  # Person, Product, Technology, etc.
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str | None = None
    centrality_score: float | None = None


class GraphRelationship(BaseModel):
    """A relationship edge returned from graph queries."""

    type: str  # DEPENDS_ON, AFFECTS, etc.
    from_entity_id: str
    to_entity_id: str
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0


class GraphPath(BaseModel):
    """An ordered traversal path through the graph."""

    nodes: list[str]  # Ordered node IDs
    edges: list[str]  # Ordered relationship types
    total_confidence: float = 1.0  # Product of edge confidences


class TraversalResult(BaseModel):
    """Result of a graph traversal query."""

    entities: list[GraphEntity] = Field(default_factory=list)
    relationships: list[GraphRelationship] = Field(default_factory=list)
    paths: list[GraphPath] = Field(default_factory=list)
    connected_document_ids: list[str] = Field(default_factory=list)
    traversal_depth_reached: int = 0
    nodes_explored: int = 0
    latency_ms: int = 0


class RetrievalStrategy(str, Enum):
    """RAG retrieval strategy."""

    VECTOR_ONLY = "vector_only"
    GRAPH_ONLY = "graph_only"
    HYBRID = "hybrid"


# =============================================================
# ABSTRACT INTERFACES
# =============================================================


class LLMProvider(ABC):
    """Interface for LLM providers (Anthropic, etc.)."""

    @abstractmethod
    async def generate(self, prompt: str, config: LLMConfig) -> LLMResponse:
        """Generate a completion from the LLM."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is reachable."""
        ...

    @abstractmethod
    def get_cost_per_token(self, model: str) -> tuple[float, float]:
        """Return (input_cost_per_token, output_cost_per_token)."""
        ...


class VectorStore(ABC):
    """Interface for vector database operations."""

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        tenant_id: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        similarity_threshold: float = 0.65,
    ) -> list[SearchResult]:
        """Search for similar vectors."""
        ...

    @abstractmethod
    async def upsert(self, chunks: list[Chunk]) -> int:
        """Upsert chunks with their embeddings. Returns count inserted."""
        ...

    @abstractmethod
    async def delete_by_document(self, document_id: str, tenant_id: str) -> int:
        """Delete all chunks for a document. Returns count deleted."""
        ...

    @abstractmethod
    async def ensure_collection(self, tenant_id: str) -> None:
        """Create the collection for a tenant if it doesn't exist."""
        ...


class GraphStore(ABC):
    """Interface for graph database operations."""

    @abstractmethod
    async def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Execute a Cypher query and return results."""
        ...

    @abstractmethod
    async def add_entities(
        self,
        entities: list[Entity],
        relationships: list[Relationship],
    ) -> None:
        """Add entities and relationships to the graph."""
        ...

    @abstractmethod
    async def search_entities(
        self,
        query: str,
        tenant_id: str,
        entity_types: list[str] | None = None,
        limit: int = 10,
    ) -> list[GraphEntity]:
        """Search entities by name using full-text index."""
        ...

    @abstractmethod
    async def traverse(
        self,
        entry_entity_ids: list[str],
        tenant_id: str,
        max_hops: int = 2,
        relationship_types: list[str] | None = None,
        entity_types: list[str] | None = None,
        min_confidence: float = 0.5,
        max_results: int = 50,
    ) -> TraversalResult:
        """Traverse the graph from entry entities."""
        ...

    @abstractmethod
    async def ensure_indices(self) -> None:
        """Create constraints and indices if they don't exist."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the graph store connection."""
        ...


class EmbeddingProvider(ABC):
    """Interface for embedding generation."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Generate embedding for a single query text."""
        ...


class Cache(ABC):
    """Interface for caching operations."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Get a value from cache. Returns None on miss."""
        ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set a value in cache with optional TTL in seconds."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a key from cache."""
        ...

    @abstractmethod
    async def invalidate(self, pattern: str) -> int:
        """Delete all keys matching a pattern. Returns count deleted."""
        ...


class Agent(ABC):
    """Interface for specialist agents."""

    @abstractmethod
    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Execute a task and return the result."""
        ...

    @abstractmethod
    def get_name(self) -> str:
        """Return the agent's name."""
        ...

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """Return a list of task types this agent can handle."""
        ...


class Plugin(ABC):
    """Interface for Knowledge Foundry plugins."""

    @abstractmethod
    def manifest(self) -> PluginManifest:
        """Return the plugin manifest describing capabilities."""
        ...

    @abstractmethod
    async def execute(self, action: str, params: dict[str, Any]) -> PluginResult:
        """Execute a plugin action."""
        ...
