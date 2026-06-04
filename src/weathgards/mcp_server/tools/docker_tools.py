"""Static, read-only Docker tool handlers.

Each public function is a parameterised handler invoked by name from the
catalog. Target name is the only runtime variable — no code is generated.
All blocking docker SDK calls run in asyncio.to_thread so the event loop
is never blocked.

Strictly READ-ONLY: no start / stop / exec / commit / push operations.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import structlog

from weathgards.platform_utils import docker_socket_uri, is_docker_available

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_client(docker_host: str | None = None) -> Any:  # type: ignore[return]
    """Return a DockerClient; raises RuntimeError when Docker is unavailable."""
    try:
        import docker  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("docker package not installed") from exc

    if not is_docker_available() and docker_host is None:
        raise RuntimeError("Docker daemon socket not reachable on this host")

    base_url = docker_host or docker_socket_uri()
    try:
        if base_url:
            return docker.DockerClient(base_url=base_url, timeout=10)
        return docker.from_env(timeout=10)
    except Exception as exc:
        raise RuntimeError(f"Docker client initialisation failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Sync implementations (run in thread)
# ---------------------------------------------------------------------------

def _container_status_sync(name: str) -> dict[str, Any]:
    try:
        import docker  # type: ignore[import-untyped]
        client = _build_client()
    except RuntimeError as exc:
        return {"error": str(exc)}

    try:
        container = client.containers.get(name)
        attrs: dict[str, Any] = container.attrs or {}
        state: dict[str, Any] = attrs.get("State", {})
        config: dict[str, Any] = attrs.get("Config", {})
        health_status: str | None = None
        if "Health" in state:
            health_status = state["Health"].get("Status")
        return {
            "name": container.name,
            "id": container.short_id,
            "status": state.get("Status", "unknown"),
            "health": health_status,
            "image": config.get("Image", "unknown"),
            "exit_code": state.get("ExitCode"),
            "started_at": state.get("StartedAt"),
            "finished_at": state.get("FinishedAt"),
        }
    except docker.errors.NotFound:
        return {"error": f"Container '{name}' not found"}
    except docker.errors.APIError as exc:
        log.warning("docker_tools.status_api_error", name=name, error=str(exc))
        return {"error": f"Docker API error: {exc}"}
    finally:
        with contextlib.suppress(Exception):
            client.close()


def _container_logs_sync(name: str, lines: int = 50) -> dict[str, Any]:
    try:
        import docker  # type: ignore[import-untyped]
        client = _build_client()
    except RuntimeError as exc:
        return {"error": str(exc)}

    try:
        container = client.containers.get(name)
        raw: bytes = container.logs(
            tail=lines,
            timestamps=True,
            stream=False,
        )
        log_lines = raw.decode("utf-8", errors="replace").splitlines()
        return {
            "name": name,
            "lines": log_lines,
            "count": len(log_lines),
        }
    except docker.errors.NotFound:
        return {"error": f"Container '{name}' not found"}
    except docker.errors.APIError as exc:
        log.warning("docker_tools.logs_api_error", name=name, error=str(exc))
        return {"error": f"Docker API error: {exc}"}
    finally:
        with contextlib.suppress(Exception):
            client.close()


def _list_containers_sync() -> dict[str, Any]:
    try:
        import docker  # type: ignore[import-untyped]
        client = _build_client()
    except RuntimeError as exc:
        return {"error": str(exc)}

    try:
        containers = client.containers.list(all=True)
        items: list[dict[str, Any]] = []
        for c in containers:
            attrs: dict[str, Any] = c.attrs or {}
            state: dict[str, Any] = attrs.get("State", {})
            config: dict[str, Any] = attrs.get("Config", {})
            items.append(
                {
                    "name": c.name,
                    "id": c.short_id,
                    "status": state.get("Status", "unknown"),
                    "image": config.get("Image", "unknown"),
                }
            )
        return {"containers": items, "count": len(items)}
    except docker.errors.APIError as exc:
        log.warning("docker_tools.list_api_error", error=str(exc))
        return {"error": f"Docker API error: {exc}"}
    finally:
        with contextlib.suppress(Exception):
            client.close()


# ---------------------------------------------------------------------------
# Public async handlers (called by catalog / routes)
# ---------------------------------------------------------------------------

async def docker_container_status(name: str) -> dict[str, Any]:
    """Return status, health, image, exit code, and timestamps for a container."""
    return await asyncio.to_thread(_container_status_sync, name)


async def docker_container_logs(name: str, lines: int = 50) -> dict[str, Any]:
    """Return the last *lines* log entries from a container, with timestamps."""
    return await asyncio.to_thread(_container_logs_sync, name, lines)


async def docker_list_containers() -> dict[str, Any]:
    """List all containers (running and stopped) with basic metadata."""
    return await asyncio.to_thread(_list_containers_sync)
