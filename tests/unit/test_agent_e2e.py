"""End-to-end tests for the multi-agent orchestrator flow."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.interfaces import LLMResponse, ModelTier, RAGResponse


@pytest.fixture
def mock_llm_provider():
    """LLM provider that returns valid JSON for each agent type."""
    llm = AsyncMock()

    # Default: supervisor planning response
    llm.generate = AsyncMock(
        return_value=LLMResponse(
            text=json.dumps({
                "reasoning": "Simple research question",
                "sub_tasks": [
                    {
                        "id": "t1",
                        "description": "Search for info",
                        "assigned_agent": "researcher",
                        "depends_on": [],
                    }
                ],
                "orchestration_pattern": "supervisor",
            }),
            model="claude-sonnet-4-20250514",
            tier=ModelTier.SONNET,
        )
    )
    return llm


@pytest.fixture
def mock_rag_pipeline():
    """Mock RAG pipeline for the researcher agent."""
    rag = AsyncMock()
    rag._graph_store = None
    rag.query = AsyncMock(
        return_value=RAGResponse(
            text="PostgreSQL 16 is the primary database.",
            citations=[],
            search_results=[],
            total_latency_ms=100,
        )
    )
    return rag


class TestGraphBuilderRouting:
    """Tests for the LangGraph routing logic."""

    def test_build_graph_with_reviewer(self):
        """Graph builder includes the reviewer node."""
        from src.agents.graph_builder import build_orchestrator_graph
        graph = build_orchestrator_graph()
        assert graph is not None
        # Graph should have reviewer node
        assert "reviewer" in graph.nodes

    def test_route_to_reviewer(self):
        """Router correctly routes to reviewer agent."""
        from src.agents.graph_builder import route_next_agent

        state = {"next_agent": "reviewer", "current_iteration": 0, "max_iterations": 5}
        assert route_next_agent(state) == "reviewer"

    def test_route_circuit_breaker_overrides_reviewer(self):
        """Circuit breaker overrides even when routing to reviewer."""
        from src.agents.graph_builder import route_next_agent

        state = {"next_agent": "reviewer", "current_iteration": 5, "max_iterations": 5}
        assert route_next_agent(state) == "synthesize"


class TestRunOrchestrator:
    """Tests for the run_orchestrator end-to-end function."""

    async def test_run_orchestrator_returns_result(self, mock_llm_provider, mock_rag_pipeline):
        """run_orchestrator returns a well-structured result dict."""
        from src.agents.graph_builder import compile_orchestrator, run_orchestrator

        compiled = compile_orchestrator(
            llm_provider=mock_llm_provider,
            rag_pipeline=mock_rag_pipeline,
        )

        # The compiled graph ainvoke will be mocked
        mock_result = {
            "final_answer": "PostgreSQL 16 is used.",
            "confidence": 0.85,
            "citations": [],
            "safety_verdict": {"safe": True, "action": "ALLOW"},
            "hitl_required": False,
            "hitl_reason": None,
            "agent_outputs": {"researcher": {"findings": "found it"}},
            "orchestration_pattern": "supervisor",
            "current_iteration": 2,
            "cost_accumulated_usd": 0.005,
            "trace_id": "test-trace-id",
        }

        # Mock ainvoke on the compiled graph
        compiled.ainvoke = AsyncMock(return_value=mock_result)

        result = await run_orchestrator(
            compiled_graph=compiled,
            user_query="What database does KF use?",
            tenant_id="default",
        )

        assert result["answer"] == "PostgreSQL 16 is used."
        assert result["confidence"] == 0.85
        assert result["iterations"] == 2
        assert result["cost_usd"] == 0.005
        assert "researcher" in result["agent_outputs"]

    async def test_compile_stores_dependencies(self, mock_llm_provider, mock_rag_pipeline):
        """compile_orchestrator stores dependencies on the compiled graph."""
        from src.agents.graph_builder import compile_orchestrator

        compiled = compile_orchestrator(
            llm_provider=mock_llm_provider,
            rag_pipeline=mock_rag_pipeline,
        )

        assert compiled._kf_llm_provider is mock_llm_provider
        assert compiled._kf_rag_pipeline is mock_rag_pipeline


class TestSupervisorPlanningFlow:
    """Tests for supervisor planning behavior with the graph."""

    async def test_supervisor_creates_plan_and_routes(self, mock_llm_provider):
        """Supervisor decomposes query and routes to first agent."""
        from src.agents.supervisor import supervisor_plan_node

        state: dict[str, Any] = {
            "user_query": "What database does KF use?",
            "tenant_id": "default",
            "task_plan": [],
            "current_iteration": 0,
            "max_iterations": 5,
            "agent_outputs": {},
            "_llm_provider": mock_llm_provider,
        }

        result = await supervisor_plan_node(state)

        assert result["next_agent"] == "researcher"
        assert len(result["task_plan"]) > 0
        assert result["task_plan"][0]["assigned_agent"] == "researcher"

    async def test_supervisor_routes_to_synthesize_when_done(self, mock_llm_provider):
        """Supervisor routes to synthesize when all tasks complete."""
        from src.agents.supervisor import supervisor_plan_node

        state: dict[str, Any] = {
            "user_query": "What database?",
            "tenant_id": "default",
            "task_plan": [
                {"id": "t1", "description": "Done", "assigned_agent": "researcher", "status": "completed"},
            ],
            "current_iteration": 1,
            "max_iterations": 5,
            "agent_outputs": {"researcher": {"findings": "PostgreSQL"}},
            "_llm_provider": mock_llm_provider,
        }

        result = await supervisor_plan_node(state)

        assert result["next_agent"] == "synthesize"


class TestAgentInteraction:
    """Tests for individual agent interactions within the orchestrator."""

    async def test_researcher_receives_rag_results(self, mock_llm_provider, mock_rag_pipeline):
        """Researcher agent queries RAG and returns findings."""
        from src.agents.researcher import researcher_node

        state: dict[str, Any] = {
            "user_query": "What database?",
            "tenant_id": "default",
            "task_plan": [
                {"id": "t1", "description": "Search DB info", "assigned_agent": "researcher", "status": "in_progress"},
            ],
            "agent_outputs": {},
            "_llm_provider": mock_llm_provider,
            "_rag_pipeline": mock_rag_pipeline,
        }

        result = await researcher_node(state)

        assert "researcher" in result["agent_outputs"]
        assert result["next_agent"] == "supervisor_plan"
        mock_rag_pipeline.query.assert_called_once()

    async def test_safety_check_on_clean_output(self):
        """Safety agent allows clean content through."""
        from src.agents.safety import safety_check_node

        state: dict[str, Any] = {
            "user_query": "What database?",
            "final_answer": "PostgreSQL 16 is the primary database.",
            "_llm_provider": None,  # Skip LLM check
        }

        result = await safety_check_node(state)

        assert result["safety_verdict"]["safe"] is True
        assert result["safety_verdict"]["action"] == "ALLOW"

    async def test_reviewer_in_full_flow(self, mock_llm_provider):
        """Reviewer agent processes content and returns verdict."""
        from src.agents.reviewer import reviewer_node

        mock_llm_provider.generate.return_value = LLMResponse(
            text=json.dumps({
                "review_result": "APPROVED",
                "issues_found": [],
                "suggestions": [],
                "confidence": 0.9,
            }),
            model="claude-sonnet-4-20250514",
            tier=ModelTier.SONNET,
        )

        state: dict[str, Any] = {
            "user_query": "Review this",
            "tenant_id": "default",
            "task_plan": [
                {"id": "t1", "description": "Review", "assigned_agent": "reviewer", "status": "in_progress"},
            ],
            "agent_outputs": {
                "researcher": {"findings": "PostgreSQL is used."},
            },
            "final_answer": "PostgreSQL 16 powers KF.",
            "_llm_provider": mock_llm_provider,
        }

        result = await reviewer_node(state)

        assert result["agent_outputs"]["reviewer"]["review_result"] == "APPROVED"
        assert result["next_agent"] == "supervisor_plan"
