"""MCP server control API — start, stop, status, connection info."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from weathgards.mcp_server.server import (
    MCPConnectionInfo,
    MCPSnippets,
    MCPStatus,
    get_manager,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["mcp-server"])

_DEFAULT_MCP_PORT = 9766


class StartRequest(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=_DEFAULT_MCP_PORT, ge=1, le=65535)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/start", response_model=MCPStatus)
async def start_mcp_server(body: StartRequest) -> MCPStatus:
    """Start the MCP server on the given host/port.

    Binding to 0.0.0.0 requires a valid token (auto-generated on first use).
    Returns 409 if already running; returns 422 for security violations.
    """
    manager = get_manager()

    if manager.is_running():
        raise HTTPException(
            status_code=409,
            detail="MCP server is already running. POST /api/mcp/stop first.",
        )

    try:
        await manager.start(body.host, body.port)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    log.info("api.mcp.started", host=body.host, port=body.port)
    return manager.status()


@router.post("/stop", response_model=MCPStatus)
async def stop_mcp_server() -> MCPStatus:
    """Gracefully stop the running MCP server."""
    manager = get_manager()
    if not manager.is_running():
        raise HTTPException(status_code=409, detail="MCP server is not running.")
    await manager.stop()
    log.info("api.mcp.stopped")
    return manager.status()


@router.get("/status", response_model=MCPStatus)
async def get_mcp_status() -> MCPStatus:
    """Return current MCP server status (running, host, port, tool count)."""
    return get_manager().status()


@router.get("/snippets", response_model=MCPSnippets)
async def get_config_snippets() -> MCPSnippets:
    """Return ready-to-use config snippets for all supported MCP clients.

    Always available — works whether the MCP server is running or not.
    When stopped, host/port come from AppSettings (configured defaults).
    """
    return get_manager().get_snippets()


@router.get("/connection-info", response_model=MCPConnectionInfo)
async def get_connection_info() -> MCPConnectionInfo:
    """Return the URL, token, and a ready-to-use client config snippet.

    Returns 409 if the server is not running.
    """
    manager = get_manager()
    info = manager.connection_info()
    if info is None:
        raise HTTPException(
            status_code=409,
            detail="MCP server is not running. POST /api/mcp/start first.",
        )
    return info
