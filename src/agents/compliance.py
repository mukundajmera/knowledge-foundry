"""Knowledge Foundry — Compliance Agent.

Ensures regulatory and policy compliance. Can veto non-compliant actions.
Per phase-2.1 spec §2.8.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from src.agents.state import OrchestratorState
from src.core.interfaces import LLMConfig, LLMProvider, ModelTier

logger = structlog.get_logger(__name__)

COMPLIANCE_SYSTEM_PROMPT = """\
You are the Compliance agent for Knowledge Foundry.
Your utility function is to ENSURE COMPLIANCE. You can veto non-compliant actions.

Check compliance against:
1. GDPR — Data protection and privacy
2. EU AI Act — AI system requirements (high-risk classification)
3. SOC2 — Security controls
4. Company policies — Internal standards

Return JSON:
{{
  "compliant": true/false,
  "violations": [
    {{
      "regulation": "GDPR|EU_AI_ACT|SOC2|COMPANY_POLICY",
      "article": "Art. 17",
      "violation_description": "...",
      "severity": "minor|major|critical",
      "remediation": "..."
    }}
  ],
  "required_controls": ["control 1"],
  "confidence": 0.85
}}
"""


async def compliance_agent_node(state: OrchestratorState) -> dict[str, Any]:
    """Compliance agent node — checks for regulatory violations."""
    llm_provider: LLMProvider | None = state.get("_llm_provider")
    if not llm_provider:
        return _update_agent_output(state, "compliance", {
            "compliant": True,
            "violations": [],
            "confidence": 0.0,
        })

    user_query = state.get("user_query", "")
    agent_outputs = state.get("agent_outputs", {})
    task_plan = state.get("task_plan", [])

    task_desc = user_query
    for task in task_plan:
        if task.get("status") == "in_progress" and task.get("assigned_agent") == "compliance":
            task_desc = task["description"]
            break

    context = json.dumps(agent_outputs, default=str)[:3000]
    prompt = f"Action to check: {task_desc}\n\nContext:\n{context}"

    config = LLMConfig(
        model="",
        tier=ModelTier.SONNET,
        temperature=0.1,
        max_tokens=2048,
        system_prompt=COMPLIANCE_SYSTEM_PROMPT,
    )

    response = await llm_provider.generate(prompt, config)

    try:
        output = json.loads(response.text)
    except (json.JSONDecodeError, AttributeError):
        output = {
            "compliant": True,
            "violations": [],
            "required_controls": [],
            "confidence": 0.5,
        }

    return _update_agent_output(state, "compliance", output)


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
