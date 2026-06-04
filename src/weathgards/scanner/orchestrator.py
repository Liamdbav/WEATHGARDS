"""Scanner orchestrator — runs all sub-scanners concurrently and caches results.

Synchronous scanner functions are wrapped in asyncio.to_thread() so they
never block the event loop. The last successful scan is kept in memory for
fast retrieval by the activation layer.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

from weathgards.scanner.docker_scanner import scan_docker
from weathgards.scanner.process_scanner import scan_processes
from weathgards.scanner.service_scanner import scan_services

if TYPE_CHECKING:
    from weathgards.scanner.models import ScanResult

log = structlog.get_logger(__name__)


@dataclass
class ScanCache:
    results: list[ScanResult] = field(default_factory=list)
    timestamp: float = 0.0
    error_count: int = 0

    @property
    def age_seconds(self) -> float:
        return time.monotonic() - self.timestamp if self.timestamp else float("inf")

    @property
    def is_empty(self) -> bool:
        return not self.results and self.timestamp == 0.0


# Module-level cache — shared across all callers within the same process
_cache = ScanCache()


async def scan_environment(
    docker_host: str | None = None,
    include_patterns: list[str] | None = None,
    *,
    force: bool = False,
    max_age: float = 30.0,
) -> list[ScanResult]:
    """Aggregate results from all sub-scanners.

    Args:
        docker_host: Optional Docker socket URI override.
        include_patterns: Extra process name patterns forwarded to process_scanner.
        force: Bypass the cache and always run a fresh scan.
        max_age: Return cached results if they are younger than this many seconds.

    Returns:
        Flat list of ScanResult across docker, process, and service scanners.
    """
    if not force and not _cache.is_empty and _cache.age_seconds < max_age:
        log.debug("orchestrator.cache_hit", age=round(_cache.age_seconds, 1))
        return _cache.results

    log.info("orchestrator.scan_start")
    t0 = time.monotonic()

    docker_task = asyncio.to_thread(scan_docker, docker_host)
    process_task = asyncio.to_thread(scan_processes, include_patterns)
    service_task = asyncio.to_thread(scan_services)

    docker_results, process_results, service_results = await asyncio.gather(
        docker_task,
        process_task,
        service_task,
        return_exceptions=False,  # individual scanners never raise — see their impls
    )

    combined: list[ScanResult] = [
        *docker_results,    # type: ignore[arg-type]
        *process_results,   # type: ignore[arg-type]
        *service_results,   # type: ignore[arg-type]
    ]

    elapsed = time.monotonic() - t0
    log.info(
        "orchestrator.scan_complete",
        total=len(combined),
        docker=len(docker_results),   # type: ignore[arg-type]
        processes=len(process_results),  # type: ignore[arg-type]
        services=len(service_results),   # type: ignore[arg-type]
        elapsed_ms=round(elapsed * 1000),
    )

    _cache.results = combined
    _cache.timestamp = time.monotonic()

    return combined


def get_cached_results() -> list[ScanResult]:
    """Return the last scan results without triggering a new scan."""
    return _cache.results


def clear_cache() -> None:
    """Invalidate the in-memory cache (useful in tests)."""
    global _cache
    _cache = ScanCache()
