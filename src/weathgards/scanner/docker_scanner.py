"""Docker container scanner.

Uses the official docker SDK which handles Unix sockets (Linux/macOS) and
named pipes (Windows Docker Desktop) transparently via DOCKER_HOST or the
docker_host setting. Never crashes — returns [] and logs a warning when the
daemon is unreachable.
"""

from __future__ import annotations

import contextlib
import time

import structlog

from weathgards.platform_utils import current_os, docker_socket_uri, is_docker_available
from weathgards.scanner.models import DockerMeta, ScanResult

log = structlog.get_logger(__name__)

# Statuses considered "running" vs everything else
_RUNNING_STATUSES = {"running", "restarting"}


def _parse_ports(ports_raw: dict | None) -> dict[str, list[str]]:
    """Convert docker SDK port dict to a plain {container_port: [host_addr, ...]} map."""
    if not ports_raw:
        return {}
    result: dict[str, list[str]] = {}
    for container_port, bindings in ports_raw.items():
        if bindings:
            result[container_port] = [
                f"{b['HostIp']}:{b['HostPort']}" for b in bindings if b
            ]
        else:
            result[container_port] = []
    return result


def _uptime_seconds(started_at: str | None) -> int | None:
    """Return seconds since container start, or None if unparseable."""
    if not started_at or started_at.startswith("0001-"):
        return None
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        return max(0, int(time.time() - dt.timestamp()))
    except (ValueError, TypeError):
        return None


def scan_docker(docker_host: str | None = None) -> list[ScanResult]:
    """Return a ScanResult for every container known to the Docker daemon.

    Args:
        docker_host: Override the socket URI (e.g. from settings). When None,
                     falls back to docker_socket_uri() then SDK auto-detect.

    Returns an empty list — never raises — if Docker is unavailable.
    """
    if not is_docker_available() and docker_host is None:
        log.debug("docker.skipped", reason="daemon socket not found")
        return []

    try:
        import docker
    except ImportError:
        log.warning("docker.import_failed", reason="docker package not installed")
        return []

    base_url = docker_host or docker_socket_uri()
    try:
        client = (
            docker.DockerClient(base_url=base_url, timeout=10)
            if base_url
            else docker.from_env(timeout=10)
        )
    except Exception as exc:
        log.warning("docker.client_init_failed", error=str(exc))
        return []

    os_id = current_os()
    results: list[ScanResult] = []

    try:
        containers = client.containers.list(all=True)
    except Exception as exc:
        log.warning("docker.list_failed", error=str(exc))
        return []
    finally:
        with contextlib.suppress(Exception):
            client.close()

    for container in containers:
        try:
            attrs = container.attrs or {}
            state = attrs.get("State", {})
            config = attrs.get("Config", {})
            net = attrs.get("NetworkSettings", {})

            name = container.name or container.short_id
            status = state.get("Status", "unknown")
            image = config.get("Image", "unknown")
            labels: dict[str, str] = config.get("Labels") or {}
            ports = _parse_ports(net.get("Ports"))
            uptime = _uptime_seconds(state.get("StartedAt"))

            results.append(
                ScanResult(
                    name=name,
                    type="docker",
                    status=status,
                    metadata=DockerMeta(
                        image=image,
                        ports=ports,
                        labels=labels,
                        uptime_seconds=uptime,
                    ),
                    os_origin=os_id,
                )
            )
        except Exception as exc:
            log.warning("docker.container_parse_failed", container=str(container), error=str(exc))

    log.info("docker.scan_complete", count=len(results))
    return results
