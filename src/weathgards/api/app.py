"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from weathgards.api.routes.scan import router as scan_router
from weathgards.api.routes.server import router as server_router
from weathgards.api.routes.settings import router as settings_router
from weathgards.api.routes.tools import router as tools_router
from weathgards.api.static import mount_frontend
from weathgards.config.settings import get_settings
from weathgards.platform_utils import is_docker_available

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()

    docker_ok = is_docker_available()
    log.info(
        "weathgards.startup",
        docker_available=docker_ok,
        docker_host=settings.docker_host or "auto",
    )

    # Store shared state on app.state so routes can access it if needed.
    app.state.docker_available = docker_ok
    app.state.settings = settings

    yield

    log.info("weathgards.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="WEATHGARDS",
        version="0.1.0",
        description="Local cross-OS MCP gateway",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        lifespan=lifespan,
    )

    # CORS: allow the Vite dev server to reach the API during development.
    # In production the frontend is served from the same origin so this is a no-op.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(scan_router)
    app.include_router(tools_router)
    app.include_router(server_router)
    app.include_router(settings_router)
    mount_frontend(app, settings.static_dir)

    return app
