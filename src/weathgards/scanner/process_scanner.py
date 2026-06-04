"""Process scanner using psutil — truly cross-OS.

Identifies "notable" processes: network servers bound to ports 3000-9999,
known database engines, and common dev tools. Skips silently on
AccessDenied / NoSuchProcess to survive restrictive environments.
"""

from __future__ import annotations

import re

import psutil
import structlog

from weathgards.platform_utils import current_os
from weathgards.scanner.models import ProcessMeta, ScanResult

log = structlog.get_logger(__name__)

# Port range considered "interesting" for generic server processes
_SERVER_PORT_LOW = 3000
_SERVER_PORT_HIGH = 9999

# Process name substrings that are always notable regardless of port
_NOTABLE_NAMES: frozenset[str] = frozenset(
    [
        # Databases
        "postgres",
        "mysqld",
        "redis-server",
        "mongod",
        "mariadb",
        "cassandra",
        "elasticsearch",
        "couchdb",
        "influxd",
        # Message brokers
        "kafka",
        "rabbitmq",
        "nats-server",
        # Dev / web servers
        "nginx",
        "apache2",
        "httpd",
        "caddy",
        "traefik",
        "node",
        "bun",
        "deno",
        "uvicorn",
        "gunicorn",
        "hypercorn",
        "puma",
        "unicorn",
        "rails",
        # Runtimes / interpreters that are likely serving something
        "python",
        "ruby",
        "java",
        "dotnet",
        "php-fpm",
    ]
)

_NOTABLE_RE = re.compile(
    "|".join(re.escape(n) for n in sorted(_NOTABLE_NAMES, key=len, reverse=True)),
    re.IGNORECASE,
)


def _is_notable_name(name: str) -> bool:
    return bool(_NOTABLE_RE.search(name))


def _listening_ports(proc: psutil.Process) -> list[int]:
    """Return sorted list of TCP/UDP ports the process listens on."""
    try:
        conns = proc.net_connections(kind="inet")
        return sorted(
            {
                c.laddr.port
                for c in conns
                if c.status in ("LISTEN", "NONE")  # NONE covers UDP
                and c.laddr
            }
        )
    except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
        return []


def _is_server_port(ports: list[int]) -> bool:
    return any(_SERVER_PORT_LOW <= p <= _SERVER_PORT_HIGH for p in ports)


def scan_processes(include_patterns: list[str] | None = None) -> list[ScanResult]:
    """Scan running processes and return notable ones as ScanResult objects.

    Args:
        include_patterns: Optional list of name substrings that always pass
                          the filter (in addition to the built-in set).

    Skips any process that raises AccessDenied or NoSuchProcess.
    Never raises.
    """
    os_id = current_os()
    extra_re: re.Pattern[str] | None = None
    if include_patterns:
        extra_re = re.compile(
            "|".join(re.escape(p) for p in include_patterns), re.IGNORECASE
        )

    results: list[ScanResult] = []

    for proc in psutil.process_iter(["pid", "name", "status", "exe", "cmdline"]):
        try:
            info = proc.info
            name: str = info.get("name") or ""
            pid: int = info.get("pid") or 0
            status: str = info.get("status") or "unknown"
            exe: str | None = info.get("exe")
            cmdline: list[str] = info.get("cmdline") or []

            ports = _listening_ports(proc)
            is_notable = (
                _is_notable_name(name)
                or _is_server_port(ports)
                or (extra_re is not None and extra_re.search(name))
            )

            if not is_notable:
                continue

            # Collect resource stats — best-effort, may be None
            cpu: float | None = None
            mem: float | None = None
            try:
                cpu = proc.cpu_percent(interval=None)
                mi = proc.memory_info()
                mem = round(mi.rss / (1024 * 1024), 2)
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass

            results.append(
                ScanResult(
                    name=name,
                    type="process",
                    status=status,
                    metadata=ProcessMeta(
                        pid=pid,
                        listening_ports=ports,
                        cpu_percent=cpu,
                        mem_rss_mb=mem,
                        exe=exe,
                        cmdline=cmdline[:8],  # cap length for serialisation
                    ),
                    os_origin=os_id,
                )
            )

        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
        except Exception as exc:
            log.warning("process.parse_failed", error=str(exc))
            continue

    log.info("process.scan_complete", count=len(results))
    return results
