"""Knowledge Foundry — Confluence MCP Server.

MCP server for Confluence integration using session-based authentication.
Provides tools for searching pages, retrieving content, and listing spaces.
"""

from __future__ import annotations

from typing import Any
import httpx
import logging

from src.mcp.base_server import MCPServer, MCPTool

logger = logging.getLogger(__name__)


class ConfluenceMCPServer(MCPServer):
    """Confluence MCP server with session-based authentication."""

    def _register_tools(self) -> None:
        """Register Confluence tools."""
        self._tools = [
            MCPTool(
                name="confluence_set_credentials",
                description="Authenticate with Confluence using session cookies",
                input_schema={
                    "type": "object",
                    "properties": {
                        "base_url": {
                            "type": "string",
                            "description": "Confluence URL (e.g., https://company.atlassian.net/wiki)",
                        },
                        "session_id": {
                            "type": "string",
                            "description": "JSESSIONID cookie value",
                        },
                        "session_token": {
                            "type": "string",
                            "description": "cloud.session.token cookie value",
                        },
                    },
                    "required": ["base_url", "session_id", "session_token"],
                },
            ),
            MCPTool(
                name="confluence_search_pages",
                description="Search Confluence pages using CQL",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (CQL syntax: text ~ \"keyword\")",
                        },
                        "space_key": {
                            "type": "string",
                            "description": "Filter by space (optional)",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "description": "Max results (1-100)",
                        },
                    },
                    "required": ["query"],
                },
            ),
            MCPTool(
                name="confluence_get_page_content",
                description="Retrieve full content of a Confluence page",
                input_schema={
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "Confluence page ID",
                        },
                    },
                    "required": ["page_id"],
                },
            ),
            MCPTool(
                name="confluence_list_spaces",
                description="List all accessible Confluence spaces",
                input_schema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    async def invoke_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke a Confluence tool.
        
        Args:
            tool_name: Name of tool to invoke.
            arguments: Tool arguments.
        
        Returns:
            Tool execution result.
        """
        if tool_name == "confluence_set_credentials":
            return await self._set_credentials(arguments)
        elif tool_name == "confluence_search_pages":
            return await self._search_pages(arguments)
        elif tool_name == "confluence_get_page_content":
            return await self._get_page_content(arguments)
        elif tool_name == "confluence_list_spaces":
            return await self._list_spaces()
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    async def _set_credentials(self, args: dict[str, Any]) -> dict[str, Any]:
        """Set Confluence credentials."""
        self.set_credentials({
            "base_url": args["base_url"],
            "session_id": args["session_id"],
            "session_token": args["session_token"],
        })
        
        # Test the connection
        try:
            await self._list_spaces()
            return {"success": True, "message": "Credentials set successfully"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _search_pages(self, args: dict[str, Any]) -> dict[str, Any]:
        """Search Confluence pages using CQL."""
        if not self._credentials:
            raise ValueError("Credentials not set. Call confluence_set_credentials first.")

        query = args["query"]
        space_key = args.get("space_key")
        limit = args.get("limit", 10)

        # Build CQL query
        cql = f'text ~ "{query}"'
        if space_key:
            cql += f" AND space = {space_key}"

        base_url = self._credentials["base_url"]
        headers = {
            "Cookie": f"JSESSIONID={self._credentials['session_id']}; cloud.session.token={self._credentials['session_token']}",
            "Content-Type": "application/json",
        }

        client = self._get_client()
        
        try:
            response = await client.get(
                f"{base_url}/rest/api/content/search",
                params={"cql": cql, "limit": limit, "expand": "space,version"},
                headers=headers,
            )

            if response.status_code == 401:
                raise ValueError("Session expired. Re-authenticate with Confluence.")

            response.raise_for_status()
            data = response.json()

            return {
                "results": [
                    {
                        "id": page["id"],
                        "title": page["title"],
                        "space": page["space"]["name"],
                        "url": f"{base_url}{page['_links']['webui']}",
                        "lastModified": page["version"]["when"],
                    }
                    for page in data["results"]
                ],
                "total": data["size"],
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"Confluence search failed: {e}")
            raise ValueError(f"Confluence API error: {e.response.status_code}")

    async def _get_page_content(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get full content of a Confluence page."""
        if not self._credentials:
            raise ValueError("Credentials not set")

        page_id = args["page_id"]
        base_url = self._credentials["base_url"]
        headers = {
            "Cookie": f"JSESSIONID={self._credentials['session_id']}; cloud.session.token={self._credentials['session_token']}",
        }

        client = self._get_client()
        
        try:
            response = await client.get(
                f"{base_url}/rest/api/content/{page_id}",
                params={"expand": "body.storage,version"},
                headers=headers,
            )
            
            if response.status_code == 401:
                raise ValueError("Session expired")
                
            response.raise_for_status()
            data = response.json()

            return {
                "id": data["id"],
                "title": data["title"],
                "content": data["body"]["storage"]["value"],
                "lastModified": data["version"]["when"],
            }
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Failed to get page content: {e.response.status_code}")

    async def _list_spaces(self) -> dict[str, Any]:
        """List all accessible Confluence spaces."""
        if not self._credentials:
            raise ValueError("Credentials not set")

        base_url = self._credentials["base_url"]
        headers = {
            "Cookie": f"JSESSIONID={self._credentials['session_id']}; cloud.session.token={self._credentials['session_token']}",
        }

        client = self._get_client()
        
        try:
            response = await client.get(
                f"{base_url}/rest/api/space",
                headers=headers,
            )
            
            if response.status_code == 401:
                raise ValueError("Session expired")
                
            response.raise_for_status()
            data = response.json()

            return {
                "spaces": [
                    {
                        "key": space["key"],
                        "name": space["name"],
                        "type": space["type"],
                    }
                    for space in data["results"]
                ],
                "total": data["size"],
            }
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Failed to list spaces: {e.response.status_code}")
