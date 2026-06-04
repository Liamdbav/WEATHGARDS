"""Native service scanner with full platform guard.

Each OS branch is isolated behind a try/except so a missing or broken
native tool silently degrades to an empty list — it never crashes the app.

  Linux   → systemctl list-units (subprocess, requires systemd)
  macOS   → launchctl list (subprocess, requires launchd)
  Windows → psutil.win_service_iter() (pure Python, no subprocess)
"""

from __future__ import annotations

import platform
import subprocess

import psutil
import structlog

from weathgards.scanner.models import ScanResult, ServiceMeta

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Linux — systemd
# ---------------------------------------------------------------------------

def _scan_systemd() -> list[ScanResult]:
    try:
        result = subprocess.run(
            [
                "systemctl",
                "list-units",
                "--type=service",
                "--all",
                "--no-pager",
                "--output=json",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            log.debug("systemd.non_zero_exit", stderr=result.stderr[:200])
            return []

        import json

        units: list[dict] = json.loads(result.stdout)
        out: list[ScanResult] = []
        for u in units:
            unit_name: str = u.get("unit", "unknown")
            out.append(
                ScanResult(
                    name=unit_name,
                    type="service",
                    status=u.get("active", "unknown"),
                    metadata=ServiceMeta(
                        unit=unit_name,
                        description=u.get("description", ""),
                        active_state=u.get("active", ""),
                        sub_state=u.get("sub", ""),
                        load_state=u.get("load", ""),
                    ),
                    os_origin="linux",
                )
            )
        log.info("systemd.scan_complete", count=len(out))
        return out

    except FileNotFoundError:
        log.debug("systemd.not_found", reason="systemctl binary missing")
        return []
    except subprocess.TimeoutExpired:
        log.warning("systemd.timeout")
        return []
    except Exception as exc:
        log.warning("systemd.failed", error=str(exc))
        return []


# ---------------------------------------------------------------------------
# macOS — launchd
# ---------------------------------------------------------------------------

def _scan_launchctl() -> list[ScanResult]:
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            log.debug("launchctl.non_zero_exit", stderr=result.stderr[:200])
            return []

        out: list[ScanResult] = []
        lines = result.stdout.splitlines()
        # Header line: PID  Status  Label
        for line in lines[1:]:
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            pid_str, exit_str, label = parts
            status = "running" if pid_str != "-" else "stopped"
            out.append(
                ScanResult(
                    name=label,
                    type="service",
                    status=status,
                    metadata=ServiceMeta(
                        unit=label,
                        active_state=status,
                        sub_state=exit_str,
                    ),
                    os_origin="macos",
                )
            )
        log.info("launchctl.scan_complete", count=len(out))
        return out

    except FileNotFoundError:
        log.debug("launchctl.not_found", reason="launchctl binary missing")
        return []
    except subprocess.TimeoutExpired:
        log.warning("launchctl.timeout")
        return []
    except Exception as exc:
        log.warning("launchctl.failed", error=str(exc))
        return []


# ---------------------------------------------------------------------------
# Windows — psutil.win_service_iter
# ---------------------------------------------------------------------------

def _scan_windows_services() -> list[ScanResult]:
    try:
        if not hasattr(psutil, "win_service_iter"):
            log.debug("win_services.not_available", reason="win_service_iter missing")
            return []

        out: list[ScanResult] = []
        for svc in psutil.win_service_iter():
            try:
                info = svc.as_dict()
                name: str = info.get("name", "unknown")
                status: str = info.get("status", "unknown")
                out.append(
                    ScanResult(
                        name=name,
                        type="service",
                        status=status,
                        metadata=ServiceMeta(
                            unit=name,
                            description=info.get("display_name", ""),
                            active_state=status,
                        ),
                        os_origin="windows",
                    )
                )
            except Exception as exc:
                log.warning("win_services.item_failed", error=str(exc))
                continue

        log.info("win_services.scan_complete", count=len(out))
        return out

    except Exception as exc:
        log.warning("win_services.failed", error=str(exc))
        return []


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def scan_services() -> list[ScanResult]:
    """Return native service entries for the current OS.

    Degrades gracefully to [] when the native tool is absent or fails.
    """
    match platform.system():
        case "Linux":
            return _scan_systemd()
        case "Darwin":
            return _scan_launchctl()
        case "Windows":
            return _scan_windows_services()
        case other:
            log.debug("service_scanner.unsupported_os", os=other)
            return []
