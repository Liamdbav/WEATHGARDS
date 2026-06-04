"""Tests for process_tools — mocks psutil, never inspects real processes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import psutil
import pytest

from weathgards.mcp_server.tools.process_tools import process_status


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proc_mock(
    name: str = "nginx",
    pid: int = 1234,
    status: str = "running",
    cpu: float = 0.5,
    mem_rss: int = 32 * 1024 * 1024,
    exe: str = "/usr/sbin/nginx",
    ports: list[int] | None = None,
) -> MagicMock:
    proc = MagicMock(spec=psutil.Process)
    proc.pid = pid
    proc.name.return_value = name
    proc.status.return_value = status
    proc.cpu_percent.return_value = cpu
    proc.exe.return_value = exe

    mem = MagicMock()
    mem.rss = mem_rss
    proc.memory_info.return_value = mem

    # Simulate oneshot context manager
    proc.oneshot.return_value.__enter__ = lambda s: s
    proc.oneshot.return_value.__exit__ = MagicMock(return_value=False)

    # net_connections for _listening_ports
    if ports:
        conns = []
        for p in ports:
            c = MagicMock()
            c.laddr = MagicMock()
            c.laddr.port = p
            c.status = "LISTEN"
            conns.append(c)
        proc.net_connections.return_value = conns
    else:
        proc.net_connections.return_value = []

    # process_iter info dict
    proc.info = {"pid": pid, "name": name}

    return proc


# ---------------------------------------------------------------------------
# process_status
# ---------------------------------------------------------------------------

class TestProcessStatus:
    @pytest.mark.asyncio
    async def test_lookup_by_pid_success(self) -> None:
        mock_proc = _make_proc_mock(name="nginx", pid=1234, ports=[80, 443])

        with patch("psutil.Process", return_value=mock_proc):
            result = await process_status("1234")

        assert result["name"] == "nginx"
        assert result["pid"] == 1234
        assert result["status"] == "running"
        assert result["listening_ports"] == [80, 443]
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_lookup_by_pid_not_found(self) -> None:
        with patch("psutil.Process", side_effect=psutil.NoSuchProcess(pid=9999)):
            result = await process_status("9999")

        assert "error" in result
        assert "9999" in result["error"]

    @pytest.mark.asyncio
    async def test_lookup_by_name_found(self) -> None:
        mock_proc = _make_proc_mock(name="nginx", pid=555)
        mock_proc.info = {"pid": 555, "name": "nginx"}

        with patch(
            "psutil.process_iter",
            return_value=[mock_proc],
        ):
            result = await process_status("nginx")

        assert result["name"] == "nginx"
        assert result["pid"] == 555
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_lookup_by_name_not_found(self) -> None:
        with patch("psutil.process_iter", return_value=[]):
            result = await process_status("nonexistent_service_xyz")

        assert "error" in result
        assert "nonexistent_service_xyz" in result["error"]

    @pytest.mark.asyncio
    async def test_name_search_is_case_insensitive(self) -> None:
        mock_proc = _make_proc_mock(name="Nginx", pid=42)
        mock_proc.info = {"pid": 42, "name": "Nginx"}

        with patch("psutil.process_iter", return_value=[mock_proc]):
            result = await process_status("NGINX")

        assert result["name"] == "Nginx"
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_access_denied_returns_error(self) -> None:
        # Simulate AccessDenied on the first call inside the oneshot block.
        # proc.name() is the first method called after entering the context.
        mock_proc = _make_proc_mock()
        mock_proc.name.side_effect = psutil.AccessDenied(pid=1)

        with patch("psutil.Process", return_value=mock_proc):
            result = await process_status("1")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_returns_cpu_and_memory(self) -> None:
        mock_proc = _make_proc_mock(cpu=2.5, mem_rss=64 * 1024 * 1024)

        with patch("psutil.Process", return_value=mock_proc):
            result = await process_status("1234")

        assert result["cpu_percent"] == 2.5
        assert result["mem_rss_mb"] == 64.0
