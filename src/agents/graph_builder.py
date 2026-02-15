"""Knowledge Foundry — LangGraph Orchestrator Builder.

Constructs the multi-agent StateGraph with conditional routing.
Per phase-2.1 spec §3.
"""

from __future__ import annotations

from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from src.agents.coder import coder_node
from src.agents.compliance import compliance_agent_node
from src.agents.growth import growth_agent_node
from src.agents.researcher import researcher_node
from src.agents.reviewer import reviewer_node
from src.agents.risk import risk_agent_node
from src.agents.safety import hitl_gate_node, safety_check_node
from src.agents.state import OrchestratorState
from src.agents.supervisor import supervisor_plan_node, synthesize_node, execute_plugin_node

logger = structlog.get_logger(__name__)


# =============================================================
# Conditional Edge Router
# =============================================================


def route_next_agent(state: OrchestratorState) -> str:
    """Route to the next agent based on state['next_agent'].

    Returns the node name for the LangGraph conditional edge.
    """
    next_agent = state.get("next_agent")
    max_iterations = state.get("max_iterations", 5)
    current_iteration = state.get("current_iteration", 0)

    # Circuit breaker — prevent infinite loops
    if current_iteration >= max_iterations:
        return "synthesize"

    # Route based on next_agent marker
    routing = {
        "supervisor_plan": "supervisor_plan",
        "researcher": "researcher",
        "coder": "coder",
        "reviewer": "reviewer",
        "risk": "risk",
        "growth": "growth",
        "compliance": "compliance",
        "synthesize": "synthesize",
        "safety_check": "safety_check",
        "hitl_gate": "hitl_gate",
        "execute_plugin": "execute_plugin",
    }

    return routing.get(next_agent, END)


# =============================================================
# Graph Builder
# =============================================================


def build_orchestrator_graph() -> StateGraph:
    """Build the LangGraph StateGraph for multi-agent orchestration.

    Graph structure:
        supervisor_plan → [researcher | coder | risk | growth | compliance | execute_plugin] → supervisor_plan
                       → synthesize → safety_check → hitl_gate → END
    """
    graph = StateGraph(OrchestratorState)

    # Add nodes
    graph.add_node("supervisor_plan", supervisor_plan_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("coder", coder_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("risk", risk_agent_node)
    graph.add_node("growth", growth_agent_node)
    graph.add_node("compliance", compliance_agent_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("safety_check", safety_check_node)
    graph.add_node("hitl_gate", hitl_gate_node)
    graph.add_node("execute_plugin", execute_plugin_node)

    # Set entry point
    graph.set_entry_point("supervisor_plan")

    # Conditional edges from supervisor — routes to specialist agents or synthesize
    graph.add_conditional_edges("supervisor_plan", route_next_agent)

    # All specialist agents route back via conditional edge
    for agent_name in ["researcher", "coder", "reviewer", "risk", "growth", "compliance", "execute_plugin"]:
        graph.add_conditional_edges(agent_name, route_next_agent)

    # Synthesize → safety_check
    graph.add_conditional_edges("synthesize", route_next_agent)

    # Safety → HITL gate
    graph.add_conditional_edges("safety_check", route_next_agent)

    # HITL gate → END
    graph.add_edge("hitl_gate", END)

    return graph


def compile_orchestrator(
    llm_provider: Any | None = None,
    rag_pipeline: Any | None = None,
):
    """Compile the orchestrator graph into a runnable.

    Injects service dependencies into the state.
    """
    graph = build_orchestrator_graph()
    compiled = graph.compile()

    # Store dependency references for injection via state
    compiled._kf_llm_provider = llm_provider
    compiled._kf_rag_pipeline = rag_pipeline

    return compiled


async def run_orchestrator(
    compiled_graph: Any,
    user_query: str,
    tenant_id: str = "default",
    user_id: str = "",
    deployment_context: str = "general",
    max_iterations: int = 5,
) -> dict[str, Any]:
    """Execute the orchestrator graph end-to-end.

    Returns the final state including the answer and metadata.
    """
    import uuid

    initial_state: OrchestratorState = {
        "user_query": user_query,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "deployment_context": deployment_context,
        "trace_id": str(uuid.uuid4()),
        "task_plan": [],
        "current_iteration": 0,
        "max_iterations": max_iterations,
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
        # Inject service references
        "_llm_provider": getattr(compiled_graph, "_kf_llm_provider", None),
        "_rag_pipeline": getattr(compiled_graph, "_kf_rag_pipeline", None),
    }

    final_state = await compiled_graph.ainvoke(initial_state)

    return {
        "answer": final_state.get("final_answer", ""),
        "confidence": final_state.get("confidence", 0.0),
        "citations": final_state.get("citations", []),
        "safety_verdict": final_state.get("safety_verdict"),
        "hitl_required": final_state.get("hitl_required", False),
        "hitl_reason": final_state.get("hitl_reason"),
        "agent_outputs": final_state.get("agent_outputs", {}),
        "orchestration_pattern": final_state.get("orchestration_pattern", "supervisor"),
        "iterations": final_state.get("current_iteration", 0),
        "cost_usd": final_state.get("cost_accumulated_usd", 0.0),
        "trace_id": final_state.get("trace_id", ""),
    }
