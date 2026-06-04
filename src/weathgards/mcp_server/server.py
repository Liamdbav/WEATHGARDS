"""MCP server lifecycle manager.

Architecture
------------
MCPServerManager owns a single FastMCP instance backed by uvicorn, running
as a background asyncio task. Tools are loaded from the activation registry
at start() and hot-reloaded every 5 seconds when the registry changes
(tools added / removed without restarting the server).

Security guarantees (enforced in code, not configuration)
---------------------------------------------------------
1. Binding to 0.0.0.0 is refused when the token store has no token.
2. BearerAuthMiddleware is always added to the Starlette app — there is
   no mode that bypasses authentication.
3. The Docker daemon socket is never forwarded over the network.
   Only the pre-written, read-only handler functions are callable via MCP.
4. DNS-rebinding protection is disabled for network binding (0.0.0.0)
   because the remote client IP is not known at startup; our bearer token
   is the security layer instead.
"""

from __future__ import annotations

import asyncio
import re
import socket
from pathlib import Path
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import structlog
import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import TransportSecuritySettings
from pydantic import BaseModel

from weathgards.mcp_server.auth import BearerAuthMiddleware, TokenStore
from weathgards.mcp_server.tools.catalog import (
    HANDLER_MAP,
    ToolDefinition,
    get_tool,
)
from weathgards.mcp_server.tools.registry import ActivatedTool, ToolRegistry, get_registry

log = structlog.get_logger(__name__)

_STARTUP_POLL_INTERVAL = 0.05  # seconds between startup checks
_STARTUP_TIMEOUT = 3.0         # seconds before giving up on startup
_WATCH_INTERVAL = 5.0          # seconds between registry polls

HandlerFn = Callable[..., Awaitable[dict[str, Any]]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_name(s: str) -> str:
    """Normalise a string to be safe as part of an identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", s).strip("_") or "target"


def _make_bound_wrapper(
    tool_def: ToolDefinition,
    handler: HandlerFn,
    target_name: str,
) -> Callable[[], Awaitable[dict[str, Any]]]:
    """Return a zero-parameter async wrapper with the target already bound.

    The resulting function's __name__ is the MCP tool name the LLM sees.
    Parameters are intentionally omitted — the target is baked in, so the
    LLM doesn't need to (and cannot) provide it.
    """
    target_param = tool_def.target_param

    async def bound() -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if target_param:
            kwargs[target_param] = target_name
        return await handler(**kwargs)  # type: ignore[arg-type]

    mcp_name = (
        f"{tool_def.name}__{_safe_name(target_name)}"
        if target_name
        else tool_def.name
    )
    description = tool_def.description
    if target_name:
        description = f"{description}\n\nTarget: {target_name}"

    bound.__name__ = mcp_name
    bound.__doc__ = description
    return bound


def _entry_key(entry: ActivatedTool) -> tuple[str, str]:
    return (entry.tool_name, entry.target_name)


def _mcp_tool_name(tool_name: str, target_name: str) -> str:
    return f"{tool_name}__{_safe_name(target_name)}" if target_name else tool_name


def _get_local_ip() -> str | None:
    """Return the primary non-loopback IPv4 address, or None."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Public status model
# ---------------------------------------------------------------------------

class MCPStatus(BaseModel):
    running: bool
    host: str | None = None
    port: int | None = None
    tool_count: int = 0
    network_ip: str | None = None
    token_configured: bool = True
    tls_enabled: bool = False


class MCPConnectionInfo(BaseModel):
    url: str
    token: str
    snippet: dict[str, Any]
    tls_enabled: bool = False


class MCPSnippets(BaseModel):
    url: str
    token: str
    claude_desktop: dict[str, Any]
    opencode: dict[str, Any]
    curl: str


# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

@dataclass
class _ServerState:
    host: str
    port: int
    fmcp: FastMCP
    uvicorn_server: uvicorn.Server
    task: asyncio.Task[None]
    watcher_task: asyncio.Task[None]
    tool_count: int = 0
    registry_snapshot: frozenset[tuple[str, str]] = field(default_factory=frozenset)
    tls_enabled: bool = False


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class MCPServerManager:
    """Singleton that owns the MCP server lifecycle."""

    def __init__(self, token_store: TokenStore | None = None) -> None:
        self._token_store: TokenStore = token_store or TokenStore()
        self._state: _ServerState | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self, host: str, port: int) -> None:
        """Start the MCP server. Raises ValueError for invalid configuration.

        Security enforcement: binding to a non-loopback address is refused
        when the token store is empty.
        """
        if self.is_running():
            await self.stop()

        is_network = host != "127.0.0.1"

        if is_network and not self._token_store.is_configured():
            raise ValueError(
                "Cannot expose MCP server on the network without a configured token. "
                "Delete config_dir()/mcp.token and restart to auto-generate one."
            )

        from weathgards.config.settings import get_settings  # avoid circular at module level
        settings = get_settings()
        cert_path = Path(settings.tls_cert_file) if settings.tls_cert_file else None
        key_path = Path(settings.tls_key_file) if settings.tls_key_file else None
        tls_enabled = (
            cert_path is not None
            and key_path is not None
            and cert_path.exists()
            and key_path.exists()
        )
        if cert_path and key_path and not tls_enabled:
            log.warning(
                "mcp_server.tls_files_missing",
                msg="TLS configuré mais certificats introuvables",
                cert=str(cert_path),
                key=str(key_path),
            )

        registry = get_registry()
        entries = await asyncio.to_thread(registry.list_active)
        fmcp, snapshot = self._build_fmcp_with_tools(host, port, entries)

        # Wrap the Starlette transport app with bearer auth
        starlette_app = fmcp.streamable_http_app()
        starlette_app.add_middleware(
            BearerAuthMiddleware,
            token_store=self._token_store,
        )

        config = uvicorn.Config(
            starlette_app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
            **(
                {"ssl_certfile": str(cert_path), "ssl_keyfile": str(key_path)}
                if tls_enabled
                else {}
            ),
        )
        uv_server = uvicorn.Server(config)
        task: asyncio.Task[None] = asyncio.create_task(
            uv_server.serve(), name="mcp-server"
        )

        if tls_enabled:
            log.info(
                "mcp_server.tls_active",
                msg="Serveur MCP démarré en HTTPS (TLS activé)",
                cert=str(cert_path),
            )

        # Wait for uvicorn to report started
        deadline = _STARTUP_TIMEOUT / _STARTUP_POLL_INTERVAL
        for _ in range(int(deadline)):
            if uv_server.started:
                break
            await asyncio.sleep(_STARTUP_POLL_INTERVAL)
        else:
            task.cancel()
            raise RuntimeError(
                f"MCP server on {host}:{port} did not start within "
                f"{_STARTUP_TIMEOUT}s — check that the port is free."
            )

        watcher: asyncio.Task[None] = asyncio.create_task(
            self._watch_registry(fmcp, registry, snapshot),
            name="mcp-registry-watcher",
        )

        self._state = _ServerState(
            host=host,
            port=port,
            fmcp=fmcp,
            uvicorn_server=uv_server,
            task=task,
            watcher_task=watcher,
            tool_count=len(entries),
            registry_snapshot=snapshot,
            tls_enabled=tls_enabled,
        )
        log.info("mcp_server.started", host=host, port=port, tools=len(entries))

    async def stop(self) -> None:
        if self._state is None:
            return
        state = self._state
        self._state = None  # mark stopped before awaiting so status() returns false

        state.watcher_task.cancel()
        state.uvicorn_server.should_exit = True
        try:
            await asyncio.wait_for(state.task, timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            state.task.cancel()

        log.info("mcp_server.stopped")

    def is_running(self) -> bool:
        return self._state is not None and not self._state.task.done()

    def status(self) -> MCPStatus:
        if not self.is_running() or self._state is None:
            return MCPStatus(
                running=False,
                token_configured=self._token_store.is_configured(),
            )
        host = self._state.host
        return MCPStatus(
            running=True,
            host=host,
            port=self._state.port,
            tool_count=self._state.tool_count,
            network_ip=_get_local_ip() if host == "0.0.0.0" else None,
            token_configured=self._token_store.is_configured(),
            tls_enabled=self._state.tls_enabled,
        )

    def connection_info(self) -> MCPConnectionInfo | None:
        if not self.is_running() or self._state is None:
            return None
        host = self._state.host
        port = self._state.port
        tls = self._state.tls_enabled
        token = self._token_store.get_token()
        scheme = "https" if tls else "http"
        display_ip = _get_local_ip() if host == "0.0.0.0" else host
        url = f"{scheme}://{display_ip}:{port}/mcp"
        snippet: dict[str, Any] = {
            "mcpServers": {
                "weathgards": {
                    "url": url,
                    "headers": {"Authorization": f"Bearer {token}"},
                }
            }
        }
        return MCPConnectionInfo(url=url, token=token, snippet=snippet, tls_enabled=tls)

    def get_token(self) -> str:
        return self._token_store.get_token()

    def get_snippets(self) -> "MCPSnippets":
        from weathgards.config.settings import get_app_settings  # avoid circular at module level

        token = self._token_store.get_token()
        app = get_app_settings()

        tls = self._state.tls_enabled if (self.is_running() and self._state is not None) else False

        if self.is_running() and self._state is not None:
            host, port = self._state.host, self._state.port
        else:
            host, port = app.mcp_host, app.mcp_port

        display_ip = _get_local_ip() if host == "0.0.0.0" else host
        scheme = "https" if tls else "http"
        url = f"{scheme}://{display_ip}:{port}/mcp"

        return MCPSnippets(
            url=url,
            token=token,
            claude_desktop={
                "mcpServers": {
                    "weathgards": {
                        "url": url,
                        "headers": {"Authorization": f"Bearer {token}"},
                    }
                }
            },
            opencode={
                "mcp": {
                    "weathgards": {
                        "type": "remote",
                        "url": url,
                        "headers": {"Authorization": f"Bearer {token}"},
                    }
                }
            },
            curl=(
                f'curl -X POST {url} \\\n'
                f'  -H "Authorization: Bearer {token}" \\\n'
                f'  -H "Content-Type: application/json" \\\n'
                f"  -d '{{\"jsonrpc\":\"2.0\",\"method\":\"tools/list\",\"id\":1}}'"
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_fmcp_with_tools(
        self,
        host: str,
        port: int,
        entries: list[ActivatedTool],
    ) -> tuple[FastMCP, frozenset[tuple[str, str]]]:
        is_network = host != "127.0.0.1"

        # Disable DNS-rebinding protection for network binding; bearer token
        # is the security layer. For localhost keep it enabled.
        transport_security = (
            TransportSecuritySettings(
                enable_dns_rebinding_protection=False,
                allowed_hosts=[],
                allowed_origins=[],
            )
            if is_network
            else None  # use FastMCP defaults (localhost allowlist)
        )

        fmcp = FastMCP(
            "weathgards",
            host=host,
            port=port,
            transport_security=transport_security,
            log_level="WARNING",
            warn_on_duplicate_tools=False,
        )

        snapshot = self._register_entries(fmcp, entries)
        return fmcp, snapshot

    @staticmethod
    def _register_entries(
        fmcp: FastMCP,
        entries: list[ActivatedTool],
    ) -> frozenset[tuple[str, str]]:
        registered: set[tuple[str, str]] = set()
        for entry in entries:
            tool_def = get_tool(entry.tool_name)
            handler = HANDLER_MAP.get(entry.tool_name)
            if tool_def is None or handler is None:
                log.warning("mcp_server.tool_not_in_catalog", tool=entry.tool_name)
                continue
            wrapper = _make_bound_wrapper(tool_def, handler, entry.target_name)
            fmcp.add_tool(wrapper, name=wrapper.__name__, description=wrapper.__doc__ or "")
            registered.add(_entry_key(entry))
            log.debug("mcp_server.tool_registered", name=wrapper.__name__)
        return frozenset(registered)

    async def _watch_registry(
        self,
        fmcp: FastMCP,
        registry: ToolRegistry,
        initial_snapshot: frozenset[tuple[str, str]],
    ) -> None:
        current = initial_snapshot
        while True:
            try:
                await asyncio.sleep(_WATCH_INTERVAL)
                entries = await asyncio.to_thread(registry.list_active)
                new_snapshot = frozenset(_entry_key(e) for e in entries)

                if new_snapshot == current:
                    continue

                # Remove tools no longer active
                for tool_name, target_name in current - new_snapshot:
                    mcp_name = _mcp_tool_name(tool_name, target_name)
                    try:
                        fmcp.remove_tool(mcp_name)
                        log.info("mcp_server.hot_remove", name=mcp_name)
                    except Exception as exc:
                        log.warning("mcp_server.hot_remove_failed", name=mcp_name, error=str(exc))

                # Add newly activated tools
                existing_keys = {(e.tool_name, e.target_name) for e in entries}
                for entry in entries:
                    if _entry_key(entry) not in current:
                        tool_def = get_tool(entry.tool_name)
                        handler = HANDLER_MAP.get(entry.tool_name)
                        if tool_def is None or handler is None:
                            continue
                        wrapper = _make_bound_wrapper(tool_def, handler, entry.target_name)
                        fmcp.add_tool(wrapper, name=wrapper.__name__, description=wrapper.__doc__ or "")
                        log.info("mcp_server.hot_add", name=wrapper.__name__)

                current = new_snapshot
                if self._state is not None:
                    self._state.tool_count = len(entries)
                    self._state.registry_snapshot = current

            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.warning("mcp_server.watcher_error", error=str(exc))


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manager: MCPServerManager | None = None


def get_manager() -> MCPServerManager:
    global _manager
    if _manager is None:
        _manager = MCPServerManager()
    return _manager
