"""Knowledge Foundry — Risk Agent.

Assesses risks and downsides of proposed actions. Uses Opus for complex reasoning.
Per phase-2.1 spec §2.6.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from src.agents.state import OrchestratorState
from src.core.interfaces import LLMConfig, LLMProvider, ModelTier

logger = structlog.get_logger(__name__)

RISK_SYSTEM_PROMPT = """\
You are the Risk Assessment agent for Knowledge Foundry.
Your utility function is to MINIMIZE RISK. Be conservative.

Analyze the proposed action for:
1. Financial risks
2. Legal/regulatory risks
3. Reputational risks
4. Operational risks
5. Technical risks

Return JSON:
{{
  "overall_risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "identified_risks": [
    {{
      "description": "...",
      "category": "financial|legal|reputational|operational|technical",
      "probability": "rare|unlikely|possible|likely|almost_certain",
      "impact": "negligible|minor|moderate|major|catastrophic",
      "risk_score": 1-25
    }}
  ],
  "recommended_mitigations": ["mitigation 1"],
  "confidence": 0.85
}}
"""


async def risk_agent_node(state: OrchestratorState) -> dict[str, Any]:
    """Risk agent node — assesses risks of proposed actions."""
    llm_provider: LLMProvider | None = state.get("_llm_provider")
    if not llm_provider:
        return _update_agent_output(state, "risk", {
            "overall_risk_level": "MEDIUM",
            "identified_risks": [],
            "confidence": 0.0,
        })

    user_query = state.get("user_query", "")
    agent_outputs = state.get("agent_outputs", {})
    task_plan = state.get("task_plan", [])

    task_desc = user_query
    for task in task_plan:
        if task.get("status") == "in_progress" and task.get("assigned_agent") == "risk":
            task_desc = task["description"]
            break

    context = json.dumps(agent_outputs, default=str)[:3000]
    prompt = f"Proposed action: {task_desc}\n\nContext:\n{context}"

    config = LLMConfig(
        model="",
        tier=ModelTier.OPUS,
        temperature=0.3,
        max_tokens=2048,
        system_prompt=RISK_SYSTEM_PROMPT,
    )

    response = await llm_provider.generate(prompt, config)

    try:
        output = json.loads(response.text)
    except (json.JSONDecodeError, AttributeError):
        output = {
            "overall_risk_level": "MEDIUM",
            "identified_risks": [],
            "recommended_mitigations": [],
            "confidence": 0.5,
        }

    return _update_agent_output(state, "risk", output)


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
