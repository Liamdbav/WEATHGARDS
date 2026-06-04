"""Static process tool handlers using psutil — truly cross-OS.

READ-ONLY: only inspects process state, never sends signals or modifies
process attributes.
"""

from __future__ import annotations

import asyncio
from typing import Any

import psutil
import structlog

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _listening_ports(proc: psutil.Process) -> list[int]:
    try:
        conns = proc.net_connections(kind="inet")
        return sorted(
            {
                c.laddr.port
                for c in conns
                if c.status in ("LISTEN", "NONE") and c.laddr
            }
        )
    except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
        return []


def _process_status_sync(name_or_pid: str) -> dict[str, Any]:
    proc: psutil.Process | None = None

    # Attempt to interpret as PID first.
    try:
        pid = int(name_or_pid)
        try:
            proc = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return {"error": f"No process with PID {pid}"}
    except ValueError:
        # Not a number — search by name substring (case-insensitive, first match).
        needle = name_or_pid.lower()
        for p in psutil.process_iter(["pid", "name"]):
            try:
                pname: str = (p.info.get("name") or "").lower()  # type: ignore[union-attr]
                if needle in pname:
                    proc = p
                    break
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue

    if proc is None:
        return {"error": f"No process matching '{name_or_pid}'"}

    try:
        with proc.oneshot():
            exe: str | None = None
            try:
                exe = proc.exe() or None
            except (psutil.AccessDenied, psutil.ZombieProcess):
                pass

            cpu: float | None = None
            mem: float | None = None
            try:
                cpu = proc.cpu_percent(interval=None)
                mi = proc.memory_info()
                mem = round(mi.rss / (1024 * 1024), 2)
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass

            return {
                "name": proc.name(),
                "pid": proc.pid,
                "status": proc.status(),
                "cpu_percent": cpu,
                "mem_rss_mb": mem,
                "listening_ports": _listening_ports(proc),
                "exe": exe,
            }
    except psutil.NoSuchProcess:
        return {"error": f"Process '{name_or_pid}' disappeared during inspection"}
    except psutil.AccessDenied as exc:
        log.warning("process_tools.access_denied", name_or_pid=name_or_pid, error=str(exc))
        return {"error": f"Access denied: {exc}"}


# ---------------------------------------------------------------------------
# Public async handler
# ---------------------------------------------------------------------------

async def process_status(name_or_pid: str) -> dict[str, Any]:
    """Return CPU, memory, status, and listening ports for a process.

    Args:
        name_or_pid: A numeric PID string ("1234") or a name substring
                     ("nginx"). On name match the first found process wins.
    """
    return await asyncio.to_thread(_process_status_sync, name_or_pid)
