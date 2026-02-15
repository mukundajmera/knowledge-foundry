"""Knowledge Foundry — Growth Agent.

Identifies opportunities and maximizes value. More creative temperature.
Per phase-2.1 spec §2.7.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from src.agents.state import OrchestratorState
from src.core.interfaces import LLMConfig, LLMProvider, ModelTier

logger = structlog.get_logger(__name__)

GROWTH_SYSTEM_PROMPT = """\
You are the Growth Strategy agent for Knowledge Foundry.
Your utility function is to MAXIMIZE VALUE. Be visionary but grounded.

Analyze opportunities for:
1. Revenue growth
2. Market expansion
3. Operational efficiency
4. Customer satisfaction
5. Competitive advantage

Return JSON:
{{
  "overall_value_potential": "LOW|MEDIUM|HIGH|VERY_HIGH",
  "identified_opportunities": [
    {{
      "description": "...",
      "dimension": "revenue|market_share|efficiency|customer_satisfaction|competitive_advantage",
      "expected_value": "...",
      "time_horizon": "immediate|short_term|medium_term|long_term"
    }}
  ],
  "recommended_enhancements": ["enhancement 1"],
  "confidence": 0.80
}}
"""


async def growth_agent_node(state: OrchestratorState) -> dict[str, Any]:
    """Growth agent node — identifies opportunities and value."""
    llm_provider: LLMProvider | None = state.get("_llm_provider")
    if not llm_provider:
        return _update_agent_output(state, "growth", {
            "overall_value_potential": "MEDIUM",
            "identified_opportunities": [],
            "confidence": 0.0,
        })

    user_query = state.get("user_query", "")
    agent_outputs = state.get("agent_outputs", {})
    task_plan = state.get("task_plan", [])

    task_desc = user_query
    for task in task_plan:
        if task.get("status") == "in_progress" and task.get("assigned_agent") == "growth":
            task_desc = task["description"]
            break

    context = json.dumps(agent_outputs, default=str)[:3000]
    prompt = f"Proposed action: {task_desc}\n\nContext:\n{context}"

    config = LLMConfig(
        model="",
        tier=ModelTier.SONNET,
        temperature=0.4,
        max_tokens=2048,
        system_prompt=GROWTH_SYSTEM_PROMPT,
    )

    response = await llm_provider.generate(prompt, config)

    try:
        output = json.loads(response.text)
    except (json.JSONDecodeError, AttributeError):
        output = {
            "overall_value_potential": "MEDIUM",
            "identified_opportunities": [],
            "recommended_enhancements": [],
            "confidence": 0.5,
        }

    return _update_agent_output(state, "growth", output)


def _update_agent_output(
    state: OrchestratorState, agent_name: str, output: dict[str, Any]
) -> dict[str, Any]:
    """Helper to update agent output and mark task complete."""
    agent_outputs = dict(state.get("agent_outputs", {}))
    agent_outputs[agent_name] = output

    task_plan = list(state.get("task_plan", []))
    for task in task_plan:
        if task.get("status") == "in_progress" and task.get("assigned_agent") == agent_name:
            task["status"] = "completed"
            task["result"] = output
            break

    return {
        "agent_outputs": agent_outputs,
        "task_plan": task_plan,
        "next_agent": "supervisor_plan",
    }
