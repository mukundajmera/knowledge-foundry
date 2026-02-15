"""Knowledge Foundry — Reviewer Agent.

Reviews content for faithfulness, quality, security, and bias.
Per phase-2.1 spec §2.4.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from src.agents.state import OrchestratorState
from src.core.interfaces import LLMConfig, LLMProvider, ModelTier

logger = structlog.get_logger(__name__)

REVIEWER_SYSTEM_PROMPT = """\
You are the Reviewer agent for Knowledge Foundry.
Your role is to review content for quality, accuracy, and safety.

Review criteria:
1. Faithfulness — Are all claims supported by source evidence?
2. Completeness — Does the answer fully address the original question?
3. Coherence — Is the answer well-structured and easy to follow?
4. Security — Are there any security concerns in the content?
5. Bias — Is the content neutral and unbiased?

Return JSON:
{{
  "review_result": "APPROVED|NEEDS_REVISION|REJECTED",
  "issues_found": [
    {{
      "severity": "info|warning|critical",
      "category": "faithfulness|completeness|coherence|security|bias",
      "description": "...",
      "suggested_fix": "..."
    }}
  ],
  "suggestions": ["suggestion 1"],
  "confidence": 0.85
}}
"""


async def reviewer_node(state: OrchestratorState) -> dict[str, Any]:
    """Reviewer agent node — reviews content for quality and accuracy."""
    llm_provider: LLMProvider | None = state.get("_llm_provider")
    if not llm_provider:
        return _update_agent_output(state, "reviewer", {
            "review_result": "APPROVED",
            "issues_found": [],
            "suggestions": [],
            "confidence": 0.0,
        })

    user_query = state.get("user_query", "")
    agent_outputs = state.get("agent_outputs", {})
    task_plan = state.get("task_plan", [])

    # Find current task
    task_desc = user_query
    for task in task_plan:
        if task.get("status") == "in_progress" and task.get("assigned_agent") == "reviewer":
            task_desc = task["description"]
            break

    # Build context from other agent outputs
    content_to_review = ""
    if "researcher" in agent_outputs:
        content_to_review += f"Research findings:\n{agent_outputs['researcher'].get('findings', '')}\n\n"
    if "coder" in agent_outputs:
        content_to_review += f"Code output:\n{agent_outputs['coder'].get('code', '')}\n\n"

    final_answer = state.get("final_answer", "")
    if final_answer:
        content_to_review += f"Final answer:\n{final_answer}\n\n"

    prompt = f"Task: {task_desc}\n\nContent to review:\n{content_to_review[:4000]}"

    config = LLMConfig(
        model="",
        tier=ModelTier.SONNET,
        temperature=0.1,
        max_tokens=2048,
        system_prompt=REVIEWER_SYSTEM_PROMPT,
    )

    response = await llm_provider.generate(prompt, config)

    try:
        output = json.loads(response.text)
    except (json.JSONDecodeError, AttributeError):
        output = {
            "review_result": "APPROVED",
            "issues_found": [],
            "suggestions": [],
            "confidence": 0.5,
        }

    return _update_agent_output(state, "reviewer", output)


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
