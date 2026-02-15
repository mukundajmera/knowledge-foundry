"""Knowledge Foundry — Coder Agent.

Generates, reviews, and debugs code. Sandboxed execution only.
Per phase-2.1 spec §2.3.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from src.agents.state import OrchestratorState
from src.core.interfaces import LLMConfig, LLMProvider, ModelTier

logger = structlog.get_logger(__name__)

CODER_SYSTEM_PROMPT = """\
You are the Coder agent for Knowledge Foundry.
You generate, review, and debug code with a focus on security and correctness.

Rules:
1. Never use eval() or exec()
2. Always use parameterized queries for databases
3. Include type hints and docstrings
4. Write testable, modular code
5. Flag any security concerns

Return JSON:
{{
  "code": "...",
  "language": "python",
  "explanation": "...",
  "test_cases": [
    {{"name": "test_...", "description": "..."}}
  ],
  "security_notes": ["note 1"],
  "confidence": 0.85
}}
"""


async def coder_node(state: OrchestratorState) -> dict[str, Any]:
    """Coder agent node — generates or reviews code."""
    llm_provider: LLMProvider | None = state.get("_llm_provider")
    if not llm_provider:
        return _update_agent_output(state, "coder", {
            "code": "",
            "explanation": "LLM provider not available",
            "confidence": 0.0,
        })

    user_query = state.get("user_query", "")
    task_plan = state.get("task_plan", [])
    agent_outputs = state.get("agent_outputs", {})

    # Find current task
    task_desc = user_query
    for task in task_plan:
        if task.get("status") == "in_progress" and task.get("assigned_agent") == "coder":
            task_desc = task["description"]
            break

    # Include researcher findings if available
    researcher_context = ""
    if "researcher" in agent_outputs:
        findings = agent_outputs["researcher"].get("findings", "")
        researcher_context = f"\n\nResearch context:\n{findings[:3000]}"

    prompt = f"Task: {task_desc}{researcher_context}"

    config = LLMConfig(
        model="",
        tier=ModelTier.SONNET,
        temperature=0.1,
        max_tokens=4096,
        system_prompt=CODER_SYSTEM_PROMPT,
    )

    response = await llm_provider.generate(prompt, config)

    try:
        output = json.loads(response.text)
    except (json.JSONDecodeError, AttributeError):
        output = {
            "code": response.text,
            "language": "python",
            "explanation": "Generated code output",
            "confidence": 0.7,
        }

    return _update_agent_output(state, "coder", output)


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
