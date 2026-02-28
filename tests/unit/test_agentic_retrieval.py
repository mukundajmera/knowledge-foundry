"""Tests for src.retrieval.agentic — Agentic Retrieval Engine."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.core.interfaces import LLMResponse, ModelTier, SearchResult
from src.retrieval.agentic import (
    AgenticReasoningEffort,
    AgenticRetrievalEngine,
    AgenticRetrievalRequest,
    BasicRetrievalRequest,
    RetrievalMode,
    RetrievalResponse,
    SubQuery,
)


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    store = AsyncMock()
    store.search = AsyncMock(return_value=[
        SearchResult(
            chunk_id="c1",
            document_id="d1",
            text="Knowledge Foundry is a platform.",
            score=0.9,
            metadata={"title": "Overview"},
        ),
        SearchResult(
            chunk_id="c2",
            document_id="d2",
            text="RAG combines retrieval and generation.",
            score=0.85,
            metadata={"title": "RAG Guide"},
        ),
    ])
    return store


@pytest.fixture
def mock_embedding_service() -> AsyncMock:
    svc = AsyncMock()
    svc.embed_query = AsyncMock(return_value=[0.1] * 3072)
    return svc


@pytest.fixture
def mock_llm_provider() -> AsyncMock:
    provider = AsyncMock()
    provider.generate = AsyncMock(return_value=LLMResponse(
        text="Based on the context, Knowledge Foundry is a RAG platform. [Source 1]",
        model="sonnet",
        tier=ModelTier.SONNET,
    ))
    return provider


@pytest.fixture
def engine(mock_vector_store, mock_embedding_service, mock_llm_provider) -> AgenticRetrievalEngine:
    return AgenticRetrievalEngine(
        vector_store=mock_vector_store,
        embedding_service=mock_embedding_service,
        llm_provider=mock_llm_provider,
    )


class TestBasicRetrieval:
    """Tests for simple top-K retrieval."""

    async def test_basic_retrieve_returns_results(self, engine: AgenticRetrievalEngine) -> None:
        req = BasicRetrievalRequest(
            kb_id=uuid4(),
            query="What is Knowledge Foundry?",
            tenant_id="tenant-1",
            top_k=5,
        )
        response = await engine.basic_retrieve(req)

        assert isinstance(response, RetrievalResponse)
        assert len(response.results) == 2
        assert response.results[0].chunk_id == "c1"
        assert response.total_latency_ms >= 0

    async def test_basic_retrieve_has_one_step(self, engine: AgenticRetrievalEngine) -> None:
        req = BasicRetrievalRequest(
            kb_id=uuid4(),
            query="test",
            tenant_id="tenant-1",
        )
        response = await engine.basic_retrieve(req)
        assert len(response.steps) == 1
        assert response.steps[0].action == "retrieve"

    async def test_basic_retrieve_empty_results(
        self, mock_embedding_service: AsyncMock, mock_llm_provider: AsyncMock
    ) -> None:
        store = AsyncMock()
        store.search = AsyncMock(return_value=[])
        engine = AgenticRetrievalEngine(store, mock_embedding_service, mock_llm_provider)

        req = BasicRetrievalRequest(
            kb_id=uuid4(), query="nothing", tenant_id="t1",
        )
        response = await engine.basic_retrieve(req)
        assert len(response.results) == 0


    async def test_basic_retrieve_scopes_by_kb_id(
        self, mock_vector_store: AsyncMock, mock_embedding_service: AsyncMock, mock_llm_provider: AsyncMock
    ) -> None:
        engine = AgenticRetrievalEngine(mock_vector_store, mock_embedding_service, mock_llm_provider)
        kb_id = uuid4()
        req = BasicRetrievalRequest(
            kb_id=kb_id,
            query="test",
            tenant_id="tenant-1",
        )
        await engine.basic_retrieve(req)

        # Verify search was called with kb_id in filters
        call_kwargs = mock_vector_store.search.call_args[1]
        assert call_kwargs["filters"]["kb_id"] == str(kb_id)


class TestAgenticRetrieval:
    """Tests for agentic multi-hop retrieval."""

    async def test_agentic_retrieve_low_effort(self, engine: AgenticRetrievalEngine) -> None:
        req = AgenticRetrievalRequest(
            query="What is Knowledge Foundry?",
            tenant_id="tenant-1",
            reasoning_effort=AgenticReasoningEffort.LOW,
        )
        response = await engine.agentic_retrieve(req)

        assert isinstance(response, RetrievalResponse)
        assert response.answer != ""
        assert len(response.steps) >= 2  # decompose + retrieve + synthesize

    async def test_agentic_retrieve_medium_effort(self, engine: AgenticRetrievalEngine) -> None:
        # LLM returns sub-queries for decomposition
        engine._llm_provider.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="- What is Knowledge Foundry?\n- How does it work?",
                model="haiku",
                tier=ModelTier.HAIKU,
            ),
            LLMResponse(
                text="Knowledge Foundry is a unified knowledge platform. [Source 1]",
                model="sonnet",
                tier=ModelTier.SONNET,
            ),
        ])

        req = AgenticRetrievalRequest(
            query="Explain Knowledge Foundry comprehensively",
            tenant_id="tenant-1",
            reasoning_effort=AgenticReasoningEffort.MEDIUM,
        )
        response = await engine.agentic_retrieve(req)

        assert response.answer != ""
        # Should have: decompose + N retrieves + synthesize
        assert len(response.steps) >= 3

    async def test_agentic_retrieve_respects_token_budget(
        self, engine: AgenticRetrievalEngine
    ) -> None:
        req = AgenticRetrievalRequest(
            query="test",
            tenant_id="tenant-1",
            token_budget=10,  # Very small budget
            reasoning_effort=AgenticReasoningEffort.LOW,
        )
        response = await engine.agentic_retrieve(req)
        # Should still produce a response (even if truncated)
        assert isinstance(response, RetrievalResponse)

    async def test_agentic_retrieve_tracks_steps(self, engine: AgenticRetrievalEngine) -> None:
        req = AgenticRetrievalRequest(
            query="test",
            tenant_id="tenant-1",
            reasoning_effort=AgenticReasoningEffort.LOW,
        )
        response = await engine.agentic_retrieve(req)

        for step in response.steps:
            assert step.step_number > 0
            assert step.action in ("decompose", "retrieve", "synthesize", "refine")

    async def test_agentic_retrieve_no_results(
        self, mock_embedding_service: AsyncMock
    ) -> None:
        store = AsyncMock()
        store.search = AsyncMock(return_value=[])
        provider = AsyncMock()
        provider.generate = AsyncMock(return_value=LLMResponse(
            text="No relevant information found.",
            model="sonnet",
            tier=ModelTier.SONNET,
        ))

        engine = AgenticRetrievalEngine(store, mock_embedding_service, provider)
        req = AgenticRetrievalRequest(
            query="nothing",
            tenant_id="t1",
            reasoning_effort=AgenticReasoningEffort.LOW,
        )
        response = await engine.agentic_retrieve(req)
        assert "No relevant information" in response.answer


class TestSubQuery:
    """Tests for the SubQuery data class."""

    def test_subquery_defaults(self) -> None:
        sq = SubQuery(text="test query")
        assert sq.text == "test query"
        assert sq.results == []
        assert sq.token_count == 0
        assert sq.kb_id is None

    def test_subquery_with_kb(self) -> None:
        kb_id = uuid4()
        sq = SubQuery(text="test", kb_id=kb_id, rationale="test reason")
        assert sq.kb_id == kb_id
        assert sq.rationale == "test reason"
