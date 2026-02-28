"""Tests for Knowledge Foundry API routes — KB management, retrieval, and governance."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import create_app
from src.core.dependencies import ServiceContainer


@pytest.fixture
def mock_container() -> ServiceContainer:
    """Create a mock service container for API testing."""
    from src.core.config import Settings

    container = ServiceContainer(settings=Settings())
    container._initialized = True
    container.vector_store = AsyncMock()
    container.vector_store.search = AsyncMock(return_value=[])
    container.vector_store.close = AsyncMock()
    container.llm_provider = AsyncMock()
    container.embedding_service = AsyncMock()
    container.embedding_service.embed_query = AsyncMock(return_value=[0.1] * 3072)
    container.rag_pipeline = AsyncMock()
    container.chunker = MagicMock()
    container.graph_store = None
    return container


@pytest.fixture
async def client(mock_container: ServiceContainer) -> AsyncClient:
    """Create an async test client with mocked services."""
    app = create_app()
    app.state.services = mock_container

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestKnowledgeBaseAPI:
    """Tests for Knowledge Base management endpoints."""

    async def test_create_knowledge_base(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/kb/knowledge-bases", json={
            "name": "Test KB",
            "description": "A test knowledge base",
            "tenant_id": str(uuid4()),
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test KB"
        assert "kb_id" in data

    async def test_list_knowledge_bases(self, client: AsyncClient) -> None:
        # Create a KB first
        tenant_id = str(uuid4())
        await client.post("/api/v1/kb/knowledge-bases", json={
            "name": "Listed KB",
            "tenant_id": tenant_id,
        })

        resp = await client.get("/api/v1/kb/knowledge-bases")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any(kb["name"] == "Listed KB" for kb in data)

    async def test_get_knowledge_base_not_found(self, client: AsyncClient) -> None:
        resp = await client.get(f"/api/v1/kb/knowledge-bases/{uuid4()}")
        assert resp.status_code == 404

    async def test_create_connector(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/kb/connectors", json={
            "name": "git-conn",
            "connector_type": "git_repo",
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "git-conn"

    async def test_list_connectors(self, client: AsyncClient) -> None:
        await client.post("/api/v1/kb/connectors", json={
            "name": "test-conn",
            "connector_type": "file_share",
        })
        resp = await client.get("/api/v1/kb/connectors")
        assert resp.status_code == 200

    async def test_register_client(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/kb/clients", json={
            "name": "my-agent",
            "description": "A test agent",
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "my-agent"


class TestGovernanceAPI:
    """Tests for Governance API endpoints."""

    async def test_create_safety_policy(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/governance/safety-policies", json={
            "name": "test-policy",
            "blocked_categories": ["toxicity", "pii_leak"],
            "default_action": "flag",
            "rules": [
                {
                    "name": "block-toxic",
                    "category": "toxicity",
                    "action": "block",
                    "threshold": 0.7,
                }
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-policy"
        assert data["rule_count"] == 1

    async def test_list_safety_policies(self, client: AsyncClient) -> None:
        await client.post("/api/v1/governance/safety-policies", json={
            "name": "listed-policy",
            "rules": [],
        })
        resp = await client.get("/api/v1/governance/safety-policies")
        assert resp.status_code == 200

    async def test_safety_check_clean(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/governance/safety-check", json={
            "text": "Hello, how can I help you?",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is True

    async def test_create_eval_suite(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/governance/eval-suites", json={
            "name": "quality-suite",
            "probes": [
                {
                    "name": "test-probe",
                    "input_query": "What is RAG?",
                    "expected_output": "Retrieval Augmented Generation",
                }
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "quality-suite"
        assert data["probe_count"] == 1

    async def test_list_eval_suites(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/governance/eval-suites")
        assert resp.status_code == 200

    async def test_list_violations(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/governance/violations")
        assert resp.status_code == 200

    async def test_list_eval_runs(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/governance/eval-runs")
        assert resp.status_code == 200

    async def test_create_safety_policy_invalid_rule_returns_422(self, client: AsyncClient) -> None:
        """Malformed rules should return 422 validation error, not 500."""
        resp = await client.post("/api/v1/governance/safety-policies", json={
            "name": "bad-policy",
            "rules": [{"invalid_field": "no category"}],
        })
        assert resp.status_code == 422

    async def test_create_eval_suite_invalid_probe_returns_422(self, client: AsyncClient) -> None:
        """Malformed probes should return 422 validation error, not 500."""
        resp = await client.post("/api/v1/governance/eval-suites", json={
            "name": "bad-suite",
            "probes": [{"no_input_query": True}],
        })
        assert resp.status_code == 422
