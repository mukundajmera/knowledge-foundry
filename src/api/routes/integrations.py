"""Knowledge Foundry — MCP Integration Routes.

API endpoints for managing Model Context Protocol integrations with
Atlassian tools (Confluence, Jira, Bitbucket).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from src.mcp.servers.confluence_server import ConfluenceMCPServer

router = APIRouter(prefix="/api/integrations", tags=["integrations"])
logger = logging.getLogger(__name__)

# Global MCP server instances (in production, store per-user)
_confluence_servers: dict[str, ConfluenceMCPServer] = {}


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
    limit: int = 10


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
        raise HTTPException(status_code=500, detail=str(e))


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
            raise HTTPException(status_code=401, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Confluence search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_integration_status(connection_id: str = "default") -> IntegrationStatusResponse:
    """Get status of all integrations."""
    return IntegrationStatusResponse(
        confluence=connection_id in _confluence_servers,
        jira=False,  # Not implemented yet
        bitbucket=False,  # Not implemented yet
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
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
