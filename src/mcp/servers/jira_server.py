"""Knowledge Foundry — Jira MCP Server.

MCP server for Jira integration using token-based authentication.
Provides tools for searching issues, creating issues, and managing workflows.
"""

from __future__ import annotations

from typing import Any
import httpx
import logging

from src.mcp.base_server import MCPServer, MCPTool

logger = logging.getLogger(__name__)


class JiraMCPServer(MCPServer):
    """Jira MCP server with token-based authentication."""

    def _register_tools(self) -> None:
        """Register Jira tools."""
        self._tools = [
            MCPTool(
                name="jira_set_credentials",
                description="Authenticate with Jira using email and API token",
                input_schema={
                    "type": "object",
                    "properties": {
                        "base_url": {
                            "type": "string",
                            "description": "Jira URL (e.g., https://company.atlassian.net)",
                        },
                        "email": {
                            "type": "string",
                            "description": "User email address",
                        },
                        "api_token": {
                            "type": "string",
                            "description": "Jira API token",
                        },
                    },
                    "required": ["base_url", "email", "api_token"],
                },
            ),
            MCPTool(
                name="jira_search_issues",
                description="Search Jira issues using JQL",
                input_schema={
                    "type": "object",
                    "properties": {
                        "jql": {
                            "type": "string",
                            "description": "JQL query (e.g., 'project = PROJ AND status = Open')",
                        },
                        "max_results": {
                            "type": "integer",
                            "default": 50,
                            "description": "Maximum number of results (1-100)",
                        },
                    },
                    "required": ["jql"],
                },
            ),
            MCPTool(
                name="jira_get_issue",
                description="Get detailed information about a Jira issue",
                input_schema={
                    "type": "object",
                    "properties": {
                        "issue_key": {
                            "type": "string",
                            "description": "Issue key (e.g., PROJ-123)",
                        },
                    },
                    "required": ["issue_key"],
                },
            ),
            MCPTool(
                name="jira_create_issue",
                description="Create a new Jira issue",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project_key": {
                            "type": "string",
                            "description": "Project key (e.g., PROJ)",
                        },
                        "issue_type": {
                            "type": "string",
                            "description": "Issue type (e.g., Bug, Task, Story)",
                        },
                        "summary": {
                            "type": "string",
                            "description": "Issue summary/title",
                        },
                        "description": {
                            "type": "string",
                            "description": "Issue description",
                        },
                    },
                    "required": ["project_key", "issue_type", "summary"],
                },
            ),
        ]

    async def invoke_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke a Jira tool.
        
        Args:
            tool_name: Name of tool to invoke.
            arguments: Tool arguments.
        
        Returns:
            Tool execution result.
        """
        if tool_name == "jira_set_credentials":
            return await self._set_credentials(arguments)
        elif tool_name == "jira_search_issues":
            return await self._search_issues(arguments)
        elif tool_name == "jira_get_issue":
            return await self._get_issue(arguments)
        elif tool_name == "jira_create_issue":
            return await self._create_issue(arguments)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    async def _set_credentials(self, args: dict[str, Any]) -> dict[str, Any]:
        """Set Jira credentials."""
        self.set_credentials({
            "base_url": args["base_url"],
            "email": args["email"],
            "api_token": args["api_token"],
        })
        
        # Test the connection
        try:
            await self._test_connection()
            return {"success": True, "message": "Credentials set successfully"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _test_connection(self) -> None:
        """Test Jira connection."""
        if not self._credentials:
            raise ValueError("Credentials not set")

        base_url = self._credentials["base_url"]
        auth = (self._credentials["email"], self._credentials["api_token"])

        client = self._get_client()
        response = await client.get(
            f"{base_url}/rest/api/3/myself",
            auth=auth,
        )
        
        if response.status_code == 401:
            raise ValueError("Invalid credentials")
        
        response.raise_for_status()

    async def _search_issues(self, args: dict[str, Any]) -> dict[str, Any]:
        """Search Jira issues using JQL."""
        if not self._credentials:
            raise ValueError("Credentials not set. Call jira_set_credentials first.")

        jql = args["jql"]
        max_results = args.get("max_results", 50)

        base_url = self._credentials["base_url"]
        auth = (self._credentials["email"], self._credentials["api_token"])

        client = self._get_client()
        
        try:
            response = await client.get(
                f"{base_url}/rest/api/3/search",
                params={"jql": jql, "maxResults": max_results},
                auth=auth,
                headers={"Accept": "application/json"},
            )

            if response.status_code == 401:
                raise ValueError("Authentication failed. Re-authenticate with Jira.")

            response.raise_for_status()
            data = response.json()

            return {
                "total": data.get("total", 0),
                "issues": [
                    {
                        "key": issue["key"],
                        "summary": issue["fields"]["summary"],
                        "status": issue["fields"]["status"]["name"],
                        "priority": issue["fields"].get("priority", {}).get("name"),
                        "assignee": issue["fields"].get("assignee", {}).get("displayName"),
                        "created": issue["fields"]["created"],
                        "updated": issue["fields"]["updated"],
                    }
                    for issue in data.get("issues", [])
                ],
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"Jira search failed: {e}")
            raise ValueError(f"Jira API error: {e.response.status_code}")

    async def _get_issue(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get detailed Jira issue information."""
        if not self._credentials:
            raise ValueError("Credentials not set")

        issue_key = args["issue_key"]
        base_url = self._credentials["base_url"]
        auth = (self._credentials["email"], self._credentials["api_token"])

        client = self._get_client()
        
        try:
            response = await client.get(
                f"{base_url}/rest/api/3/issue/{issue_key}",
                auth=auth,
                headers={"Accept": "application/json"},
            )
            
            if response.status_code == 401:
                raise ValueError("Authentication failed")
            
            if response.status_code == 404:
                raise ValueError(f"Issue {issue_key} not found")
                
            response.raise_for_status()
            issue = response.json()

            return {
                "key": issue["key"],
                "summary": issue["fields"]["summary"],
                "description": issue["fields"].get("description"),
                "status": issue["fields"]["status"]["name"],
                "priority": issue["fields"].get("priority", {}).get("name"),
                "assignee": issue["fields"].get("assignee", {}).get("displayName"),
                "reporter": issue["fields"].get("reporter", {}).get("displayName"),
                "created": issue["fields"]["created"],
                "updated": issue["fields"]["updated"],
                "project": issue["fields"]["project"]["name"],
            }
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Failed to get issue: {e.response.status_code}")

    async def _create_issue(self, args: dict[str, Any]) -> dict[str, Any]:
        """Create a new Jira issue."""
        if not self._credentials:
            raise ValueError("Credentials not set")

        base_url = self._credentials["base_url"]
        auth = (self._credentials["email"], self._credentials["api_token"])

        client = self._get_client()
        
        payload = {
            "fields": {
                "project": {"key": args["project_key"]},
                "summary": args["summary"],
                "issuetype": {"name": args["issue_type"]},
            }
        }
        
        if "description" in args:
            payload["fields"]["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": args["description"]}],
                    }
                ],
            }
        
        try:
            response = await client.post(
                f"{base_url}/rest/api/3/issue",
                json=payload,
                auth=auth,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            
            if response.status_code == 401:
                raise ValueError("Authentication failed")
                
            response.raise_for_status()
            data = response.json()

            return {
                "success": True,
                "key": data["key"],
                "id": data["id"],
                "self": data["self"],
            }
        except httpx.HTTPStatusError as e:
            error_detail = e.response.json() if e.response.content else {}
            raise ValueError(f"Failed to create issue: {error_detail.get('errors', str(e))}")
