"""Knowledge Foundry — Researcher Agent.

Finds information from vector DB and knowledge graph using hybrid retrieval.
Per phase-2.1 spec §2.2.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from src.agents.state import OrchestratorState
from src.core.interfaces import (
    LLMConfig,
    LLMProvider,
    ModelTier,
    RAGResponse,
    RetrievalStrategy,
)

logger = structlog.get_logger(__name__)

RESEARCHER_SYSTEM_PROMPT = """\
You are the Researcher agent for Knowledge Foundry.
Your role is to find and synthesize information from the enterprise knowledge base.

Given the research results below, provide:
1. A clear summary of findings
2. Key facts with source references
3. Any knowledge gaps (what was NOT found)
4. Confidence level in your findings

Format your output as JSON:
{{
  "findings": "...",
  "key_facts": ["fact 1", "fact 2"],
  "knowledge_gaps": ["gap 1"],
  "confidence": 0.85
}}
"""


async def researcher_node(state: OrchestratorState) -> dict[str, Any]:
    """Researcher agent node — searches knowledge base and synthesizes findings.

    Uses the RAG pipeline to search vector and graph stores, then
    summarizes findings for the supervisor.
    """
    rag_pipeline = state.get("_rag_pipeline")
    llm_provider: LLMProvider | None = state.get("_llm_provider")

    if not rag_pipeline:
        return _update_state(state, {
            "findings": "RAG pipeline not available.",
            "confidence": 0.0,
        })

    user_query = state.get("user_query", "")
    tenant_id = state.get("tenant_id", "default")
    task_plan = state.get("task_plan", [])

    # Find current sub-task description
    current_task = None
    for task in task_plan:
        if task.get("status") == "in_progress" and task.get("assigned_agent") == "researcher":
            current_task = task
            break

    research_question = current_task["description"] if current_task else user_query

    # Determine retrieval strategy — use hybrid if graph store is available
    strategy = RetrievalStrategy.VECTOR_ONLY
    if hasattr(rag_pipeline, "_graph_store") and rag_pipeline._graph_store:
        strategy = RetrievalStrategy.HYBRID

    # Perform RAG search
    try:
        rag_response: RAGResponse = await rag_pipeline.query(
            query=research_question,
            tenant_id=tenant_id,
            top_k=15,
            strategy=strategy,
            max_hops=2,
        )
    except Exception as exc:
        logger.warning("researcher.rag_error", error=str(exc))
        return _update_state(state, {
            "findings": f"Search failed: {str(exc)}",
            "confidence": 0.0,
        })

    # Build research output
    research_output = {
        "findings": rag_response.text,
        "sources": [
            {
                "document_id": c.document_id,
                "title": c.title,
                "relevance_score": c.relevance_score,
            }
            for c in rag_response.citations
        ],
        "search_results_count": len(rag_response.search_results),
        "strategy_used": strategy.value,
        "confidence": 0.8 if rag_response.search_results else 0.3,
        "latency_ms": rag_response.total_latency_ms,
    }

    return _update_state(state, research_output)


def _update_state(state: OrchestratorState, output: dict[str, Any]) -> dict[str, Any]:
    """Mark current task as completed and store output."""
    agent_outputs = dict(state.get("agent_outputs", {}))
    agent_outputs["researcher"] = output

    task_plan = list(state.get("task_plan", []))
    for task in task_plan:
        if task.get("status") == "in_progress" and task.get("assigned_agent") == "researcher":
            task["status"] = "completed"
            task["result"] = output
            break

    citations = list(state.get("citations", []))
    for source in output.get("sources", []):
        citations.append(source)

    return {
        "agent_outputs": agent_outputs,
        "task_plan": task_plan,
        "citations": citations,
        "next_agent": "supervisor_plan",
    }
