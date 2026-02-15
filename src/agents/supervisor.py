"""Knowledge Foundry — Supervisor Agent.

Central orchestrator that decomposes tasks, delegates to specialist agents,
and synthesizes final answers.  Per phase-2.1 spec §2.1.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import structlog

from src.agents.state import OrchestratorState, SubTask
from src.core.interfaces import LLMConfig, LLMProvider, ModelTier
from src.plugins.registry import PluginRegistry, PluginLoader

logger = structlog.get_logger(__name__)

SUPERVISOR_SYSTEM_PROMPT = """\
You are the Supervisor agent for Knowledge Foundry. Your role is to orchestrate
specialist agents and tools to answer user queries with maximum accuracy and minimum cost.

## Your Workflow:
1. ANALYZE the user query — classify complexity, identify sub-tasks
2. PLAN which agents/tools to invoke and in what order
3. Return your plan as valid JSON

## Available Agents:
- researcher: Finds information from vector DB and knowledge graph
- coder: Generates, reviews, and debugs code
- risk: Assesses risks and downsides
- growth: Identifies opportunities and value
- compliance: Ensures regulatory compliance

## Available Tools (Plugins):
{plugin_list}

## Rules:
- For simple factual questions, assign only "researcher"
- For code generation/review, assign "coder"
- For executing/testing code (e.g. math, data analysis), assign "plugin:code_sandbox"
- For querying internal database (users, docs), assign "plugin:database"
- For sending notifications (email/slack), assign "plugin:communication"
- For specific tool needs (math, search), assign the matching plugin
- Maximum {max_iterations} sub-tasks
- Every task needs a clear description

Return JSON:
{{
  "reasoning": "...",
  "sub_tasks": [
    {{
      "id": "t1", 
      "description": "...", 
      "assigned_agent": "researcher" OR "plugin:<name>", 
      "plugin_action": "<action if plugin>",
      "plugin_params": {{...}},
      "depends_on": []
    }},
    ...
  ],
  "orchestration_pattern": "supervisor"
}}
"""


async def supervisor_plan_node(state: OrchestratorState) -> dict[str, Any]:
    """Supervisor planning node — decompose query into sub-tasks.

    This is a LangGraph node function: takes state, returns state updates.
    """
    llm_provider: LLMProvider | None = state.get("_llm_provider")
    if not llm_provider:
        return {"error": "LLM provider not available", "next_agent": None}

    # Ensure plugins are loaded
    PluginLoader.load_plugins()
    registry = PluginRegistry()
    plugins = registry.list_plugins()
    plugin_desc = "\n".join(
        [f"- {p.name}: {p.description} (Actions: {', '.join(p.actions)})" for p in plugins]
    )

    user_query = state.get("user_query", "")
    current_iteration = state.get("current_iteration", 0)
    max_iterations = state.get("max_iterations", 5)
    agent_outputs = state.get("agent_outputs", {})
    task_plan = state.get("task_plan", [])

    # If we have completed all tasks, go to synthesis
    pending = [t for t in task_plan if t.get("status") == "pending"]
    if task_plan and not pending:
        return {"next_agent": "synthesize", "current_iteration": current_iteration}

    # If we already have a plan with pending tasks, route to next
    if pending:
        next_task = pending[0]
        next_task["status"] = "in_progress"
        
        assigned = next_task["assigned_agent"]
        if assigned.startswith("plugin:"):
            return {
                "task_plan": task_plan,
                "next_agent": "execute_plugin",
                "current_iteration": current_iteration + 1,
            }
            
        return {
            "task_plan": task_plan,
            "next_agent": assigned,
            "current_iteration": current_iteration + 1,
        }

    # First iteration — create the plan
    if current_iteration >= max_iterations:
        return {"next_agent": "synthesize", "current_iteration": current_iteration}

    prompt = (
        f"User query: {user_query}\n\n"
        f"Previous agent outputs: {json.dumps(agent_outputs, default=str)[:2000]}\n\n"
        f"Create a plan to answer this query."
    )

    config = LLMConfig(
        model="",
        tier=ModelTier.SONNET,
        temperature=0.2,
        max_tokens=2048,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT.format(
            max_iterations=max_iterations, plugin_list=plugin_desc
        ),
    )

    response = await llm_provider.generate(prompt, config)

    # Parse the plan
    try:
        plan_data = _extract_json(response.text)
        sub_tasks = plan_data.get("sub_tasks", [])
        # Ensure IDs
        for i, task in enumerate(sub_tasks):
            if not task.get("id"):
                task["id"] = f"t{i + 1}"
            task["status"] = "pending"
            task["result"] = None
    except Exception:
        # Fallback plan
        sub_tasks = [
            {
                "id": "t1",
                "description": user_query,
                "assigned_agent": "researcher",
                "status": "pending",
                "result": None,
                "depends_on": [],
            }
        ]

    # Route to first pending task
    first = sub_tasks[0] if sub_tasks else None
    next_agent = "synthesize"
    
    if first:
        first["status"] = "in_progress"
        assigned = first["assigned_agent"]
        next_agent = "execute_plugin" if assigned.startswith("plugin:") else assigned

    return {
        "task_plan": sub_tasks,
        "orchestration_pattern": plan_data.get("orchestration_pattern", "supervisor")
        if "plan_data" in dir()
        else "supervisor",
        "next_agent": next_agent,
        "current_iteration": current_iteration + 1,
        "cost_accumulated_usd": state.get("cost_accumulated_usd", 0.0)
        + response.cost_usd,
    }


async def execute_plugin_node(state: OrchestratorState) -> dict[str, Any]:
    """Execute a plugin action defined in the current task."""
    task_plan = state.get("task_plan", [])
    
    # Find current in-progress task
    current_task = next((t for t in task_plan if t.get("status") == "in_progress"), None)
    
    if not current_task:
        return {"next_agent": "supervisor_plan"}
        
    assigned = current_task.get("assigned_agent", "")
    if not assigned.startswith("plugin:"):
         return {"next_agent": "supervisor_plan"}
         
    plugin_name = assigned.split(":", 1)[1]
    action = current_task.get("plugin_action", "")
    params = current_task.get("plugin_params", {})
    
    registry = PluginRegistry()
    logger.info("Executing plugin", plugin=plugin_name, action=action)
    
    result = await registry.execute(plugin_name, action, params)
    
    output = {
        "success": result.success,
        "data": result.data,
        "error": result.error
    }
    
    # Update task status
    current_task["status"] = "completed"
    current_task["result"] = output
    
    # Update agent outputs for context
    agent_outputs = state.get("agent_outputs", {})
    agent_outputs[current_task["id"]] = output
    
    return {
        "task_plan": task_plan,
        "agent_outputs": agent_outputs,
        "next_agent": "supervisor_plan" # Return to supervisor to route next task
    }


async def synthesize_node(state: OrchestratorState) -> dict[str, Any]:
    """Synthesis node — compile all agent outputs into a final answer."""
    llm_provider: LLMProvider | None = state.get("_llm_provider")
    if not llm_provider:
        return {"final_answer": "Error: LLM provider not available", "confidence": 0.0}

    user_query = state.get("user_query", "")
    agent_outputs = state.get("agent_outputs", {})
    
    synth_prompt = (
        f"User question: {user_query}\n\n"
        f"Agent/Tool results:\n"
        f"{json.dumps(agent_outputs, default=str)[:8000]}\n\n"
        f"Synthesize a comprehensive, well-cited answer. "
        f"Use all available evidence. Cite sources with [Source N]."
    )

    config = LLMConfig(
        model="",
        tier=ModelTier.SONNET,
        temperature=0.2,
        max_tokens=4096,
        system_prompt="You synthesize research from multiple agents into a coherent answer.",
    )

    response = await llm_provider.generate(synth_prompt, config)

    return {
        "final_answer": response.text,
        "confidence": 0.8,
        "next_agent": "safety_check",
    }


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response."""
    import re

    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])
    return {}
