"""Tests for POST /v1/orchestrate — multi-agent orchestrator endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import create_app
from src.core.dependencies import ServiceContainer


@pytest.fixture
def mock_container() -> ServiceContainer:
    """Create a mock service container with agent graph."""
    from src.core.config import Settings

    container = ServiceContainer(settings=Settings())
    container._initialized = True

    # Mock agent graph
    container.agent_graph = MagicMock()

    # Mock other services needed for health checks
    container.llm_provider = AsyncMock()
    container.vector_store = AsyncMock()
    container.vector_store.close = AsyncMock()
    container.embedding_service = AsyncMock()
    container.rag_pipeline = AsyncMock()
    container.redis_client = AsyncMock()
    container.redis_client.ping = AsyncMock()
    container.qdrant_client = AsyncMock()
    container.qdrant_client.get_collections = AsyncMock()

    return container


@pytest.fixture
def app(mock_container: ServiceContainer):
    application = create_app()
    application.state.services = mock_container
    return application


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestOrchestratorRoute:
    @pytest.mark.asyncio
    async def test_orchestrate_requires_body(self, client: AsyncClient) -> None:
        resp = await client.post("/v1/orchestrate")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_orchestrate_success(self, client: AsyncClient) -> None:
        mock_result = {
            "answer": "Knowledge Foundry uses PostgreSQL.",
            "confidence": 0.85,
            "citations": [{"document_id": "d1", "title": "Arch Doc"}],
            "agent_outputs": {"researcher": {"findings": "..."}, "coder": {"code": "..."}},
            "orchestration_pattern": "supervisor",
            "safety_verdict": {"safe": True, "action": "ALLOW"},
            "hitl_required": False,
            "hitl_reason": None,
            "iterations": 2,
            "cost_usd": 0.003,
            "trace_id": "abc-123",
        }

        with patch(
            "src.agents.graph_builder.run_orchestrator",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.post(
                "/v1/orchestrate",
                json={
                    "query": "What database does KF use?",
                    "tenant_id": "00000000-0000-0000-0000-000000000001",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Knowledge Foundry uses PostgreSQL."
        assert data["confidence"] == 0.85
        assert len(data["citations"]) == 1
        assert set(data["agents_used"]) == {"researcher", "coder"}
        assert data["orchestration_pattern"] == "supervisor"
        assert data["safety_verdict"]["safe"] is True
        assert data["hitl_required"] is False
        assert data["performance"]["iterations"] == 2
        assert data["performance"]["cost_usd"] == 0.003

    @pytest.mark.asyncio
    async def test_orchestrate_no_agent_graph(self) -> None:
        """Returns 503 when agent graph is not initialized."""
        from src.core.config import Settings

        container = ServiceContainer(settings=Settings())
        container._initialized = True
        container.agent_graph = None  # No agent graph

        application = create_app()
        application.state.services = container

        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/v1/orchestrate",
                json={
                    "query": "Test",
                    "tenant_id": "00000000-0000-0000-0000-000000000001",
                },
            )
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_orchestrate_internal_error(self, client: AsyncClient) -> None:
        """Returns 500 when orchestrator raises an exception."""
        with patch(
            "src.agents.graph_builder.run_orchestrator",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM failed"),
        ):
            resp = await client.post(
                "/v1/orchestrate",
                json={
                    "query": "What is KF?",
                    "tenant_id": "00000000-0000-0000-0000-000000000001",
                },
            )
        assert resp.status_code == 500
        assert "RuntimeError" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_orchestrate_with_custom_params(self, client: AsyncClient) -> None:
        """Custom deployment_context and max_iterations are forwarded."""
        mock_result = {
            "answer": "Risk assessment...",
            "confidence": 0.9,
            "citations": [],
            "agent_outputs": {"risk": {}},
            "orchestration_pattern": "supervisor",
            "safety_verdict": None,
            "hitl_required": True,
            "hitl_reason": "Financial context requires HITL",
            "iterations": 1,
            "cost_usd": 0.01,
            "trace_id": "xyz",
        }

        with patch(
            "src.agents.graph_builder.run_orchestrator",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            resp = await client.post(
                "/v1/orchestrate",
                json={
                    "query": "Evaluate investment risk",
                    "tenant_id": "00000000-0000-0000-0000-000000000001",
                    "deployment_context": "financial",
                    "max_iterations": 10,
                    "user_id": "test-user",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["hitl_required"] is True
        # Verify the correct params were forwarded
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["deployment_context"] == "financial"
        assert call_kwargs["max_iterations"] == 10
        assert call_kwargs["user_id"] == "test-user"
