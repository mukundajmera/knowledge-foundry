"""Knowledge Foundry — Agent Orchestration State.

Shared state schema for the LangGraph-based multi-agent orchestrator.
Per phase-2.1 spec §3.1.
"""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class SubTask(BaseModel):
    """A sub-task planned by the Supervisor."""

    id: str
    description: str
    assigned_agent: str
    status: str = "pending"  # pending | in_progress | completed | failed
    result: dict[str, Any] | None = None
    depends_on: list[str] = Field(default_factory=list)


class OrchestratorState(TypedDict, total=False):
    """Shared state across all agents in the LangGraph.

    Following LangGraph conventions, fields are typed but many are optional
    so the graph can be initialized with minimal data.
    """

    # === Input ===
    user_query: str
    tenant_id: str
    workspace_id: str
    user_id: str
    deployment_context: str  # "general", "hr_screening", etc.
    trace_id: str

    # === Supervisor Planning ===
    task_plan: list[dict[str, Any]]  # List of SubTask dicts
    current_iteration: int
    max_iterations: int
    orchestration_pattern: str  # "supervisor", "hierarchical", "utility_aware"

    # === Agent Results ===
    agent_outputs: dict[str, Any]  # Keyed by agent name
    messages: list[dict[str, str]]  # Message history

    # === Retrieval Context ===
    retrieved_documents: list[dict[str, Any]]
    graph_context: list[dict[str, Any]]
    assembled_context: str

    # === Safety ===
    safety_verdict: dict[str, Any] | None

    # === Quality ===
    review_verdict: dict[str, Any] | None

    # === Output ===
    final_answer: str | None
    confidence: float
    citations: list[dict[str, Any]]
    hitl_required: bool
    hitl_reason: str | None

    # === Metadata ===
    latency_budget_ms: int
    cost_accumulated_usd: float
    error: str | None
    next_agent: str | None

    # === Private Injection ===
    _llm_provider: Any
    _rag_pipeline: Any
