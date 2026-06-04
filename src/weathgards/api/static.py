"""Static file serving for the React/Vite frontend build.

Strategy:
  - /api/* routes are handled by the API routers (registered first).
  - Everything else is served from frontend/dist/.
  - Any path that doesn't match a real file falls back to index.html
    so client-side routing works correctly.
  - If dist/ doesn't exist (dev mode without a build), we log a clear
    message instead of crashing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi import FastAPI

log = structlog.get_logger(__name__)


def mount_frontend(app: FastAPI, dist_dir: Path) -> None:
    if not dist_dir.exists():
        log.warning(
            "frontend.dist_missing",
            path=str(dist_dir),
            hint="Run `cd frontend && npm run build` to generate the static bundle.",
        )
        return

    # Serve static assets (JS, CSS, images) under their exact paths.
    app.mount(
        "/assets",
        StaticFiles(directory=dist_dir / "assets"),
        name="assets",
    )

    # SPA fallback: any non-/api/* request that isn't a known static asset
    # returns index.html so React Router can handle the path client-side.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        candidate = dist_dir / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist_dir / "index.html")
