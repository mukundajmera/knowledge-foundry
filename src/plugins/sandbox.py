"""Knowledge Foundry — Code Sandbox Plugin.

Provides safe execution of Python code in isolated Docker containers.
"""

from __future__ import annotations

import asyncio
import structlog
from typing import Any

from src.core.interfaces import Plugin, PluginManifest, PluginResult

logger = structlog.get_logger(__name__)

# Check for Docker SDK availability
try:
    import docker
    from docker.errors import ContainerError, ImageNotFound, APIError
    _DOCKER_AVAILABLE = True
except ImportError:
    _DOCKER_AVAILABLE = False
    docker = None
    logger.warning("Docker SDK for Python not installed. CodeSandboxPlugin will be disabled.")


class CodeSandboxPlugin(Plugin):
    """Plugin for executing code in a sandboxed Docker container."""

    def __init__(self, image: str = "python:3.12-slim", timeout_svc: int = 10):
        self.image = image
        self.timeout = timeout_svc
        self.client = docker.from_env() if _DOCKER_AVAILABLE else None

    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="code_sandbox",
            version="1.0.0",
            description="Executes Python code in a secure, isolated sandbox.",
            actions=["execute_python"],
            permissions=["docker_socket", "read_only_fs"],
        )

    async def execute(self, action: str, params: dict[str, Any]) -> PluginResult:
        if not _DOCKER_AVAILABLE:
             return PluginResult(success=False, error="Docker SDK not installed")
        
        if not self.client:
             try:
                 self.client = docker.from_env()
             except Exception as e:
                 return PluginResult(success=False, error=f"Docker daemon not running: {e}")

        if action != "execute_python":
            return PluginResult(success=False, error=f"Unknown action: {action}")

        code = params.get("code")
        if not code:
            return PluginResult(success=False, error="Missing 'code' parameter")

        try:
            # Run blocking docker call in thread pool
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, self._run_container, code)
            return result
        except Exception as e:
            logger.exception("Sandbox execution failed")
            return PluginResult(success=False, error=str(e))

    def _run_container(self, code: str) -> PluginResult:
        """Run code in a fresh container."""
        # Ensure image exists
        try:
            self.client.images.get(self.image)
        except ImageNotFound:
            # This is blocking, might time out if network slow, but OK for MVP
            try:
                self.client.images.pull(self.image)
            except APIError as e:
                 return PluginResult(success=False, error=f"Failed to pull image: {e}")

        try:
            # We use 'python -c' to run the code
            # Network disabled, read-only root fs, limited resources
            logs = self.client.containers.run(
                self.image,
                command=["python", "-c", code],
                network_mode="none",
                mem_limit="128m",
                nano_cpus=500000000, # 0.5 CPU
                read_only=True,
                remove=True,
                stdout=True,
                stderr=True,
                detach=False
            )
            # logs is bytes
            output = logs.decode("utf-8").strip()
            return PluginResult(success=True, data={"stdout": output})

        except ContainerError as e:
             # Container exited with non-zero
             return PluginResult(success=False, error=f"Execution error: {e.stderr.decode('utf-8') if e.stderr else str(e)}")
        except APIError as e:
             return PluginResult(success=False, error=f"Docker API error: {str(e)}")
        except Exception as e:
             return PluginResult(success=False, error=f"Unexpected error: {str(e)}")
