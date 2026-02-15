"""Knowledge Foundry — Base MCP Server.

Base class for Model Context Protocol (MCP) servers that connect
to external tools like Confluence, Jira, and Bitbucket.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
import httpx
import logging

logger = logging.getLogger(__name__)


class MCPTool:
    """Represents an MCP tool that can be invoked."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
    ) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema


class MCPServer(ABC):
    """Base class for MCP servers.
    
    Each MCP server provides tools for interacting with an external service.
    Subclasses implement specific integrations (Confluence, Jira, Bitbucket).
    """

    def __init__(self) -> None:
        self._tools: list[MCPTool] = []
        self._client: httpx.AsyncClient | None = None
        self._credentials: dict[str, str] = {}
        self._register_tools()

    @abstractmethod
    def _register_tools(self) -> None:
        """Register available tools for this server."""
        pass

    @abstractmethod
    async def invoke_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke a tool with the given arguments.
        
        Args:
            tool_name: Name of the tool to invoke.
            arguments: Tool arguments as dictionary.
        
        Returns:
            Tool execution result.
        
        Raises:
            ValueError: If tool not found.
        """
        pass

    def set_credentials(self, credentials: dict[str, str]) -> None:
        """Set credentials for this MCP server.
        
        Args:
            credentials: Dictionary containing auth credentials.
        """
        self._credentials = credentials

    def get_tools(self) -> list[MCPTool]:
        """Get list of available tools."""
        return self._tools

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
