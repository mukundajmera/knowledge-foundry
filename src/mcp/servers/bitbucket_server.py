"""Knowledge Foundry — Bitbucket MCP Server.

MCP server for Bitbucket integration using app password authentication.
Provides tools for repository operations, pull requests, and code search.
"""

from __future__ import annotations

from typing import Any
import httpx
import logging

from src.mcp.base_server import MCPServer, MCPTool

logger = logging.getLogger(__name__)


class BitbucketMCPServer(MCPServer):
    """Bitbucket MCP server with app password authentication."""

    def _register_tools(self) -> None:
        """Register Bitbucket tools."""
        self._tools = [
            MCPTool(
                name="bitbucket_set_credentials",
                description="Authenticate with Bitbucket using username and app password",
                input_schema={
                    "type": "object",
                    "properties": {
                        "workspace": {
                            "type": "string",
                            "description": "Bitbucket workspace slug",
                        },
                        "username": {
                            "type": "string",
                            "description": "Bitbucket username",
                        },
                        "app_password": {
                            "type": "string",
                            "description": "Bitbucket app password",
                        },
                    },
                    "required": ["workspace", "username", "app_password"],
                },
            ),
            MCPTool(
                name="bitbucket_list_repositories",
                description="List repositories in the workspace",
                input_schema={
                    "type": "object",
                    "properties": {
                        "max_results": {
                            "type": "integer",
                            "default": 50,
                            "description": "Maximum number of results",
                        },
                    },
                },
            ),
            MCPTool(
                name="bitbucket_search_code",
                description="Search code across repositories",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "repo_slug": {
                            "type": "string",
                            "description": "Repository slug (optional)",
                        },
                    },
                    "required": ["query"],
                },
            ),
            MCPTool(
                name="bitbucket_get_pull_requests",
                description="Get pull requests for a repository",
                input_schema={
                    "type": "object",
                    "properties": {
                        "repo_slug": {
                            "type": "string",
                            "description": "Repository slug",
                        },
                        "state": {
                            "type": "string",
                            "enum": ["OPEN", "MERGED", "DECLINED"],
                            "default": "OPEN",
                            "description": "PR state filter",
                        },
                    },
                    "required": ["repo_slug"],
                },
            ),
        ]

    async def invoke_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke a Bitbucket tool.
        
        Args:
            tool_name: Name of tool to invoke.
            arguments: Tool arguments.
        
        Returns:
            Tool execution result.
        """
        if tool_name == "bitbucket_set_credentials":
            return await self._set_credentials(arguments)
        elif tool_name == "bitbucket_list_repositories":
            return await self._list_repositories(arguments)
        elif tool_name == "bitbucket_search_code":
            return await self._search_code(arguments)
        elif tool_name == "bitbucket_get_pull_requests":
            return await self._get_pull_requests(arguments)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    async def _set_credentials(self, args: dict[str, Any]) -> dict[str, Any]:
        """Set Bitbucket credentials."""
        self.set_credentials({
            "workspace": args["workspace"],
            "username": args["username"],
            "app_password": args["app_password"],
        })
        
        # Test the connection
        try:
            await self._test_connection()
            return {"success": True, "message": "Credentials set successfully"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _test_connection(self) -> None:
        """Test Bitbucket connection."""
        if not self._credentials:
            raise ValueError("Credentials not set")

        workspace = self._credentials["workspace"]
        auth = (self._credentials["username"], self._credentials["app_password"])

        client = self._get_client()
        response = await client.get(
            f"https://api.bitbucket.org/2.0/workspaces/{workspace}",
            auth=auth,
        )
        
        if response.status_code == 401:
            raise ValueError("Invalid credentials")
        
        if response.status_code == 404:
            raise ValueError(f"Workspace '{workspace}' not found")
        
        response.raise_for_status()

    async def _list_repositories(self, args: dict[str, Any]) -> dict[str, Any]:
        """List repositories in the workspace."""
        if not self._credentials:
            raise ValueError("Credentials not set. Call bitbucket_set_credentials first.")

        workspace = self._credentials["workspace"]
        max_results = args.get("max_results", 50)
        auth = (self._credentials["username"], self._credentials["app_password"])

        client = self._get_client()
        
        try:
            response = await client.get(
                f"https://api.bitbucket.org/2.0/repositories/{workspace}",
                params={"pagelen": max_results},
                auth=auth,
            )

            if response.status_code == 401:
                raise ValueError("Authentication failed. Re-authenticate with Bitbucket.")

            response.raise_for_status()
            data = response.json()

            return {
                "repositories": [
                    {
                        "slug": repo["slug"],
                        "name": repo["name"],
                        "full_name": repo["full_name"],
                        "description": repo.get("description"),
                        "is_private": repo["is_private"],
                        "language": repo.get("language"),
                        "updated": repo["updated_on"],
                    }
                    for repo in data.get("values", [])
                ],
                "total": data.get("size", 0),
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"Bitbucket list repositories failed: {e}")
            raise ValueError(f"Bitbucket API error: {e.response.status_code}")

    async def _search_code(self, args: dict[str, Any]) -> dict[str, Any]:
        """Search code across repositories."""
        if not self._credentials:
            raise ValueError("Credentials not set")

        workspace = self._credentials["workspace"]
        query = args["query"]
        repo_slug = args.get("repo_slug")
        auth = (self._credentials["username"], self._credentials["app_password"])

        client = self._get_client()
        
        # Build search URL
        if repo_slug:
            search_url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/search/code"
        else:
            # Search across all repos in workspace (requires iterating repos)
            # For simplicity, we'll require a repo_slug for now
            raise ValueError("repo_slug is required for code search")
        
        try:
            response = await client.get(
                search_url,
                params={"search_query": query},
                auth=auth,
            )
            
            if response.status_code == 401:
                raise ValueError("Authentication failed")
                
            response.raise_for_status()
            data = response.json()

            return {
                "results": [
                    {
                        "path": result["path_matches"][0]["text"] if result.get("path_matches") else "",
                        "content_matches": [
                            {
                                "line": match.get("line"),
                                "text": match.get("text"),
                            }
                            for match in result.get("content_matches", [])
                        ],
                    }
                    for result in data.get("values", [])
                ],
                "total": data.get("size", 0),
            }
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Failed to search code: {e.response.status_code}")

    async def _get_pull_requests(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get pull requests for a repository."""
        if not self._credentials:
            raise ValueError("Credentials not set")

        workspace = self._credentials["workspace"]
        repo_slug = args["repo_slug"]
        state = args.get("state", "OPEN")
        auth = (self._credentials["username"], self._credentials["app_password"])

        client = self._get_client()
        
        try:
            response = await client.get(
                f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests",
                params={"state": state},
                auth=auth,
            )
            
            if response.status_code == 401:
                raise ValueError("Authentication failed")
            
            if response.status_code == 404:
                raise ValueError(f"Repository {repo_slug} not found")
                
            response.raise_for_status()
            data = response.json()

            return {
                "pull_requests": [
                    {
                        "id": pr["id"],
                        "title": pr["title"],
                        "state": pr["state"],
                        "author": pr["author"]["display_name"],
                        "created": pr["created_on"],
                        "updated": pr["updated_on"],
                        "source_branch": pr["source"]["branch"]["name"],
                        "destination_branch": pr["destination"]["branch"]["name"],
                    }
                    for pr in data.get("values", [])
                ],
                "total": data.get("size", 0),
            }
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Failed to get pull requests: {e.response.status_code}")
