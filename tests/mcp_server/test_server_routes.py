"""Tests for /api/mcp/* routes — mocks MCPServerManager to avoid
starting a real uvicorn server in tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from weathgards.mcp_server.auth import TokenStore
from weathgards.mcp_server.server import (
    MCPConnectionInfo,
    MCPServerManager,
    MCPStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _stopped_status() -> MCPStatus:
    return MCPStatus(running=False, token_configured=True)


def _running_status(
    host: str = "127.0.0.1",
    port: int = 9766,
    tls_enabled: bool = False,
) -> MCPStatus:
    return MCPStatus(
        running=True,
        host=host,
        port=port,
        tool_count=2,
        network_ip="192.168.1.30" if host == "0.0.0.0" else None,
        token_configured=True,
        tls_enabled=tls_enabled,
    )


@pytest.fixture
def mock_manager() -> MagicMock:
    m = MagicMock(spec=MCPServerManager)
    m.is_running.return_value = False
    m.status.return_value = _stopped_status()
    m.start = AsyncMock()
    m.stop = AsyncMock()
    m.connection_info.return_value = None
    m.get_token.return_value = "test-token-abc"
    return m


@pytest.fixture
def api_client(app: object, mock_manager: MagicMock) -> TestClient:
    with patch("weathgards.api.routes.server.get_manager", return_value=mock_manager):
        yield TestClient(app)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# GET /api/mcp/status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_returns_stopped_when_not_running(
        self, api_client: TestClient, mock_manager: MagicMock
    ) -> None:
        resp = api_client.get("/api/mcp/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is False

    def test_returns_running_when_active(
        self, api_client: TestClient, mock_manager: MagicMock
    ) -> None:
        mock_manager.status.return_value = _running_status()
        resp = api_client.get("/api/mcp/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is True
        assert data["host"] == "127.0.0.1"
        assert data["port"] == 9766
        assert data["tool_count"] == 2
        assert data["tls_enabled"] is False

    def test_tls_enabled_reflected_in_status(
        self, api_client: TestClient, mock_manager: MagicMock
    ) -> None:
        mock_manager.status.return_value = _running_status(tls_enabled=True)
        resp = api_client.get("/api/mcp/status")
        assert resp.status_code == 200
        assert resp.json()["tls_enabled"] is True


# ---------------------------------------------------------------------------
# POST /api/mcp/start
# ---------------------------------------------------------------------------

class TestStartMCP:
    def test_start_localhost_succeeds(
        self, api_client: TestClient, mock_manager: MagicMock
    ) -> None:
        mock_manager.status.return_value = _running_status()
        resp = api_client.post("/api/mcp/start", json={"host": "127.0.0.1", "port": 9766})
        assert resp.status_code == 200
        mock_manager.start.assert_awaited_once_with("127.0.0.1", 9766)

    def test_start_when_already_running_returns_409(
        self, api_client: TestClient, mock_manager: MagicMock
    ) -> None:
        mock_manager.is_running.return_value = True
        resp = api_client.post("/api/mcp/start", json={"host": "127.0.0.1", "port": 9766})
        assert resp.status_code == 409

    def test_start_network_without_token_returns_422(
        self, api_client: TestClient, mock_manager: MagicMock
    ) -> None:
        mock_manager.start.side_effect = ValueError(
            "Cannot expose MCP server on the network without a configured token."
        )
        resp = api_client.post("/api/mcp/start", json={"host": "0.0.0.0", "port": 9766})
        assert resp.status_code == 422
        assert "token" in resp.json()["detail"].lower()

    def test_start_runtime_error_returns_503(
        self, api_client: TestClient, mock_manager: MagicMock
    ) -> None:
        mock_manager.start.side_effect = RuntimeError("port already in use")
        resp = api_client.post("/api/mcp/start", json={"host": "127.0.0.1", "port": 9766})
        assert resp.status_code == 503

    def test_start_network_with_token_calls_manager(
        self, api_client: TestClient, mock_manager: MagicMock
    ) -> None:
        mock_manager.status.return_value = _running_status("0.0.0.0")
        resp = api_client.post("/api/mcp/start", json={"host": "0.0.0.0", "port": 9766})
        assert resp.status_code == 200
        mock_manager.start.assert_awaited_once_with("0.0.0.0", 9766)


# ---------------------------------------------------------------------------
# POST /api/mcp/stop
# ---------------------------------------------------------------------------

class TestStopMCP:
    def test_stop_running_server(
        self, api_client: TestClient, mock_manager: MagicMock
    ) -> None:
        mock_manager.is_running.return_value = True
        resp = api_client.post("/api/mcp/stop")
        assert resp.status_code == 200
        mock_manager.stop.assert_awaited_once()

    def test_stop_when_not_running_returns_409(
        self, api_client: TestClient, mock_manager: MagicMock
    ) -> None:
        mock_manager.is_running.return_value = False
        resp = api_client.post("/api/mcp/stop")
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# GET /api/mcp/connection-info
# ---------------------------------------------------------------------------

class TestConnectionInfo:
    def test_returns_409_when_not_running(
        self, api_client: TestClient, mock_manager: MagicMock
    ) -> None:
        mock_manager.connection_info.return_value = None
        resp = api_client.get("/api/mcp/connection-info")
        assert resp.status_code == 409

    def test_returns_url_token_snippet_when_running(
        self, api_client: TestClient, mock_manager: MagicMock
    ) -> None:
        mock_manager.connection_info.return_value = MCPConnectionInfo(
            url="http://192.168.1.30:9766/mcp",
            token="secret-token",
            snippet={
                "mcpServers": {
                    "weathgards": {
                        "url": "http://192.168.1.30:9766/mcp",
                        "headers": {"Authorization": "Bearer secret-token"},
                    }
                }
            },
        )
        resp = api_client.get("/api/mcp/connection-info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] == "http://192.168.1.30:9766/mcp"
        assert data["token"] == "secret-token"
        assert "mcpServers" in data["snippet"]
        assert "weathgards" in data["snippet"]["mcpServers"]


# ---------------------------------------------------------------------------
# MCPServerManager unit tests (no FastAPI)
# ---------------------------------------------------------------------------

class TestMCPServerManagerSecurity:
    @pytest.mark.asyncio
    async def test_start_network_without_token_raises(self, tmp_path: Path) -> None:
        """Binding 0.0.0.0 with an empty token store must raise ValueError."""
        # Create a token store that has no token
        store = TokenStore.__new__(TokenStore)
        store._token = ""  # bypass normal init — simulate empty token
        store._path = tmp_path / "mcp.token"

        manager = MCPServerManager(token_store=store)
        with pytest.raises(ValueError, match="token"):
            await manager.start("0.0.0.0", 19999)

    def test_is_running_false_initially(self, tmp_path: Path) -> None:
        store = TokenStore(data_dir=tmp_path)
        manager = MCPServerManager(token_store=store)
        assert manager.is_running() is False

    def test_status_reflects_not_running(self, tmp_path: Path) -> None:
        store = TokenStore(data_dir=tmp_path)
        manager = MCPServerManager(token_store=store)
        status = manager.status()
        assert status.running is False
        assert status.host is None
        assert status.tool_count == 0

    def test_connection_info_none_when_stopped(self, tmp_path: Path) -> None:
        store = TokenStore(data_dir=tmp_path)
        manager = MCPServerManager(token_store=store)
        assert manager.connection_info() is None


class TestMCPServerManagerToolLoading:
    """Verify that activated registry entries are wired to the FastMCP instance."""

    @pytest.mark.asyncio
    async def test_activated_tools_registered_on_start(self, tmp_path: Path) -> None:
        from weathgards.mcp_server.tools.registry import ActivatedTool, ToolRegistry

        registry = ToolRegistry(data_dir=tmp_path)
        entry = registry.register("docker_container_status", "nginx")

        store = TokenStore(data_dir=tmp_path)
        manager = MCPServerManager(token_store=store)

        # Build fmcp without starting uvicorn (test internal helper directly)
        entries = registry.list_active()
        fmcp, snapshot = manager._build_fmcp_with_tools("127.0.0.1", 19998, entries)

        tool_names = [t.name for t in fmcp._tool_manager.list_tools()]
        assert any("docker_container_status" in n and "nginx" in n for n in tool_names)
        assert ("docker_container_status", "nginx") in snapshot

    @pytest.mark.asyncio
    async def test_unknown_catalog_entry_skipped_gracefully(self, tmp_path: Path) -> None:
        from weathgards.mcp_server.tools.registry import ToolRegistry

        registry = ToolRegistry(data_dir=tmp_path)
        # Register a tool name that doesn't exist in the catalog
        registry.register("nonexistent_tool", "target")

        store = TokenStore(data_dir=tmp_path)
        manager = MCPServerManager(token_store=store)

        entries = registry.list_active()
        # Should not raise
        fmcp, snapshot = manager._build_fmcp_with_tools("127.0.0.1", 19997, entries)
        tool_names = [t.name for t in fmcp._tool_manager.list_tools()]
        assert not any("nonexistent_tool" in n for n in tool_names)
