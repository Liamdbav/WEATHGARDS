"""Tests for docker_tools handlers — mocks the docker SDK, never touches a daemon."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from weathgards.mcp_server.tools.docker_tools import (
    docker_container_logs,
    docker_container_status,
    docker_list_containers,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_client(containers: list[MagicMock] | None = None) -> MagicMock:
    client = MagicMock()
    client.containers.list.return_value = containers or []
    return client


def _make_container_mock(
    name: str = "web",
    status: str = "running",
    image: str = "nginx:latest",
    exit_code: int = 0,
    started_at: str = "2024-01-01T00:00:00Z",
    health_status: str | None = None,
) -> MagicMock:
    c = MagicMock()
    c.name = name
    c.short_id = name[:12]
    state: dict = {
        "Status": status,
        "ExitCode": exit_code,
        "StartedAt": started_at,
        "FinishedAt": "0001-01-01T00:00:00Z",
    }
    if health_status:
        state["Health"] = {"Status": health_status}
    c.attrs = {
        "State": state,
        "Config": {"Image": image},
    }
    return c


# ---------------------------------------------------------------------------
# docker_container_status
# ---------------------------------------------------------------------------

class TestDockerContainerStatus:
    @pytest.mark.asyncio
    async def test_docker_unavailable_returns_error(self) -> None:
        # is_docker_available is a module-level import in docker_tools
        with patch(
            "weathgards.mcp_server.tools.docker_tools.is_docker_available",
            return_value=False,
        ):
            result = await docker_container_status("nginx")
        assert "error" in result
        assert "not reachable" in result["error"]

    @pytest.mark.asyncio
    async def test_container_not_found_returns_error(self) -> None:
        import docker as real_docker

        mock_client = MagicMock()
        mock_client.containers.get.side_effect = real_docker.errors.NotFound("nginx")

        # _build_client is fully replaced — no need to also patch is_docker_available
        with patch(
            "weathgards.mcp_server.tools.docker_tools._build_client",
            return_value=mock_client,
        ):
            result = await docker_container_status("nginx")

        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_running_container_returns_fields(self) -> None:
        container = _make_container_mock(
            name="api",
            status="running",
            image="myapp:1.0",
            health_status="healthy",
        )
        mock_client = MagicMock()
        mock_client.containers.get.return_value = container

        with patch(
            "weathgards.mcp_server.tools.docker_tools._build_client",
            return_value=mock_client,
        ):
            result = await docker_container_status("api")

        assert result["name"] == "api"
        assert result["status"] == "running"
        assert result["image"] == "myapp:1.0"
        assert result["health"] == "healthy"
        assert result["exit_code"] == 0
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_api_error_returns_error_dict(self) -> None:
        import docker as real_docker

        mock_client = MagicMock()
        mock_client.containers.get.side_effect = real_docker.errors.APIError("boom")

        with patch(
            "weathgards.mcp_server.tools.docker_tools._build_client",
            return_value=mock_client,
        ):
            result = await docker_container_status("broken")

        assert "error" in result
        assert "Docker API error" in result["error"]


# ---------------------------------------------------------------------------
# docker_container_logs
# ---------------------------------------------------------------------------

class TestDockerContainerLogs:
    @pytest.mark.asyncio
    async def test_returns_log_lines(self) -> None:
        raw_logs = b"2024-01-01T00:00:00Z line1\n2024-01-01T00:00:01Z line2\n"
        container = MagicMock()
        container.logs.return_value = raw_logs
        mock_client = MagicMock()
        mock_client.containers.get.return_value = container

        with patch(
            "weathgards.mcp_server.tools.docker_tools._build_client",
            return_value=mock_client,
        ):
            result = await docker_container_logs("nginx", lines=10)

        assert result["name"] == "nginx"
        assert result["count"] == 2
        assert isinstance(result["lines"], list)
        container.logs.assert_called_once_with(tail=10, timestamps=True, stream=False)

    @pytest.mark.asyncio
    async def test_not_found_returns_error(self) -> None:
        import docker as real_docker

        mock_client = MagicMock()
        mock_client.containers.get.side_effect = real_docker.errors.NotFound("gone")

        with patch(
            "weathgards.mcp_server.tools.docker_tools._build_client",
            return_value=mock_client,
        ):
            result = await docker_container_logs("gone")

        assert "error" in result


# ---------------------------------------------------------------------------
# docker_list_containers
# ---------------------------------------------------------------------------

class TestDockerListContainers:
    @pytest.mark.asyncio
    async def test_returns_all_containers(self) -> None:
        containers = [
            _make_container_mock("web", "running", "nginx:latest"),
            _make_container_mock("db", "exited", "postgres:15"),
        ]
        mock_client = _make_mock_client(containers)

        with patch(
            "weathgards.mcp_server.tools.docker_tools._build_client",
            return_value=mock_client,
        ):
            result = await docker_list_containers()

        assert result["count"] == 2
        names = [c["name"] for c in result["containers"]]  # type: ignore[index]
        assert "web" in names
        assert "db" in names

    @pytest.mark.asyncio
    async def test_empty_daemon_returns_zero_count(self) -> None:
        mock_client = _make_mock_client([])

        with patch(
            "weathgards.mcp_server.tools.docker_tools._build_client",
            return_value=mock_client,
        ):
            result = await docker_list_containers()

        assert result["count"] == 0
        assert result["containers"] == []

    @pytest.mark.asyncio
    async def test_docker_unavailable_returns_error(self) -> None:
        with patch(
            "weathgards.mcp_server.tools.docker_tools.is_docker_available",
            return_value=False,
        ):
            result = await docker_list_containers()

        assert "error" in result
