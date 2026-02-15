"""Knowledge Foundry — Dependency Injection Container.

Centralizes creation and lifecycle management for all infrastructure services.
The `ServiceContainer` is initialized in the FastAPI lifespan and stored on
`app.state` so that routes can access services via `request.app.state`.

Service dependencies form this graph::

    Settings ──► AnthropicProvider ──► LLMRouter
                                         │
    Settings ──► Redis (optional) ─────► EmbeddingService
                                         │
    Settings ──► QdrantVectorStore ──────┤
                                         ▼
    Settings ──► Neo4jGraphStore ──────► RAGPipeline (hybrid)
                                         │
    SemanticChunker ◄────────────────────┤
                                         ▼
    EntityExtractor ◄────────────────── AgentGraph (LangGraph)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import redis.asyncio as aioredis
from qdrant_client import AsyncQdrantClient

from src.core.config import Settings, get_settings
from src.llm.providers import (
    AnthropicProvider,
    LMStudioProvider,
    OllamaProvider,
    OracleCodeAssistProvider,
)
from src.llm.router import LLMRouter
from src.retrieval.chunking import SemanticChunker
from src.retrieval.embeddings import EmbeddingService
from src.retrieval.hybrid_rag import RAGPipeline
from src.retrieval.vector_store import QdrantVectorStore
from src.graph.graph_store import Neo4jGraphStore
from src.graph.extraction import EntityRelationshipExtractor
from src.agents.graph_builder import compile_orchestrator
from src.api.middleware.rate_limit import RateLimiter
from src.cache.response_cache import ResponseCache, create_response_cache, create_retrieval_cache
from src.compliance.audit import AuditTrail

logger = logging.getLogger(__name__)


@dataclass
class ServiceContainer:
    """Holds all initialized service instances.

    Created during app startup and attached to ``app.state.services``.
    Closed during app shutdown.
    """

    settings: Settings
    # Infrastructure clients
    qdrant_client: AsyncQdrantClient | None = None
    redis_client: Any | None = None  # aioredis.Redis

    # Service instances
    llm_provider: AnthropicProvider | None = None
    llm_router: LLMRouter | None = None
    vector_store: QdrantVectorStore | None = None
    embedding_service: EmbeddingService | None = None
    chunker: SemanticChunker | None = None
    rag_pipeline: RAGPipeline | None = None

    # Graph & agents (Milestone 2)
    graph_store: Neo4jGraphStore | None = None
    entity_extractor: EntityRelationshipExtractor | None = None
    agent_graph: Any | None = None  # Compiled LangGraph

    # Security & caching (Milestone 3)
    rate_limiter: RateLimiter | None = None
    audit_trail: AuditTrail | None = None
    response_cache: ResponseCache | None = None
    retrieval_cache: ResponseCache | None = None

    # Startup/shutdown tracking
    _initialized: bool = field(default=False, repr=False)

    @property
    def is_ready(self) -> bool:
        """Check if all critical services are initialized."""
        return self._initialized and all([
            self.llm_provider,
            self.vector_store,
            self.embedding_service,
            self.rag_pipeline,
        ])


async def create_services(settings: Settings | None = None) -> ServiceContainer:
    """Initialize all services and return a populated container.

    This is the main DI entry point. Each service is created in dependency
    order, with graceful degradation for optional services (Redis).

    Args:
        settings: Application settings. Uses cached singleton if not provided.

    Returns:
        Fully initialized ServiceContainer.
    """
    settings = settings or get_settings()
    container = ServiceContainer(settings=settings)

    # --- 1. Redis (optional — embedding cache) ---
    try:
        container.redis_client = aioredis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
            password=settings.redis.password or None,
            decode_responses=True,
        )
        await container.redis_client.ping()
        logger.info("Redis connected: %s:%d", settings.redis.host, settings.redis.port)
    except Exception as exc:
        logger.warning("Redis unavailable (cache disabled): %s", exc)
        container.redis_client = None

    # --- 2. Qdrant vector store ---
    try:
        container.qdrant_client = AsyncQdrantClient(
            host=settings.qdrant.host,
            port=settings.qdrant.port,
            api_key=settings.qdrant.api_key or None,
            timeout=10,
        )
        container.vector_store = QdrantVectorStore(
            client=container.qdrant_client,
            settings=settings.qdrant,
        )
        logger.info("Qdrant connected: %s:%d", settings.qdrant.host, settings.qdrant.port)
    except Exception as exc:
        logger.error("Qdrant connection failed: %s", exc)
        container.vector_store = None

    # --- 3. LLM provider + router ---
    try:
        container.llm_provider = AnthropicProvider(settings=settings)
        container.llm_router = LLMRouter(
            provider=container.llm_provider,
            settings=settings,
        )
        logger.info("Anthropic LLM provider initialized")
    except Exception as exc:
        logger.error("LLM provider initialization failed: %s", exc)

    # --- 3b. Optional providers (Oracle, LM Studio, Ollama) ---
    if container.llm_router:
        # Oracle Code Assist (cloud, requires endpoint + key)
        if settings.oracle.endpoint and settings.oracle.api_key:
            try:
                oracle_provider = OracleCodeAssistProvider(settings=settings.oracle)
                container.llm_router.register_provider("oracle", oracle_provider)
                logger.info("Oracle Code Assist provider registered")
            except Exception as exc:
                logger.warning("Oracle Code Assist unavailable: %s", exc)

        # LM Studio (local)
        try:
            lmstudio_provider = LMStudioProvider(settings=settings.lmstudio)
            if await lmstudio_provider.health_check():
                container.llm_router.register_provider("lmstudio", lmstudio_provider)
                logger.info("LM Studio provider registered")
            else:
                logger.info("LM Studio not running — skipped")
        except Exception as exc:
            logger.info("LM Studio unavailable: %s", exc)

        # Ollama (local)
        try:
            ollama_provider = OllamaProvider(settings=settings.ollama)
            if await ollama_provider.health_check():
                container.llm_router.register_provider("ollama", ollama_provider)
                logger.info("Ollama provider registered")
            else:
                logger.info("Ollama not running — skipped")
        except Exception as exc:
            logger.info("Ollama unavailable: %s", exc)

    # --- 4. Embedding service ---
    try:
        container.embedding_service = EmbeddingService(
            redis_client=container.redis_client,
        )
        logger.info("Embedding service initialized (cache=%s)", container.redis_client is not None)
    except Exception as exc:
        logger.error("Embedding service initialization failed: %s", exc)

    # --- 5. Semantic chunker ---
    container.chunker = SemanticChunker()

    # --- 6. Neo4j graph store (optional) ---
    try:
        container.graph_store = Neo4jGraphStore(settings=settings.neo4j)
        if await container.graph_store.health_check():
            await container.graph_store.ensure_indices()
            logger.info("Neo4j connected: %s", settings.neo4j.bolt_uri)
        else:
            logger.warning("Neo4j unreachable — graph features disabled")
            container.graph_store = None
    except Exception as exc:
        logger.warning("Neo4j unavailable (graph disabled): %s", exc)
        container.graph_store = None

    # --- 7. RAG pipeline (requires vector store + embedding + LLM) ---
    if container.vector_store and container.embedding_service and container.llm_provider:
        container.rag_pipeline = RAGPipeline(
            vector_store=container.vector_store,
            embedding_service=container.embedding_service,
            llm_provider=container.llm_provider,
            graph_store=container.graph_store,
        )
        logger.info("RAG pipeline initialized (graph=%s)", container.graph_store is not None)
    else:
        missing = []
        if not container.vector_store:
            missing.append("vector_store")
        if not container.embedding_service:
            missing.append("embedding_service")
        if not container.llm_provider:
            missing.append("llm_provider")
        logger.warning("RAG pipeline NOT initialized — missing: %s", ", ".join(missing))

    # --- 8. Entity extractor ---
    if container.llm_provider:
        container.entity_extractor = EntityRelationshipExtractor(
            llm_provider=container.llm_provider,
        )

    # --- 9. Agent orchestrator graph ---
    try:
        container.agent_graph = compile_orchestrator(
            llm_provider=container.llm_provider,
            rag_pipeline=container.rag_pipeline,
        )
        logger.info("Agent orchestrator graph compiled")
    except Exception as exc:
        logger.warning("Agent graph compilation failed: %s", exc)

    # --- 10. Security & caching (Milestone 3) ---
    container.rate_limiter = RateLimiter()
    container.audit_trail = AuditTrail()
    container.response_cache = create_response_cache()
    container.retrieval_cache = create_retrieval_cache()
    logger.info("Security & caching services initialized")

    container._initialized = True
    return container


async def close_services(container: ServiceContainer) -> None:
    """Gracefully shut down all services.

    Args:
        container: The service container to tear down.
    """
    if container.graph_store:
        try:
            await container.graph_store.close()
            logger.info("Neo4j client closed")
        except Exception as exc:
            logger.warning("Error closing Neo4j: %s", exc)

    if container.vector_store:
        try:
            await container.vector_store.close()
            logger.info("Qdrant client closed")
        except Exception as exc:
            logger.warning("Error closing Qdrant: %s", exc)

    if container.redis_client:
        try:
            await container.redis_client.aclose()
            logger.info("Redis client closed")
        except Exception as exc:
            logger.warning("Error closing Redis: %s", exc)

    container._initialized = False


async def check_health(container: ServiceContainer) -> dict[str, str]:
    """Check the health of all services for the readiness probe.

    Returns:
        Dict mapping service name → status ("ok" or "unavailable").
    """
    checks: dict[str, str] = {"api": "ok"}

    # Qdrant
    if container.qdrant_client:
        try:
            collections = await container.qdrant_client.get_collections()
            checks["qdrant"] = "ok"
        except Exception:
            checks["qdrant"] = "unavailable"
    else:
        checks["qdrant"] = "unavailable"

    # Redis
    if container.redis_client:
        try:
            await container.redis_client.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "unavailable"
    else:
        checks["redis"] = "unavailable (optional)"

    # LLM
    checks["llm"] = "ok" if container.llm_provider else "unavailable"

    # Embedding
    checks["embedding"] = "ok" if container.embedding_service else "unavailable"

    # RAG
    checks["rag_pipeline"] = "ok" if container.rag_pipeline else "unavailable"

    # Neo4j
    if container.graph_store:
        try:
            is_healthy = await container.graph_store.health_check()
            checks["neo4j"] = "ok" if is_healthy else "unavailable"
        except Exception:
            checks["neo4j"] = "unavailable"
    else:
        checks["neo4j"] = "unavailable (optional)"

    # Agent graph
    checks["agent_graph"] = "ok" if container.agent_graph else "unavailable"

    return checks
