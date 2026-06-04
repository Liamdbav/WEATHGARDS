"""GET/PUT /api/settings — runtime-mutable application configuration."""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter

from weathgards.config.settings import AppSettings, get_app_settings, save_app_settings

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings", response_model=AppSettings)
async def read_settings() -> AppSettings:
    """Return current runtime settings (loaded from config_dir()/settings.json)."""
    return await asyncio.to_thread(get_app_settings)


@router.put("/settings", response_model=AppSettings)
async def write_settings(body: AppSettings) -> AppSettings:
    """Persist updated settings. MCP server changes take effect on next start."""
    await asyncio.to_thread(save_app_settings, body)
    log.info(
        "api.settings.updated",
        mcp_host=body.mcp_host,
        mcp_port=body.mcp_port,
        network_exposed=body.network_exposed,
        auto_scan_interval=body.auto_scan_interval,
    )
    return body
