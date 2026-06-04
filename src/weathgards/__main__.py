"""Entry point for `weathgards` console script and `python -m weathgards`."""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="weathgards",
        description="Local cross-OS MCP gateway for Docker, processes and services.",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Bind address (overrides WEATHGARDS_HOST). Default: 127.0.0.1",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="TCP port (overrides WEATHGARDS_PORT). Default: 8000",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn auto-reload (development only).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )

    args = parser.parse_args()

    # Deferred imports so --version / --help work before heavy deps load.
    import uvicorn

    from weathgards.config.settings import get_settings

    settings = get_settings()
    host = args.host or settings.host
    port = args.port or settings.port

    uvicorn.run(
        "weathgards.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=args.reload,
        log_config=None,  # structlog owns logging
    )


if __name__ == "__main__":
    sys.exit(main())  # type: ignore[func-returns-value]
