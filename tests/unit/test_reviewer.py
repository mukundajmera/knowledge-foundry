"""Unit tests for the Reviewer agent."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.core.interfaces import LLMResponse, ModelTier


@pytest.fixture
def mock_llm_provider():
    llm = AsyncMock()
    llm.generate = AsyncMock(
        return_value=LLMResponse(
            text=json.dumps({
                "review_result": "APPROVED",
                "issues_found": [],
                "suggestions": ["Consider adding more citations"],
                "confidence": 0.9,
            }),
            model="claude-sonnet-4-20250514",
            tier=ModelTier.SONNET,
        )
    )
    return llm


@pytest.fixture
def base_state(mock_llm_provider) -> dict[str, Any]:
    """Base orchestrator state for testing."""
    return {
        "user_query": "Review the research findings",
        "tenant_id": "default",
        "user_id": "test-user",
        "deployment_context": "general",
        "trace_id": "test-trace",
        "task_plan": [],
        "current_iteration": 0,
        "max_iterations": 5,
        "orchestration_pattern": "supervisor",
        "agent_outputs": {},
        "messages": [],
        "retrieved_documents": [],
        "graph_context": [],
        "assembled_context": "",
        "safety_verdict": None,
        "review_verdict": None,
        "final_answer": None,
        "confidence": 0.0,
        "citations": [],
        "hitl_required": False,
        "hitl_reason": None,
        "latency_budget_ms": 10_000,
        "cost_accumulated_usd": 0.0,
        "error": None,
        "next_agent": None,
        "_llm_provider": mock_llm_provider,
    }


class TestReviewerAgent:
    async def test_reviewer_approves_content(self, base_state, mock_llm_provider):
        """Reviewer approves clean content."""
        from src.agents.reviewer import reviewer_node

        base_state["task_plan"] = [
            {"id": "t1", "description": "Review answer", "assigned_agent": "reviewer", "status": "in_progress"},
        ]
        base_state["agent_outputs"] = {
            "researcher": {"findings": "KF uses PostgreSQL 16 for primary storage."},
        }

        result = await reviewer_node(base_state)

        assert "reviewer" in result["agent_outputs"]
        assert result["agent_outputs"]["reviewer"]["review_result"] == "APPROVED"
        assert result["next_agent"] == "supervisor_plan"

    async def test_reviewer_rejects_content(self, base_state, mock_llm_provider):
        """Reviewer rejects problematic content."""
        from src.agents.reviewer import reviewer_node

        mock_llm_provider.generate.return_value = LLMResponse(
            text=json.dumps({
                "review_result": "REJECTED",
                "issues_found": [
                    {
                        "severity": "critical",
                        "category": "faithfulness",
                        "description": "Claim not supported by evidence",
                        "suggested_fix": "Remove unsupported claim",
                    }
                ],
                "suggestions": ["Revise the answer to only include sourced claims"],
                "confidence": 0.95,
            }),
            model="claude-sonnet-4-20250514",
            tier=ModelTier.SONNET,
        )

        base_state["task_plan"] = [
            {"id": "t1", "description": "Review answer", "assigned_agent": "reviewer", "status": "in_progress"},
        ]

        result = await reviewer_node(base_state)

        output = result["agent_outputs"]["reviewer"]
        assert output["review_result"] == "REJECTED"
        assert len(output["issues_found"]) == 1
        assert output["issues_found"][0]["severity"] == "critical"

    async def test_reviewer_needs_revision(self, base_state, mock_llm_provider):
        """Reviewer flags content for revision."""
        from src.agents.reviewer import reviewer_node

        mock_llm_provider.generate.return_value = LLMResponse(
            text=json.dumps({
                "review_result": "NEEDS_REVISION",
                "issues_found": [
                    {"severity": "warning", "category": "completeness", "description": "Missing details"},
                ],
                "suggestions": ["Add more context about deployment"],
                "confidence": 0.8,
            }),
            model="claude-sonnet-4-20250514",
            tier=ModelTier.SONNET,
        )

        result = await reviewer_node(base_state)

        assert result["agent_outputs"]["reviewer"]["review_result"] == "NEEDS_REVISION"

    async def test_reviewer_no_llm(self, base_state):
        """Returns default APPROVED when LLM not available."""
        from src.agents.reviewer import reviewer_node

        base_state["_llm_provider"] = None
        result = await reviewer_node(base_state)

        assert result["agent_outputs"]["reviewer"]["review_result"] == "APPROVED"
        assert result["agent_outputs"]["reviewer"]["confidence"] == 0.0

    async def test_reviewer_marks_task_completed(self, base_state, mock_llm_provider):
        """Reviewer marks its task as completed in the plan."""
        from src.agents.reviewer import reviewer_node

        base_state["task_plan"] = [
            {"id": "t1", "description": "Research", "assigned_agent": "researcher", "status": "completed"},
            {"id": "t2", "description": "Review", "assigned_agent": "reviewer", "status": "in_progress"},
        ]

        result = await reviewer_node(base_state)

        # Task should be marked completed
        reviewer_task = [t for t in result["task_plan"] if t["assigned_agent"] == "reviewer"][0]
        assert reviewer_task["status"] == "completed"
        assert reviewer_task["result"] is not None

    async def test_reviewer_includes_final_answer_context(self, base_state, mock_llm_provider):
        """Reviewer uses final_answer when present as review context."""
        from src.agents.reviewer import reviewer_node

        base_state["final_answer"] = "PostgreSQL 16 is the primary database."

        result = await reviewer_node(base_state)

        # Verify LLM was called (meaning it processed the context)
        mock_llm_provider.generate.assert_called_once()
        prompt = mock_llm_provider.generate.call_args[0][0]
        assert "Final answer:" in prompt

    async def test_reviewer_handles_malformed_llm_response(self, base_state, mock_llm_provider):
        """Reviewer gracefully handles non-JSON LLM response."""
        from src.agents.reviewer import reviewer_node

        mock_llm_provider.generate.return_value = LLMResponse(
            text="This is not valid JSON",
            model="claude-sonnet-4-20250514",
            tier=ModelTier.SONNET,
        )

        result = await reviewer_node(base_state)

        # Should fallback to default approved
        assert result["agent_outputs"]["reviewer"]["review_result"] == "APPROVED"
        assert result["agent_outputs"]["reviewer"]["confidence"] == 0.5
