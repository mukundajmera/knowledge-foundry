"""Unit tests for Code Sandbox Plugin."""

from unittest.mock import MagicMock, patch

import pytest

from src.plugins.sandbox import CodeSandboxPlugin


# Mock _DOCKER_AVAILABLE to verify behavior when missing
@pytest.fixture
def mock_no_docker():
    with patch("src.plugins.sandbox._DOCKER_AVAILABLE", False):
        yield

# Mock docker client for success tests
@pytest.fixture
def mock_docker_client():
    with patch("src.plugins.sandbox._DOCKER_AVAILABLE", True), \
         patch("src.plugins.sandbox.docker") as mock:
        client = MagicMock()
        mock.from_env.return_value = client
        yield client


@pytest.mark.asyncio
async def test_sandbox_manifest(mock_docker_client):
    plugin = CodeSandboxPlugin()
    manifest = plugin.manifest()
    assert manifest.name == "code_sandbox"
    assert "execute_python" in manifest.actions

@pytest.mark.asyncio
async def test_sandbox_execution_success(mock_docker_client):
    plugin = CodeSandboxPlugin()

    # Mock container run output
    mock_docker_client.containers.run.return_value = b"Hello Sandbox"

    res = await plugin.execute("execute_python", {"code": "print('Hello Sandbox')"})

    assert res.success is True
    assert res.data["stdout"] == "Hello Sandbox"

    # Verify strict security calls
    mock_docker_client.containers.run.assert_called_once()
    args, kwargs = mock_docker_client.containers.run.call_args
    assert kwargs.get("network_mode") == "none"
    assert kwargs.get("read_only") is True
    assert kwargs.get("mem_limit") == "128m"

@pytest.mark.asyncio
async def test_sandbox_no_docker(mock_no_docker):
    plugin = CodeSandboxPlugin()
    res = await plugin.execute("execute_python", {"code": "print('fail')"})
    assert res.success is False
    assert "Docker SDK not installed" in res.error
