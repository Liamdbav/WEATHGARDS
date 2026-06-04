"""Integration tests for /api/catalog, /api/activate-tool, /api/tools,
/api/test-tool — all registry I/O uses a tmp_path fixture."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from weathgards.mcp_server.tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_registry(tmp_path: Path) -> ToolRegistry:
    return ToolRegistry(data_dir=tmp_path)


@pytest.fixture
def api_client(app: Any, isolated_registry: ToolRegistry) -> TestClient:
    """TestClient whose routes use an isolated tmp registry."""
    with patch(
        "weathgards.api.routes.tools.get_registry",
        return_value=isolated_registry,
    ):
        yield TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/catalog
# ---------------------------------------------------------------------------

class TestGetCatalog:
    def test_returns_list(self, api_client: TestClient) -> None:
        resp = api_client.get("/api/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 4  # 4 tools registered in catalog

    def test_each_entry_has_required_fields(self, api_client: TestClient) -> None:
        data = api_client.get("/api/catalog").json()
        for tool in data:
            assert "name" in tool
            assert "description" in tool
            assert "target_type" in tool
            assert "parameters" in tool

    def test_docker_container_status_present(self, api_client: TestClient) -> None:
        names = [t["name"] for t in api_client.get("/api/catalog").json()]
        assert "docker_container_status" in names
        assert "docker_container_logs" in names
        assert "docker_list_containers" in names
        assert "process_status" in names


# ---------------------------------------------------------------------------
# POST /api/activate-tool
# ---------------------------------------------------------------------------

class TestActivateTool:
    def test_activate_known_tool(self, api_client: TestClient) -> None:
        resp = api_client.post(
            "/api/activate-tool",
            json={"tool_name": "docker_container_status", "target_name": "nginx"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tool_name"] == "docker_container_status"
        assert data["target_name"] == "nginx"
        assert data["enabled"] is True
        assert "id" in data

    def test_activate_unknown_tool_returns_422(self, api_client: TestClient) -> None:
        resp = api_client.post(
            "/api/activate-tool",
            json={"tool_name": "nonexistent_tool", "target_name": "web"},
        )
        assert resp.status_code == 422

    def test_activate_is_idempotent(self, api_client: TestClient) -> None:
        body = {"tool_name": "process_status", "target_name": "nginx"}
        r1 = api_client.post("/api/activate-tool", json=body)
        r2 = api_client.post("/api/activate-tool", json=body)
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["id"] == r2.json()["id"]


# ---------------------------------------------------------------------------
# GET /api/tools/active
# ---------------------------------------------------------------------------

class TestListActiveTools:
    def test_empty_registry(self, api_client: TestClient) -> None:
        resp = api_client.get("/api/tools/active")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_lists_activated_tools(self, api_client: TestClient) -> None:
        api_client.post(
            "/api/activate-tool",
            json={"tool_name": "docker_container_status", "target_name": "web"},
        )
        api_client.post(
            "/api/activate-tool",
            json={"tool_name": "process_status", "target_name": "nginx"},
        )
        resp = api_client.get("/api/tools/active")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# DELETE /api/tools/{id}
# ---------------------------------------------------------------------------

class TestDeactivateTool:
    def test_deactivate_existing(self, api_client: TestClient) -> None:
        entry = api_client.post(
            "/api/activate-tool",
            json={"tool_name": "docker_container_logs", "target_name": "api"},
        ).json()

        resp = api_client.delete(f"/api/tools/{entry['id']}")
        assert resp.status_code == 204

        active_ids = [e["id"] for e in api_client.get("/api/tools/active").json()]
        assert entry["id"] not in active_ids

    def test_deactivate_nonexistent_returns_404(self, api_client: TestClient) -> None:
        resp = api_client.delete("/api/tools/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/test-tool
# ---------------------------------------------------------------------------

class TestTestTool:
    def test_unknown_tool_returns_422(self, api_client: TestClient) -> None:
        resp = api_client.post(
            "/api/test-tool",
            json={"tool_name": "ghost_tool", "target_name": "web"},
        )
        assert resp.status_code == 422

    def test_calls_handler_and_returns_result(self, api_client: TestClient) -> None:
        mock_result = {"name": "nginx", "status": "running", "image": "nginx:latest"}

        async def fake_handler(**kwargs: Any) -> dict[str, Any]:
            return mock_result

        with patch(
            "weathgards.api.routes.tools.HANDLER_MAP",
            {"docker_container_status": fake_handler},
        ):
            resp = api_client.post(
                "/api/test-tool",
                json={"tool_name": "docker_container_status", "target_name": "nginx"},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_target_name_bound_to_target_param(self, api_client: TestClient) -> None:
        received_kwargs: dict[str, Any] = {}

        async def capture_handler(**kwargs: Any) -> dict[str, Any]:
            received_kwargs.update(kwargs)
            return {"ok": True}

        with patch(
            "weathgards.api.routes.tools.HANDLER_MAP",
            {"docker_container_status": capture_handler},
        ):
            api_client.post(
                "/api/test-tool",
                json={"tool_name": "docker_container_status", "target_name": "mycontainer"},
            )

        # target_param for docker_container_status is "name"
        assert received_kwargs.get("name") == "mycontainer"

    def test_extra_params_forwarded(self, api_client: TestClient) -> None:
        received_kwargs: dict[str, Any] = {}

        async def capture_handler(**kwargs: Any) -> dict[str, Any]:
            received_kwargs.update(kwargs)
            return {"ok": True}

        with patch(
            "weathgards.api.routes.tools.HANDLER_MAP",
            {"docker_container_logs": capture_handler},
        ):
            api_client.post(
                "/api/test-tool",
                json={
                    "tool_name": "docker_container_logs",
                    "target_name": "api",
                    "params": {"lines": 100},
                },
            )

        assert received_kwargs.get("name") == "api"
        assert received_kwargs.get("lines") == 100

    def test_no_target_tool_works(self, api_client: TestClient) -> None:
        mock_result = {"containers": [], "count": 0}

        async def fake_list(**kwargs: Any) -> dict[str, Any]:
            return mock_result

        with patch(
            "weathgards.api.routes.tools.HANDLER_MAP",
            {"docker_list_containers": fake_list},
        ):
            resp = api_client.post(
                "/api/test-tool",
                json={"tool_name": "docker_list_containers"},
            )

        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_handler_exception_returns_500(self, api_client: TestClient) -> None:
        async def broken_handler(**kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("daemon gone")

        with patch(
            "weathgards.api.routes.tools.HANDLER_MAP",
            {"docker_container_status": broken_handler},
        ):
            resp = api_client.post(
                "/api/test-tool",
                json={"tool_name": "docker_container_status", "target_name": "web"},
            )

        assert resp.status_code == 500
        assert "daemon gone" in resp.json()["detail"]
