"""Tests for the scanner orchestrator — verifies aggregation and caching."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from weathgards.scanner.models import DockerMeta, ProcessMeta, ScanResult, ServiceMeta
from weathgards.scanner.orchestrator import (
    ScanCache,
    clear_cache,
    get_cached_results,
    scan_environment,
)


def _make_result(name: str, kind: str) -> ScanResult:
    meta: DockerMeta | ProcessMeta | ServiceMeta
    if kind == "docker":
        meta = DockerMeta(image="test:latest")
    elif kind == "process":
        meta = ProcessMeta(pid=1)
    else:
        meta = ServiceMeta(unit=name)
    return ScanResult(name=name, type=kind, status="ok", metadata=meta, os_origin="linux")  # type: ignore[arg-type]


DOCKER_RESULT = _make_result("api", "docker")
PROCESS_RESULT = _make_result("uvicorn", "process")
SERVICE_RESULT = _make_result("nginx.service", "service")


@pytest.fixture(autouse=True)
def reset_cache():
    """Ensure cache is clean before every test."""
    clear_cache()
    yield
    clear_cache()


class TestScanEnvironment:
    @pytest.mark.asyncio
    async def test_aggregates_all_scanners(self):
        with (
            patch("weathgards.scanner.orchestrator.scan_docker", return_value=[DOCKER_RESULT]),
            patch("weathgards.scanner.orchestrator.scan_processes", return_value=[PROCESS_RESULT]),
            patch("weathgards.scanner.orchestrator.scan_services", return_value=[SERVICE_RESULT]),
        ):
            results = await scan_environment(force=True)

        assert len(results) == 3
        types = {r.type for r in results}
        assert types == {"docker", "process", "service"}

    @pytest.mark.asyncio
    async def test_empty_scanners_return_empty_list(self):
        with (
            patch("weathgards.scanner.orchestrator.scan_docker", return_value=[]),
            patch("weathgards.scanner.orchestrator.scan_processes", return_value=[]),
            patch("weathgards.scanner.orchestrator.scan_services", return_value=[]),
        ):
            results = await scan_environment(force=True)
        assert results == []

    @pytest.mark.asyncio
    async def test_cache_is_populated_after_scan(self):
        with (
            patch("weathgards.scanner.orchestrator.scan_docker", return_value=[DOCKER_RESULT]),
            patch("weathgards.scanner.orchestrator.scan_processes", return_value=[]),
            patch("weathgards.scanner.orchestrator.scan_services", return_value=[]),
        ):
            await scan_environment(force=True)

        cached = get_cached_results()
        assert len(cached) == 1
        assert cached[0].name == "api"

    @pytest.mark.asyncio
    async def test_cache_hit_skips_scanners(self):
        # Prime the cache
        with (
            patch("weathgards.scanner.orchestrator.scan_docker", return_value=[DOCKER_RESULT]) as mock_d,
            patch("weathgards.scanner.orchestrator.scan_processes", return_value=[]) as mock_p,
            patch("weathgards.scanner.orchestrator.scan_services", return_value=[]) as mock_s,
        ):
            await scan_environment(force=True)
            mock_d.reset_mock()
            mock_p.reset_mock()
            mock_s.reset_mock()

            # Second call within max_age — scanners should NOT be called
            await scan_environment(max_age=60.0)
            mock_d.assert_not_called()
            mock_p.assert_not_called()
            mock_s.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_bypasses_cache(self):
        with (
            patch("weathgards.scanner.orchestrator.scan_docker", return_value=[DOCKER_RESULT]) as mock_d,
            patch("weathgards.scanner.orchestrator.scan_processes", return_value=[]),
            patch("weathgards.scanner.orchestrator.scan_services", return_value=[]),
        ):
            await scan_environment(force=True)
            await scan_environment(force=True)
            assert mock_d.call_count == 2

    @pytest.mark.asyncio
    async def test_expired_cache_triggers_new_scan(self):
        with (
            patch("weathgards.scanner.orchestrator.scan_docker", return_value=[DOCKER_RESULT]) as mock_d,
            patch("weathgards.scanner.orchestrator.scan_processes", return_value=[]),
            patch("weathgards.scanner.orchestrator.scan_services", return_value=[]),
        ):
            await scan_environment(force=True)
            # Make cache appear old
            from weathgards.scanner import orchestrator
            orchestrator._cache.timestamp -= 100.0
            await scan_environment(max_age=30.0)
            assert mock_d.call_count == 2


class TestScanCache:
    def test_is_empty_initially(self):
        cache = ScanCache()
        assert cache.is_empty is True

    def test_not_empty_after_population(self):
        cache = ScanCache()
        cache.results = [DOCKER_RESULT]
        cache.timestamp = 1.0
        assert cache.is_empty is False

    def test_age_infinite_when_never_scanned(self):
        cache = ScanCache()
        assert cache.age_seconds == float("inf")


class TestGetCachedResults:
    def test_returns_empty_list_initially(self):
        assert get_cached_results() == []

    @pytest.mark.asyncio
    async def test_returns_last_scan(self):
        with (
            patch("weathgards.scanner.orchestrator.scan_docker", return_value=[DOCKER_RESULT]),
            patch("weathgards.scanner.orchestrator.scan_processes", return_value=[PROCESS_RESULT]),
            patch("weathgards.scanner.orchestrator.scan_services", return_value=[]),
        ):
            await scan_environment(force=True)

        cached = get_cached_results()
        assert len(cached) == 2


class TestClearCache:
    @pytest.mark.asyncio
    async def test_clears_results(self):
        with (
            patch("weathgards.scanner.orchestrator.scan_docker", return_value=[DOCKER_RESULT]),
            patch("weathgards.scanner.orchestrator.scan_processes", return_value=[]),
            patch("weathgards.scanner.orchestrator.scan_services", return_value=[]),
        ):
            await scan_environment(force=True)

        clear_cache()
        assert get_cached_results() == []
