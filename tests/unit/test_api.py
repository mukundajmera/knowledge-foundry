"""Tests for src.api — FastAPI routes (health, query, documents).

Tests run without live infrastructure by mocking the service container.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import create_app
from src.core.dependencies import ServiceContainer
from src.core.interfaces import (
    Citation,
    Chunk,
    LLMResponse,
    ModelTier,
    RAGResponse,
    RoutingDecision,
    SearchResult,
)


@pytest.fixture
def mock_container() -> ServiceContainer:
    """Create a mock service container with all services."""
    from src.core.config import Settings

    container = ServiceContainer(settings=Settings())
    container._initialized = True

    # Mock vector store
    container.vector_store = AsyncMock()
    container.vector_store.ensure_collection = AsyncMock()
    container.vector_store.search = AsyncMock(return_value=[])
    container.vector_store.upsert = AsyncMock(return_value=2)
    container.vector_store.delete_by_document = AsyncMock(return_value=3)
    container.vector_store.close = AsyncMock()

    # Mock LLM provider
    container.llm_provider = AsyncMock()

    # Mock embedding service
    container.embedding_service = AsyncMock()
    container.embedding_service.embed = AsyncMock(return_value=[[0.1] * 3072, [0.2] * 3072])
    container.embedding_service.embed_query = AsyncMock(return_value=[0.1] * 3072)

    # Mock chunker
    container.chunker = MagicMock()
    chunk1 = MagicMock(spec=Chunk)
    chunk1.text = "Chunk 1 text"
    chunk1.embedding = None
    chunk2 = MagicMock(spec=Chunk)
    chunk2.text = "Chunk 2 text"
    chunk2.embedding = None
    container.chunker.chunk_document = MagicMock(return_value=[chunk1, chunk2])

    # Mock RAG pipeline
    container.rag_pipeline = AsyncMock()
    container.rag_pipeline.query = AsyncMock(
        return_value=RAGResponse(
            text="Answer based on context.",
            citations=[
                Citation(
                    document_id="d1",
                    title="Test Doc",
                    chunk_id="c1",
                    relevance_score=0.92,
                ),
            ],
            routing_decision=RoutingDecision(
                initial_tier=ModelTier.SONNET,
                final_tier=ModelTier.SONNET,
                complexity_score=0.4,
                task_type_detected="rag_qa",
            ),
            llm_response=LLMResponse(
                text="Answer based on context.",
                model="claude-sonnet-4-20250514",
                tier=ModelTier.SONNET,
                input_tokens=100,
                output_tokens=50,
                latency_ms=200,
                cost_usd=0.001,
            ),
            search_results=[
                SearchResult(
                    chunk_id="c1",
                    document_id="d1",
                    text="Some context.",
                    score=0.92,
                    metadata={"title": "Test Doc"},
                ),
            ],
            total_latency_ms=250,
        )
    )

    # Mock Redis client for health check
    container.redis_client = AsyncMock()
    container.redis_client.ping = AsyncMock()

    # Mock Qdrant client for health check
    container.qdrant_client = AsyncMock()
    container.qdrant_client.get_collections = AsyncMock()

    return container


@pytest.fixture
def app(mock_container: ServiceContainer):
    """Create app with mocked services pre-injected."""
    application = create_app()
    application.state.services = mock_container
    return application


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthRoutes:
    @pytest.mark.asyncio
    async def test_health(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_ready_all_ok(self, client: AsyncClient) -> None:
        resp = await client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["checks"]["qdrant"] == "ok"
        assert data["checks"]["redis"] == "ok"
        assert data["checks"]["llm"] == "ok"
        assert data["checks"]["rag_pipeline"] == "ok"

    @pytest.mark.asyncio
    async def test_ready_degraded(self, mock_container: ServiceContainer) -> None:
        mock_container.rag_pipeline = None
        application = create_app()
        application.state.services = mock_container
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/ready")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "degraded"


class TestQueryRoute:
    @pytest.mark.asyncio
    async def test_query_requires_body(self, client: AsyncClient) -> None:
        resp = await client.post("/v1/query")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_query_success(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/v1/query",
            json={
                "query": "What is Python?",
                "tenant_id": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Answer based on context."
        assert len(data["citations"]) == 1
        assert data["citations"][0]["document_id"] == "d1"
        assert data["routing"]["initial_tier"] == "sonnet"
        assert data["performance"]["input_tokens"] == 100
        assert data["result_count"] == 1

    @pytest.mark.asyncio
    async def test_query_no_pipeline(self, mock_container: ServiceContainer) -> None:
        mock_container.rag_pipeline = None
        application = create_app()
        application.state.services = mock_container
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/v1/query",
                json={
                    "query": "Test",
                    "tenant_id": "00000000-0000-0000-0000-000000000001",
                },
            )
            assert resp.status_code == 503


class TestDocumentRoutes:
    @pytest.mark.asyncio
    async def test_ingest_requires_body(self, client: AsyncClient) -> None:
        resp = await client.post("/v1/documents/ingest")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_ingest_success(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/v1/documents/ingest",
            json={
                "tenant_id": "00000000-0000-0000-0000-000000000001",
                "documents": [
                    {"title": "Test Doc", "content": "Some content about Python."}
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] == 1
        assert data["total_chunks"] == 2  # Mock returns 2 chunks
        assert len(data["ingested"]) == 1
        assert data["ingested"][0]["title"] == "Test Doc"
        assert data["ingested"][0]["chunk_count"] == 2

    @pytest.mark.asyncio
    async def test_delete_success(self, client: AsyncClient) -> None:
        resp = await client.delete(
            "/v1/documents/00000000-0000-0000-0000-000000000001",
            params={"tenant_id": "00000000-0000-0000-0000-000000000001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["chunks_deleted"] == 3  # Mock returns 3

    @pytest.mark.asyncio
    async def test_ingest_no_services(self) -> None:
        application = create_app()
        # No services set up at all
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/v1/documents/ingest",
                json={
                    "tenant_id": "00000000-0000-0000-0000-000000000001",
                    "documents": [
                        {"title": "Test", "content": "Content."}
                    ],
                },
            )
            assert resp.status_code == 503
