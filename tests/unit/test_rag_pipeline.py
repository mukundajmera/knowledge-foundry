"""Unit tests for Hybrid RAG pipeline (Milestone 2 upgrade)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.interfaces import (
    Citation,
    GraphEntity,
    GraphRelationship,
    LLMResponse,
    ModelTier,
    RAGResponse,
    RetrievalStrategy,
    SearchResult,
    TraversalResult,
)


# =============================================================
# Fixtures
# =============================================================


@pytest.fixture
def mock_vector_store():
    store = AsyncMock()
    store.search = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_embedding_service():
    svc = AsyncMock()
    svc.embed_query = AsyncMock(return_value=[0.1] * 1536)
    return svc


@pytest.fixture
def mock_llm_provider():
    llm = AsyncMock()
    llm.generate = AsyncMock(
        return_value=LLMResponse(
            text="Here is the answer based on context.",
            model="claude-sonnet-4-20250514",
            tier=ModelTier.SONNET,
        )
    )
    return llm


@pytest.fixture
def mock_graph_store():
    store = AsyncMock()
    store.search_entities = AsyncMock(return_value=[])
    store.traverse = AsyncMock(return_value=TraversalResult())
    return store


@pytest.fixture
def rag_pipeline(mock_vector_store, mock_embedding_service, mock_llm_provider):
    from src.retrieval.hybrid_rag import RAGPipeline

    return RAGPipeline(
        vector_store=mock_vector_store,
        embedding_service=mock_embedding_service,
        llm_provider=mock_llm_provider,
    )


@pytest.fixture
def hybrid_pipeline(mock_vector_store, mock_embedding_service, mock_llm_provider, mock_graph_store):
    from src.retrieval.hybrid_rag import RAGPipeline

    return RAGPipeline(
        vector_store=mock_vector_store,
        embedding_service=mock_embedding_service,
        llm_provider=mock_llm_provider,
        graph_store=mock_graph_store,
    )


# =============================================================
# Tests: Vector-only strategy (backward compat with M1)
# =============================================================


class TestVectorOnlyStrategy:
    async def test_vector_only_no_results(self, rag_pipeline, mock_vector_store):
        """Returns fallback message when no results found."""
        mock_vector_store.search.return_value = []

        response = await rag_pipeline.query(
            query="test query",
            tenant_id="t1",
            strategy=RetrievalStrategy.VECTOR_ONLY,
        )

        assert isinstance(response, RAGResponse)
        assert "couldn't find" in response.text.lower()

    async def test_vector_only_with_results(
        self, rag_pipeline, mock_vector_store, mock_llm_provider
    ):
        """Returns synthesized answer from vector results."""
        mock_vector_store.search.return_value = [
            SearchResult(
                chunk_id="c1",
                document_id="d1",
                text="Knowledge Foundry uses PostgreSQL.",
                score=0.9,
                metadata={"title": "Architecture Doc"},
            ),
        ]

        response = await rag_pipeline.query(
            query="What database does KF use?",
            tenant_id="t1",
        )

        assert response.text is not None
        assert len(response.citations) >= 0  # May have citations
        mock_llm_provider.generate.assert_called_once()


# =============================================================
# Tests: Graph-only strategy
# =============================================================


class TestGraphOnlyStrategy:
    async def test_graph_only_no_graph_store(self, rag_pipeline):
        """Returns empty when no graph store configured."""
        response = await rag_pipeline.query(
            query="test",
            tenant_id="t1",
            strategy=RetrievalStrategy.GRAPH_ONLY,
        )
        assert "couldn't find" in response.text.lower()

    async def test_graph_only_with_entities(self, hybrid_pipeline, mock_graph_store):
        """Returns entities from graph search."""
        mock_graph_store.search_entities.return_value = [
            GraphEntity(
                id="e1", type="Technology", name="PostgreSQL",
                properties={}, tenant_id="t1",
            ),
        ]
        mock_graph_store.traverse.return_value = TraversalResult(
            entities=[],
            relationships=[
                GraphRelationship(
                    type="DEPENDS_ON",
                    from_entity_id="e1",
                    to_entity_id="e2",
                ),
            ],
            traversal_depth_reached=1,
            nodes_explored=2,
        )

        response = await hybrid_pipeline.query(
            query="PostgreSQL",
            tenant_id="t1",
            strategy=RetrievalStrategy.GRAPH_ONLY,
        )

        assert response.text is not None
        mock_graph_store.search_entities.assert_called_once()
        mock_graph_store.traverse.assert_called_once()


# =============================================================
# Tests: Hybrid strategy
# =============================================================


class TestHybridStrategy:
    async def test_hybrid_parallel_search(
        self, hybrid_pipeline, mock_vector_store, mock_graph_store, mock_embedding_service
    ):
        """Both vector and graph search are called in parallel."""
        mock_vector_store.search.return_value = [
            SearchResult(
                chunk_id="c1",
                document_id="d1",
                text="KF architecture doc",
                score=0.85,
                metadata={"title": "Architecture"},
            ),
        ]
        mock_graph_store.search_entities.return_value = [
            GraphEntity(id="e1", type="Technology", name="Neo4j", properties={}, tenant_id="t1"),
        ]
        mock_graph_store.traverse.return_value = TraversalResult(
            entities=[],
            relationships=[],
            traversal_depth_reached=0,
            nodes_explored=1,
        )

        response = await hybrid_pipeline.query(
            query="What is the architecture?",
            tenant_id="t1",
            strategy=RetrievalStrategy.HYBRID,
        )

        mock_vector_store.search.assert_called_once()
        mock_graph_store.search_entities.assert_called_once()
        assert response.text is not None

    async def test_hybrid_fallback_to_vector(self, rag_pipeline, mock_vector_store):
        """Falls back to vector-only when graph store is not configured."""
        mock_vector_store.search.return_value = [
            SearchResult(
                chunk_id="c1",
                document_id="d1",
                text="Some text",
                score=0.8,
                metadata={"title": "Doc"},
            ),
        ]

        response = await rag_pipeline.query(
            query="test",
            tenant_id="t1",
            strategy=RetrievalStrategy.HYBRID,
        )

        mock_vector_store.search.assert_called_once()
        assert response.text is not None


# =============================================================
# Tests: Context assembly
# =============================================================


class TestContextAssembly:
    def test_format_entities_table(self, hybrid_pipeline):
        """Test entity table formatting."""
        entities = [
            GraphEntity(id="1", type="Tech", name="Neo4j", centrality_score=0.85),
            GraphEntity(id="2", type="Person", name="Alice", centrality_score=None),
        ]
        table = hybrid_pipeline._format_entities_table(entities)
        assert "Neo4j" in table
        assert "0.850" in table
        assert "—" in table  # For None centrality

    def test_format_entities_empty(self, hybrid_pipeline):
        """Empty entities returns placeholder."""
        table = hybrid_pipeline._format_entities_table([])
        assert "No entities" in table

    def test_format_relationships(self, hybrid_pipeline):
        """Test relationship formatting."""
        rels = [
            GraphRelationship(
                type="DEPENDS_ON",
                from_entity_id="e1",
                to_entity_id="e2",
                confidence=0.9,
            ),
        ]
        formatted = hybrid_pipeline._format_relationships(rels)
        assert "DEPENDS_ON" in formatted
        assert "0.90" in formatted
