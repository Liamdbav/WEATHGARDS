"""Tests for service_scanner — verifies each platform branch and graceful degradation."""

from __future__ import annotations

import json
import platform
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from weathgards.scanner.models import ScanResult, ServiceMeta
from weathgards.scanner.service_scanner import (
    _scan_launchctl,
    _scan_systemd,
    _scan_windows_services,
    scan_services,
)

# ---------------------------------------------------------------------------
# Linux — systemd
# ---------------------------------------------------------------------------

_SYSTEMD_JSON = json.dumps([
    {"unit": "nginx.service", "load": "loaded", "active": "active", "sub": "running", "description": "A high performance web server"},
    {"unit": "sshd.service", "load": "loaded", "active": "active", "sub": "running", "description": "OpenSSH server"},
    {"unit": "bluetooth.service", "load": "not-found", "active": "inactive", "sub": "dead", "description": ""},
])


class TestScanSystemd:
    def test_parses_systemctl_output(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = _SYSTEMD_JSON

        with patch("subprocess.run", return_value=mock_result):
            results = _scan_systemd()

        assert len(results) == 3
        names = {r.name for r in results}
        assert "nginx.service" in names
        assert "sshd.service" in names

    def test_returns_correct_types(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = _SYSTEMD_JSON

        with patch("subprocess.run", return_value=mock_result):
            results = _scan_systemd()

        for r in results:
            assert r.type == "service"
            assert r.os_origin == "linux"
            assert isinstance(r.metadata, ServiceMeta)

    def test_returns_empty_on_nonzero_exit(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Failed to connect to bus"

        with patch("subprocess.run", return_value=mock_result):
            results = _scan_systemd()
        assert results == []

    def test_returns_empty_when_systemctl_missing(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            results = _scan_systemd()
        assert results == []

    def test_returns_empty_on_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="systemctl", timeout=10)):
            results = _scan_systemd()
        assert results == []

    def test_returns_empty_on_bad_json(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json at all"

        with patch("subprocess.run", return_value=mock_result):
            results = _scan_systemd()
        assert results == []


# ---------------------------------------------------------------------------
# macOS — launchctl
# ---------------------------------------------------------------------------

_LAUNCHCTL_OUTPUT = """\
PID\tStatus\tLabel
1234\t0\tcom.apple.notifyd
-\t0\tcom.apple.spindump
5678\t0\tcom.example.myapp
"""


class TestScanLaunchctl:
    def test_parses_launchctl_output(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = _LAUNCHCTL_OUTPUT

        with patch("subprocess.run", return_value=mock_result):
            results = _scan_launchctl()

        labels = {r.name for r in results}
        assert "com.apple.notifyd" in labels
        assert "com.example.myapp" in labels

    def test_running_status(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = _LAUNCHCTL_OUTPUT

        with patch("subprocess.run", return_value=mock_result):
            results = _scan_launchctl()

        running = {r.name: r.status for r in results}
        assert running["com.apple.notifyd"] == "running"
        assert running["com.apple.spindump"] == "stopped"

    def test_returns_empty_when_launchctl_missing(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            results = _scan_launchctl()
        assert results == []

    def test_returns_empty_on_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("launchctl", 10)):
            results = _scan_launchctl()
        assert results == []

    def test_returns_empty_on_nonzero_exit(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            results = _scan_launchctl()
        assert results == []


# ---------------------------------------------------------------------------
# Windows — psutil.win_service_iter
# ---------------------------------------------------------------------------

class TestScanWindowsServices:
    def _make_svc(self, name: str, status: str, display: str = "") -> MagicMock:
        svc = MagicMock()
        svc.as_dict.return_value = {
            "name": name,
            "status": status,
            "display_name": display,
        }
        return svc

    def test_returns_services(self):
        svcs = [
            self._make_svc("wuauserv", "running", "Windows Update"),
            self._make_svc("spooler", "stopped", "Print Spooler"),
        ]
        mock_psutil = MagicMock(spec=["win_service_iter"])
        mock_psutil.win_service_iter.return_value = iter(svcs)

        with patch("weathgards.scanner.service_scanner.psutil", mock_psutil):
            results = _scan_windows_services()

        assert len(results) == 2
        names = {r.name for r in results}
        assert "wuauserv" in names
        assert "spooler" in names

    def test_returns_empty_when_win_service_iter_absent(self):
        # Simulate a psutil build that has no win_service_iter (non-Windows)
        mock_psutil = MagicMock(spec=[])  # no attributes at all

        with patch("weathgards.scanner.service_scanner.psutil", mock_psutil):
            results = _scan_windows_services()

        assert results == []

    def test_skips_broken_service_entry(self):
        good = self._make_svc("ok", "running")
        bad = MagicMock()
        bad.as_dict.side_effect = RuntimeError("access denied")

        import psutil as real_psutil

        if not hasattr(real_psutil, "win_service_iter"):
            pytest.skip("Not on Windows — win_service_iter unavailable")

        with patch.object(real_psutil, "win_service_iter", return_value=iter([good, bad])):
            results = _scan_windows_services()
        assert all(isinstance(r, ScanResult) for r in results)


# ---------------------------------------------------------------------------
# scan_services dispatcher
# ---------------------------------------------------------------------------

class TestScanServices:
    def test_linux_dispatches_to_systemd(self):
        with (
            patch.object(platform, "system", return_value="Linux"),
            patch("weathgards.scanner.service_scanner._scan_systemd", return_value=[]) as mock_fn,
        ):
            scan_services()
            mock_fn.assert_called_once()

    def test_macos_dispatches_to_launchctl(self):
        with (
            patch.object(platform, "system", return_value="Darwin"),
            patch("weathgards.scanner.service_scanner._scan_launchctl", return_value=[]) as mock_fn,
        ):
            scan_services()
            mock_fn.assert_called_once()

    def test_windows_dispatches_to_win_services(self):
        with (
            patch.object(platform, "system", return_value="Windows"),
            patch("weathgards.scanner.service_scanner._scan_windows_services", return_value=[]) as mock_fn,
        ):
            scan_services()
            mock_fn.assert_called_once()

    def test_unknown_os_returns_empty(self):
        with patch.object(platform, "system", return_value="FreeBSD"):
            results = scan_services()
        assert results == []
