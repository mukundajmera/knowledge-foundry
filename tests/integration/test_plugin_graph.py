"""Integration test for Plugin System within the Agent Graph."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Any

from src.agents.graph_builder import compile_orchestrator
from src.agents.state import OrchestratorState
from src.core.interfaces import LLMProvider, LLMResponse, ModelTier, LLMConfig

class MockLLM(LLMProvider):
    """Mock LLM that returns specific plans based on prompts."""
    
    def __init__(self):
        self.call_count = 0

    async def generate(self, prompt: str, config: LLMConfig) -> LLMResponse:
        self.call_count += 1
        
        # 1. First call: Supervisor planning -> Route to plugin
        if "Create a plan" in prompt:
            return LLMResponse(
                text='''
                {
                    "reasoning": "User asked for math. Using calculator.",
                    "sub_tasks": [
                        {
                            "id": "t1",
                            "description": "Calculate 50 * 2",
                            "assigned_agent": "plugin:calculator",
                            "plugin_action": "evaluate",
                            "plugin_params": {"expression": "50 * 2"},
                            "depends_on": []
                        }
                    ],
                    "orchestration_pattern": "supervisor"
                }
                ''',
                model="mock",
                tier=ModelTier.SONNET
            )
            
        # 2. Second call: Supervisor planning (after plugin) -> Synthesis
        if "Previous agent outputs" in prompt and '"result": 100' in prompt:
             return LLMResponse(
                text='''
                {
                    "reasoning": "Math complete. Synthesizing.",
                    "sub_tasks": [],
                    "orchestration_pattern": "supervisor"
                }
                ''',
                model="mock",
                tier=ModelTier.SONNET
            )
            
        # 3. Third call: Synthesis
        if "Synthesize a comprehensive" in prompt:
            return LLMResponse(
                text="The result of 50 * 2 is 100.",
                model="mock",
                tier=ModelTier.SONNET
            )
            
        return LLMResponse(text="", model="mock", tier=ModelTier.SONNET)

    async def health_check(self) -> bool:
        return True

    def get_cost_per_token(self, model: str) -> tuple[float, float]:
        return (0, 0)

@pytest.mark.asyncio
async def test_plugin_graph_execution():
    # Setup
    llm = MockLLM()
    # Reset registry to avoid pollution
    from src.plugins.registry import PluginRegistry
    PluginRegistry._instance = None
    PluginRegistry._plugins = {}
    
    graph = compile_orchestrator(llm_provider=llm)
    
    initial_state = {
        "user_query": "What is 50 * 2?",
        "tenant_id": "test",
        "current_iteration": 0,
        "max_iterations": 3,
        "agent_outputs": {},
        "task_plan": [],
        "_llm_provider": llm
    }
    
    # Execute
    final_state = await graph.ainvoke(initial_state)
    
    # Assertions
    agent_outputs = final_state.get("agent_outputs", {})
    
    # 1. Verify plugin was executed and result captured
    assert "t1" in agent_outputs
    assert agent_outputs["t1"]["success"] is True
    assert agent_outputs["t1"]["data"]["result"] == 100
    
    # 2. Verify final answer
    assert final_state["final_answer"] == "The result of 50 * 2 is 100."
    # 3. Verify iteration count (Plan -> Execute -> Plan -> Synthesize -> Safety -> HITL -> End)
    # The exact count depends on how many nodes are visited. 
    # Just checking we didn't infinite loop and got a result.
    assert final_state["confidence"] == 0.8

@pytest.mark.asyncio
async def test_communication_graph_execution():
    from unittest.mock import MagicMock
    
    class MockCommLLM(LLMProvider):
        async def generate(self, prompt: str, config: LLMConfig) -> LLMResponse:
            if "Synthesize a comprehensive" in prompt:
                return LLMResponse(text="Email sent successfully.", model="mock", tier=ModelTier.SONNET)
            
            if "Create a plan" in prompt:
                if "Previous agent outputs" in prompt and "mock-msg" in prompt:
                    return LLMResponse(
                        text='''{"sub_tasks": [], "orchestration_pattern": "supervisor"}''',
                        model="mock", tier=ModelTier.SONNET
                    )
                return LLMResponse(
                    text='''
                    {
                        "sub_tasks": [
                            {
                                "id": "t1",
                                "description": "Send email",
                                "assigned_agent": "plugin:communication",
                                "plugin_action": "send_message",
                                "plugin_params": {"channel": "email", "recipient": "user@test.com", "content": "Hi"}
                            }
                        ]
                    }
                    ''',
                    model="mock", tier=ModelTier.SONNET
                )
            
            return LLMResponse(text="", model="mock", tier=ModelTier.SONNET)
        
        async def health_check(self) -> bool: return True
        def get_cost_per_token(self, model: str) -> tuple[float, float]: return (0, 0)

    # Setup
    llm = MockCommLLM()
    # Reset plugin registry
    from src.plugins.registry import PluginRegistry
    PluginRegistry._instance = None
    PluginRegistry._plugins = {}
    
    graph = compile_orchestrator(llm_provider=llm)
    
    initial_state = {
        "user_query": "Email user",
        "tenant_id": "test",
        "current_iteration": 0,
        "max_iterations": 3,
        "agent_outputs": {},
        "task_plan": [],
        "_llm_provider": llm
    }
    
    final_state = await graph.ainvoke(initial_state)
    
    agent_outputs = final_state.get("agent_outputs", {})
    assert "t1" in agent_outputs
    assert agent_outputs["t1"]["data"]["status"] == "sent"
    assert final_state["final_answer"] == "Email sent successfully."

@pytest.mark.asyncio
async def test_sandbox_graph_execution():
    
    # Setup Mock LLM for Code Task
    class MockCodeLLM(LLMProvider):
        async def generate(self, prompt: str, config: LLMConfig) -> LLMResponse:
            # Check for synthesis first
            if "Synthesize a comprehensive" in prompt:
                return LLMResponse(text="Output was Hello Sandbox", model="mock", tier=ModelTier.SONNET)
                
            if "Create a plan" in prompt:
                 # If we have outputs, it's the second iteration
                if "Previous agent outputs" in prompt and "Hello Sandbox" in prompt:
                    return LLMResponse(
                        text='''
                        {
                            "reasoning": "Code ran. Synthesizing.",
                            "sub_tasks": [],
                            "orchestration_pattern": "supervisor"
                        }
                        ''',
                        model="mock",
                        tier=ModelTier.SONNET
                    )
                # First iteration
                return LLMResponse(
                    text='''
                    {
                        "sub_tasks": [
                            {
                                "id": "t1",
                                "description": "Run python code",
                                "assigned_agent": "plugin:code_sandbox",
                                "plugin_action": "execute_python",
                                "plugin_params": {"code": "print('Hello Sandbox')"}
                            }
                        ]
                    }
                    ''',
                    model="mock",
                    tier=ModelTier.SONNET
                )
            
            return LLMResponse(text="", model="mock", tier=ModelTier.SONNET)
            
        async def health_check(self) -> bool: return True
        def get_cost_per_token(self, model: str) -> tuple[float, float]: return (0, 0)

    # Mock Docker to avoid needing daemon
    with patch("src.plugins.sandbox.docker") as mock_docker, \
         patch("src.plugins.sandbox._DOCKER_AVAILABLE", True):
        
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.containers.run.return_value = b"Hello Sandbox"
        
        # Ensure plugin is reloaded/registered with mock
        from src.plugins.registry import PluginRegistry
        PluginRegistry._instance = None
        PluginRegistry._plugins = {}
        
        llm = MockCodeLLM()
        graph = compile_orchestrator(llm_provider=llm)
        
        initial_state = {
            "user_query": "Run this code",
            "tenant_id": "test",
            "current_iteration": 0,
            "max_iterations": 3,
            "agent_outputs": {},
            "task_plan": [],
            "_llm_provider": llm
        }
        
        final_state = await graph.ainvoke(initial_state)
        
        agent_outputs = final_state.get("agent_outputs", {})
        assert "t1" in agent_outputs
        # Sandbox returns stdout in data
        assert agent_outputs["t1"]["data"]["stdout"] == "Hello Sandbox"
        assert final_state["final_answer"] == "Output was Hello Sandbox"
