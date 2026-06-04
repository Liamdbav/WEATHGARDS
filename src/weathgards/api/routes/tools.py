"""Tool catalog, activation, and test-tool API routes."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from weathgards.mcp_server.tools.catalog import (
    CATALOG,
    HANDLER_MAP,
    ToolDefinition,
    get_tool,
)
from weathgards.mcp_server.tools.registry import ActivatedTool, get_registry

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["tools"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ActivateRequest(BaseModel):
    tool_name: str
    target_name: str


class TestToolRequest(BaseModel):
    tool_name: str
    target_name: str | None = None
    # Extra params beyond the target (e.g. lines=100 for docker_container_logs)
    params: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/catalog", response_model=list[ToolDefinition])
async def get_catalog() -> list[ToolDefinition]:
    """Return the full list of available tool templates."""
    return CATALOG


@router.get("/tools/active", response_model=list[ActivatedTool])
async def list_active_tools() -> list[ActivatedTool]:
    """Return all currently enabled (tool, target) activations."""
    registry = get_registry()
    return await asyncio.to_thread(registry.list_active)


@router.post("/activate-tool", response_model=ActivatedTool, status_code=201)
async def activate_tool(body: ActivateRequest) -> ActivatedTool:
    """Activate a tool template for a specific target.

    Idempotent: activating the same (tool, target) pair returns the existing
    entry. The tool_name must exist in the catalog.
    """
    if get_tool(body.tool_name) is None:
        raise HTTPException(
            status_code=422,
            detail=f"Tool '{body.tool_name}' is not in the catalog.",
        )

    registry = get_registry()
    entry = await asyncio.to_thread(registry.register, body.tool_name, body.target_name)
    log.info(
        "api.tool_activated",
        tool=body.tool_name,
        target=body.target_name,
        id=entry.id,
    )
    return entry


@router.delete("/tools/{entry_id}", status_code=204)
async def deactivate_tool(entry_id: str) -> None:
    """Disable an activated tool by its registry entry ID."""
    registry = get_registry()
    found = await asyncio.to_thread(registry.unregister, entry_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Entry '{entry_id}' not found.")


@router.post("/test-tool")
async def test_tool(body: TestToolRequest) -> dict[str, Any]:
    """Execute a catalog handler directly (in-process, no LLM involved).

    Uses the pre-written, static handler — this is NOT code generation.
    The target_name is bound to the tool's target_param; any additional
    params are merged and forwarded as keyword arguments.
    """
    tool_def = get_tool(body.tool_name)
    if tool_def is None:
        raise HTTPException(
            status_code=422,
            detail=f"Tool '{body.tool_name}' is not in the catalog.",
        )

    handler = HANDLER_MAP.get(body.tool_name)
    if handler is None:
        raise HTTPException(status_code=500, detail="Handler mapping inconsistency.")

    # Build keyword arguments: bind target_name to the tool's target param first,
    # then overlay any extra params from the request body.
    kwargs: dict[str, Any] = {}
    if tool_def.target_param and body.target_name is not None:
        kwargs[tool_def.target_param] = body.target_name
    kwargs.update(body.params)

    try:
        result: dict[str, Any] = await handler(**kwargs)  # type: ignore[arg-type]
    except Exception as exc:
        log.warning(
            "api.test_tool_failed",
            tool=body.tool_name,
            target=body.target_name,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    log.info("api.test_tool_ok", tool=body.tool_name, target=body.target_name)
    return result
