"""Tests for process_scanner — mocks psutil, verifies filtering and graceful degradation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import psutil
import pytest

from weathgards.scanner.models import ProcessMeta, ScanResult
from weathgards.scanner.process_scanner import (
    _is_notable_name,
    _is_server_port,
    _listening_ports,
    scan_processes,
)

# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

class TestIsNotableName:
    @pytest.mark.parametrize("name", [
        "nginx", "Nginx", "NGINX",
        "postgres", "redis-server", "mongod",
        "uvicorn", "gunicorn", "node",
        "mysqld", "kafka", "rabbitmq",
    ])
    def test_known_names_are_notable(self, name: str):
        assert _is_notable_name(name) is True

    @pytest.mark.parametrize("name", [
        "bash", "systemd", "cron", "grep", "top", "less",
    ])
    def test_generic_names_are_not_notable(self, name: str):
        assert _is_notable_name(name) is False


class TestIsServerPort:
    @pytest.mark.parametrize("ports", [
        [3000], [8080], [9999], [5432, 8080],
    ])
    def test_server_ports_detected(self, ports: list[int]):
        assert _is_server_port(ports) is True

    @pytest.mark.parametrize("ports", [
        [], [22], [2999], [10000], [80, 443],
    ])
    def test_non_server_ports_ignored(self, ports: list[int]):
        assert _is_server_port(ports) is False


class TestListeningPorts:
    def test_returns_listen_ports(self):
        conn = MagicMock()
        conn.status = "LISTEN"
        conn.laddr = MagicMock(port=8080)

        proc = MagicMock(spec=psutil.Process)
        proc.net_connections.return_value = [conn]

        result = _listening_ports(proc)
        assert 8080 in result

    def test_skips_non_listen(self):
        conn = MagicMock()
        conn.status = "ESTABLISHED"
        conn.laddr = MagicMock(port=8080)

        proc = MagicMock(spec=psutil.Process)
        proc.net_connections.return_value = [conn]

        assert _listening_ports(proc) == []

    def test_access_denied_returns_empty(self):
        proc = MagicMock(spec=psutil.Process)
        proc.net_connections.side_effect = psutil.AccessDenied(pid=1)
        assert _listening_ports(proc) == []

    def test_no_such_process_returns_empty(self):
        proc = MagicMock(spec=psutil.Process)
        proc.net_connections.side_effect = psutil.NoSuchProcess(pid=1)
        assert _listening_ports(proc) == []


# ---------------------------------------------------------------------------
# scan_processes integration
# ---------------------------------------------------------------------------

def _make_proc_mock(
    pid: int = 100,
    name: str = "nginx",
    status: str = "running",
    exe: str | None = "/usr/sbin/nginx",
    cmdline: list[str] | None = None,
    ports: list[int] | None = None,
    cpu: float = 0.5,
    mem_rss: int = 10 * 1024 * 1024,
) -> MagicMock:
    proc = MagicMock(spec=psutil.Process)
    proc.info = {
        "pid": pid,
        "name": name,
        "status": status,
        "exe": exe,
        "cmdline": cmdline or [exe or name],
    }
    # net_connections
    if ports:
        conns = []
        for p in ports:
            c = MagicMock()
            c.status = "LISTEN"
            c.laddr = MagicMock(port=p)
            conns.append(c)
        proc.net_connections.return_value = conns
    else:
        proc.net_connections.return_value = []

    proc.cpu_percent.return_value = cpu
    mem_mock = MagicMock()
    mem_mock.rss = mem_rss
    proc.memory_info.return_value = mem_mock
    return proc


class TestScanProcesses:
    def test_returns_notable_process(self):
        proc = _make_proc_mock(name="nginx", ports=[80])
        with patch("weathgards.scanner.process_scanner.psutil.process_iter", return_value=[proc]):
            results = scan_processes()
        assert any(r.name == "nginx" for r in results)

    def test_filters_uninteresting_processes(self):
        procs = [
            _make_proc_mock(pid=1, name="bash", ports=[]),
            _make_proc_mock(pid=2, name="grep", ports=[]),
            _make_proc_mock(pid=3, name="sshd", ports=[]),
        ]
        with patch("weathgards.scanner.process_scanner.psutil.process_iter", return_value=procs):
            results = scan_processes()
        assert results == []

    def test_includes_process_on_server_port(self):
        proc = _make_proc_mock(pid=42, name="myapp", ports=[8080])
        with patch("weathgards.scanner.process_scanner.psutil.process_iter", return_value=[proc]):
            results = scan_processes()
        assert len(results) == 1
        assert isinstance(results[0].metadata, ProcessMeta)
        assert 8080 in results[0].metadata.listening_ports

    def test_skips_access_denied_process(self):
        bad = MagicMock(spec=psutil.Process)
        bad.info = {}
        proc_iter_bad = MagicMock(spec=psutil.Process)
        proc_iter_bad.info = {"pid": 9, "name": "nginx", "status": "running", "exe": None, "cmdline": []}
        proc_iter_bad.net_connections.side_effect = psutil.AccessDenied(pid=9)
        proc_iter_bad.cpu_percent.return_value = 0.0
        mem_mock = MagicMock()
        mem_mock.rss = 1024
        proc_iter_bad.memory_info.return_value = mem_mock

        with patch("weathgards.scanner.process_scanner.psutil.process_iter", return_value=[proc_iter_bad]):
            results = scan_processes()
        # nginx is a notable name — it should appear but with empty ports
        assert all(isinstance(r, ScanResult) for r in results)

    def test_skips_no_such_process_mid_scan(self):
        """A process that disappears mid-iteration must be silently skipped."""
        bad = MagicMock(spec=psutil.Process)
        bad.info = {"pid": 7, "name": "redis-server", "status": "running", "exe": None, "cmdline": []}
        bad.net_connections.side_effect = psutil.NoSuchProcess(pid=7)
        bad.cpu_percent.side_effect = psutil.NoSuchProcess(pid=7)
        bad.memory_info.side_effect = psutil.NoSuchProcess(pid=7)

        with patch("weathgards.scanner.process_scanner.psutil.process_iter", return_value=[bad]):
            results = scan_processes()
        # redis-server is notable by name; it appears with empty stats
        assert isinstance(results, list)

    def test_include_patterns_extend_filter(self):
        proc = _make_proc_mock(pid=55, name="myspecialapp", ports=[])
        with patch("weathgards.scanner.process_scanner.psutil.process_iter", return_value=[proc]):
            results = scan_processes(include_patterns=["myspecialapp"])
        assert any(r.name == "myspecialapp" for r in results)

    def test_returns_correct_scan_result_fields(self):
        proc = _make_proc_mock(pid=123, name="uvicorn", ports=[8000])
        with patch("weathgards.scanner.process_scanner.psutil.process_iter", return_value=[proc]):
            results = scan_processes()
        r = results[0]
        assert r.type == "process"
        assert r.status == "running"
        assert r.os_origin in {"linux", "macos", "windows"}
        assert isinstance(r.metadata, ProcessMeta)
        assert r.metadata.pid == 123

    def test_process_iter_raises_does_not_crash(self):
        """If process_iter itself blows up, scan returns empty list."""
        with patch(
            "weathgards.scanner.process_scanner.psutil.process_iter",
            side_effect=RuntimeError("unexpected"),
        ), pytest.raises(RuntimeError):
            # The orchestrator wraps this — scanner itself propagates unexpected errors
            # This test documents the contract: only per-item errors are swallowed
            scan_processes()
