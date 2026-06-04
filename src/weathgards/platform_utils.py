"""
Cross-OS platform detection utilities.

Single source of truth for OS identity, Docker availability, and config paths.
All other modules import from here — never call platform/platformdirs directly.
"""

from __future__ import annotations

import platform
from pathlib import Path

from platformdirs import user_data_dir


def current_os() -> str:
    """Return a normalised OS identifier: 'linux', 'macos', or 'windows'.

    Raises NotImplementedError for any other platform so unsupported envs
    fail loudly rather than silently misbehaving.
    """
    match platform.system():
        case "Linux":
            return "linux"
        case "Darwin":
            return "macos"
        case "Windows":
            return "windows"
        case other:
            raise NotImplementedError(
                f"Unsupported operating system: {other!r}. "
                "WEATHGARDS supports Linux, macOS, and Windows only."
            )


def is_docker_available() -> bool:
    """Return True if the Docker daemon socket/pipe is reachable at runtime.

    Checks the default socket path for each OS. Does NOT attempt a live API
    call — purely filesystem-based so it never blocks.
    """
    match platform.system():
        case "Linux" | "Darwin":
            return Path("/var/run/docker.sock").exists()
        case "Windows":
            # Docker Desktop on Windows uses a named pipe
            return Path(r"\\.\pipe\docker_engine").exists()
        case _:
            return False


def config_dir() -> Path:
    """Return the platform-appropriate user data directory for WEATHGARDS.

    Uses platformdirs so the result respects OS conventions:
      Linux   → ~/.local/share/weathgards
      macOS   → ~/Library/Application Support/weathgards
      Windows → C:\\Users\\<user>\\AppData\\Local\\weathgards\\weathgards
    """
    path = Path(user_data_dir(appname="weathgards", appauthor=False))
    path.mkdir(parents=True, exist_ok=True)
    return path


def docker_socket_uri() -> str | None:
    """Return the Docker socket URI for the current OS, or None if unavailable.

    The docker SDK accepts a full URI (unix:// or npipe://) via the
    DOCKER_HOST env-var equivalent — this helper provides the default.
    """
    if not is_docker_available():
        return None

    match platform.system():
        case "Linux" | "Darwin":
            return "unix:///var/run/docker.sock"
        case "Windows":
            return "npipe:////./pipe/docker_engine"
        case _:
            return None
