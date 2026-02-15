"""Tests for graph-aware document ingestion."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import create_app
from src.core.dependencies import ServiceContainer
from src.core.interfaces import Chunk, Entity, Relationship


@pytest.fixture
def mock_container_with_graph() -> ServiceContainer:
    """Service container with graph store and entity extractor mocked."""
    from src.core.config import Settings

    container = ServiceContainer(settings=Settings())
    container._initialized = True

    # Mock vector store
    container.vector_store = AsyncMock()
    container.vector_store.ensure_collection = AsyncMock()
    container.vector_store.upsert = AsyncMock(return_value=2)
    container.vector_store.close = AsyncMock()

    # Mock LLM provider
    container.llm_provider = AsyncMock()

    # Mock embedding service
    container.embedding_service = AsyncMock()
    container.embedding_service.embed = AsyncMock(return_value=[[0.1] * 3072, [0.2] * 3072])

    # Mock chunker
    container.chunker = MagicMock()
    chunk1 = MagicMock(spec=Chunk)
    chunk1.text = "Knowledge Foundry uses PostgreSQL."
    chunk1.embedding = None
    chunk2 = MagicMock(spec=Chunk)
    chunk2.text = "Neo4j stores entity relationships."
    chunk2.embedding = None
    container.chunker.chunk_document = MagicMock(return_value=[chunk1, chunk2])

    # Mock RAG pipeline
    container.rag_pipeline = AsyncMock()

    # Mock graph store
    container.graph_store = AsyncMock()
    container.graph_store.add_entities = AsyncMock()

    # Mock entity extractor
    container.entity_extractor = AsyncMock()
    mock_extraction = MagicMock()
    container.entity_extractor.extract_from_document = AsyncMock(return_value=mock_extraction)
    container.entity_extractor.to_graph_models = MagicMock(return_value=(
        [MagicMock(spec=Entity), MagicMock(spec=Entity)],  # 2 entities
        [MagicMock(spec=Relationship)],  # 1 relationship
    ))

    # Mock Redis/Qdrant for health
    container.redis_client = AsyncMock()
    container.redis_client.ping = AsyncMock()
    container.qdrant_client = AsyncMock()
    container.qdrant_client.get_collections = AsyncMock()

    return container


@pytest.fixture
def app_with_graph(mock_container_with_graph: ServiceContainer):
    application = create_app()
    application.state.services = mock_container_with_graph
    return application


@pytest.fixture
async def client_with_graph(app_with_graph):
    transport = ASGITransport(app=app_with_graph)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestGraphAwareIngestion:
    @pytest.mark.asyncio
    async def test_ingest_with_entity_extraction(
        self, client_with_graph: AsyncClient, mock_container_with_graph: ServiceContainer
    ) -> None:
        """Ingestion extracts entities and stores them in graph."""
        resp = await client_with_graph.post(
            "/v1/documents/ingest",
            json={
                "tenant_id": "00000000-0000-0000-0000-000000000001",
                "documents": [
                    {"title": "Architecture Doc", "content": "KF uses PostgreSQL and Neo4j."}
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        # Verify chunks were ingested
        assert data["total_chunks"] == 2

        # Verify entities were extracted
        assert data["ingested"][0]["entities_extracted"] == 2
        assert data["ingested"][0]["relationships_extracted"] == 1

        # Verify graph store was called
        mock_container_with_graph.graph_store.add_entities.assert_called_once()
        mock_container_with_graph.entity_extractor.extract_from_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingest_without_graph_store(self) -> None:
        """Ingestion works normally when graph store is unavailable."""
        from src.core.config import Settings

        container = ServiceContainer(settings=Settings())
        container._initialized = True
        container.vector_store = AsyncMock()
        container.vector_store.ensure_collection = AsyncMock()
        container.vector_store.upsert = AsyncMock(return_value=1)
        container.embedding_service = AsyncMock()
        container.embedding_service.embed = AsyncMock(return_value=[[0.1] * 3072])
        container.chunker = MagicMock()
        chunk = MagicMock(spec=Chunk)
        chunk.text = "Test content"
        chunk.embedding = None
        container.chunker.chunk_document = MagicMock(return_value=[chunk])
        container.graph_store = None  # No graph store
        container.entity_extractor = None  # No extractor

        application = create_app()
        application.state.services = container

        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/v1/documents/ingest",
                json={
                    "tenant_id": "00000000-0000-0000-0000-000000000001",
                    "documents": [
                        {"title": "Test", "content": "Content without graph."}
                    ],
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ingested"][0]["entities_extracted"] == 0
        assert data["ingested"][0]["relationships_extracted"] == 0

    @pytest.mark.asyncio
    async def test_ingest_graph_extraction_failure_non_fatal(
        self, mock_container_with_graph: ServiceContainer
    ) -> None:
        """Graph extraction failure does NOT fail the ingestion."""
        mock_container_with_graph.entity_extractor.extract_from_document = AsyncMock(
            side_effect=RuntimeError("Neo4j timeout")
        )

        application = create_app()
        application.state.services = mock_container_with_graph

        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/v1/documents/ingest",
                json={
                    "tenant_id": "00000000-0000-0000-0000-000000000001",
                    "documents": [
                        {"title": "Test", "content": "Content with failing graph."}
                    ],
                },
            )
        assert resp.status_code == 200  # Ingestion succeeds
        data = resp.json()
        assert data["total_chunks"] == 2  # Vector store ingestion worked
        assert data["ingested"][0]["entities_extracted"] == 0  # Graph extraction failed
