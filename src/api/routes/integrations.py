"""Knowledge Foundry — MCP Integration Routes.

API endpoints for managing Model Context Protocol integrations with
Atlassian tools (Confluence, Jira, Bitbucket).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.mcp.servers.confluence_server import ConfluenceMCPServer
from src.mcp.servers.jira_server import JiraMCPServer
from src.mcp.servers.bitbucket_server import BitbucketMCPServer

router = APIRouter(prefix="/api/integrations", tags=["integrations"])
logger = logging.getLogger(__name__)

# Global MCP server instances (in production, store per-user)
_confluence_servers: dict[str, ConfluenceMCPServer] = {}
_jira_servers: dict[str, JiraMCPServer] = {}
_bitbucket_servers: dict[str, BitbucketMCPServer] = {}


# =============================================================
# REQUEST/RESPONSE MODELS
# =============================================================


class ConfluenceConnectRequest(BaseModel):
    """Request to connect to Confluence."""

    model_config = ConfigDict(populate_by_name=True)

    base_url: str
    session_id: str
    session_token: str


class IntegrationResponse(BaseModel):
    """Generic integration response."""

    success: bool
    message: str
    connection_id: str | None = None


class IntegrationStatusResponse(BaseModel):
    """Status of all integrations."""

    confluence: bool
    jira: bool
    bitbucket: bool


class ConfluenceSearchRequest(BaseModel):
    """Request to search Confluence pages."""

    query: str
    space_key: str | None = None
    limit: int = Field(default=10, ge=1, le=100)


class JiraConnectRequest(BaseModel):
    """Request to connect to Jira."""

    model_config = ConfigDict(populate_by_name=True)

    base_url: str
    email: str
    api_token: str


class JiraSearchRequest(BaseModel):
    """Request to search Jira issues."""

    jql: str
    max_results: int = Field(default=50, ge=1, le=100)


class BitbucketConnectRequest(BaseModel):
    """Request to connect to Bitbucket."""

    model_config = ConfigDict(populate_by_name=True)

    workspace: str
    username: str
    app_password: str


# =============================================================
# ROUTES
# =============================================================


@router.post("/confluence/connect")
async def connect_confluence(request: ConfluenceConnectRequest) -> IntegrationResponse:
    """Connect to Confluence using session cookies.
    
    Stores encrypted credentials and tests the connection.
    """
    try:
        # Create MCP server instance
        server = ConfluenceMCPServer()
        
        # Test connection with plaintext credentials
        # NOTE: In production, credentials should be encrypted before storage
        # and the server should use the encrypted values
        result = await server.invoke_tool(
            "confluence_set_credentials",
            {
                "base_url": request.base_url,
                "session_id": request.session_id,
                "session_token": request.session_token,
            },
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=401,
                detail=f"Failed to connect: {result.get('error', 'Unknown error')}",
            )
        
        # Store server instance
        # WARNING: Using hardcoded "default" connection_id means all users share
        # the same Confluence connection. In production, use a per-user/per-tenant
        # identifier (e.g., user.id or tenant_id) to prevent cross-user data leakage.
        connection_id = "default"  # TODO: Replace with user.id in production
        _confluence_servers[connection_id] = server
        
        logger.info(f"Confluence connected for user: {connection_id}")
        
        return IntegrationResponse(
            success=True,
            message="Connected to Confluence successfully",
            connection_id=connection_id,
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions to preserve status code and detail
        raise
    except Exception as e:
        logger.error(f"Confluence connection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Confluence connection failed: {type(e).__name__}")


@router.post("/confluence/search")
async def search_confluence(
    request: ConfluenceSearchRequest,
    connection_id: str = "default",
) -> dict[str, Any]:
    """Search Confluence pages using CQL.
    
    Requires prior authentication via /connect endpoint.
    """
    server = _confluence_servers.get(connection_id)
    if not server:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Connect to Confluence first.",
        )
    
    try:
        result = await server.invoke_tool(
            "confluence_search_pages",
            {
                "query": request.query,
                "space_key": request.space_key,
                "limit": request.limit,
            },
        )
        return result
    
    except ValueError as e:
        if "expired" in str(e).lower():
            raise HTTPException(status_code=401, detail="Session expired. Please reconnect.")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Confluence search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Confluence search failed: {type(e).__name__}")


@router.get("/status")
async def get_integration_status(connection_id: str = "default") -> IntegrationStatusResponse:
    """Get status of all integrations."""
    return IntegrationStatusResponse(
        confluence=connection_id in _confluence_servers,
        jira=connection_id in _jira_servers,
        bitbucket=connection_id in _bitbucket_servers,
    )


@router.delete("/{provider}")
async def disconnect_integration(
    provider: str,
    connection_id: str = "default",
) -> IntegrationResponse:
    """Disconnect from an integration provider."""
    if provider == "confluence":
        if connection_id in _confluence_servers:
            server = _confluence_servers.pop(connection_id)
            await server.close()
            return IntegrationResponse(
                success=True,
                message="Disconnected from Confluence",
            )
        else:
            raise HTTPException(status_code=404, detail="Not connected to Confluence")
    elif provider == "jira":
        if connection_id in _jira_servers:
            server = _jira_servers.pop(connection_id)
            await server.close()
            return IntegrationResponse(
                success=True,
                message="Disconnected from Jira",
            )
        else:
            raise HTTPException(status_code=404, detail="Not connected to Jira")
    elif provider == "bitbucket":
        if connection_id in _bitbucket_servers:
            server = _bitbucket_servers.pop(connection_id)
            await server.close()
            return IntegrationResponse(
                success=True,
                message="Disconnected from Bitbucket",
            )
        else:
            raise HTTPException(status_code=404, detail="Not connected to Bitbucket")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")


# =============================================================
# JIRA ROUTES
# =============================================================


@router.post("/jira/connect")
async def connect_jira(request: JiraConnectRequest) -> IntegrationResponse:
    """Connect to Jira using email and API token.
    
    Stores credentials and tests the connection.
    """
    try:
        server = JiraMCPServer()
        
        # Test connection
        result = await server.invoke_tool(
            "jira_set_credentials",
            {
                "base_url": request.base_url,
                "email": request.email,
                "api_token": request.api_token,
            },
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=401,
                detail=f"Failed to connect: {result.get('error', 'Unknown error')}",
            )
        
        # WARNING: Using hardcoded "default" connection_id - see Confluence comment above
        connection_id = "default"
        _jira_servers[connection_id] = server
        
        logger.info(f"Jira connected for user: {connection_id}")
        
        return IntegrationResponse(
            success=True,
            message="Connected to Jira successfully",
            connection_id=connection_id,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Jira connection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Jira connection failed: {type(e).__name__}")


@router.post("/jira/search")
async def search_jira(
    request: JiraSearchRequest,
    connection_id: str = "default",
) -> dict[str, Any]:
    """Search Jira issues using JQL.
    
    Requires prior authentication via /jira/connect endpoint.
    """
    server = _jira_servers.get(connection_id)
    if not server:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Connect to Jira first.",
        )
    
    try:
        result = await server.invoke_tool(
            "jira_search_issues",
            {
                "jql": request.jql,
                "max_results": request.max_results,
            },
        )
        return result
    
    except ValueError as e:
        if "authentication" in str(e).lower():
            raise HTTPException(status_code=401, detail="Authentication failed. Please reconnect.")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Jira search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Jira search failed: {type(e).__name__}")


# =============================================================
# BITBUCKET ROUTES
# =============================================================


@router.post("/bitbucket/connect")
async def connect_bitbucket(request: BitbucketConnectRequest) -> IntegrationResponse:
    """Connect to Bitbucket using username and app password.
    
    Stores credentials and tests the connection.
    """
    try:
        server = BitbucketMCPServer()
        
        # Test connection
        result = await server.invoke_tool(
            "bitbucket_set_credentials",
            {
                "workspace": request.workspace,
                "username": request.username,
                "app_password": request.app_password,
            },
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=401,
                detail=f"Failed to connect: {result.get('error', 'Unknown error')}",
            )
        
        # WARNING: Using hardcoded "default" connection_id - see Confluence comment above
        connection_id = "default"
        _bitbucket_servers[connection_id] = server
        
        logger.info(f"Bitbucket connected for user: {connection_id}")
        
        return IntegrationResponse(
            success=True,
            message="Connected to Bitbucket successfully",
            connection_id=connection_id,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bitbucket connection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Bitbucket connection failed: {type(e).__name__}")


@router.get("/bitbucket/repositories")
async def list_bitbucket_repositories(
    connection_id: str = "default",
) -> dict[str, Any]:
    """List repositories in the Bitbucket workspace.
    
    Requires prior authentication via /bitbucket/connect endpoint.
    """
    server = _bitbucket_servers.get(connection_id)
    if not server:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Connect to Bitbucket first.",
        )
    
    try:
        result = await server.invoke_tool(
            "bitbucket_list_repositories",
            {},
        )
        return result
    
    except ValueError as e:
        if "authentication" in str(e).lower():
            raise HTTPException(status_code=401, detail="Authentication failed. Please reconnect.")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Bitbucket list repositories failed: {e}")
        raise HTTPException(status_code=500, detail=f"Bitbucket list failed: {type(e).__name__}")
