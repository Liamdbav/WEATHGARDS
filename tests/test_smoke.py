"""Smoke tests — basic API contracts that must pass regardless of Docker presence."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from weathgards.api.app import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health_returns_ok(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


def test_health_reports_os(client: TestClient) -> None:
    r = client.get("/api/health")
    data = r.json()
    assert isinstance(data["os"], str)
    assert data["os"] in {"linux", "macos", "windows"}


def test_health_reports_docker_flag(client: TestClient) -> None:
    r = client.get("/api/health")
    data = r.json()
    # docker_available must be a boolean — true or false, doesn't matter
    assert isinstance(data["docker_available"], bool)


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

def test_scan_returns_list(client: TestClient) -> None:
    r = client.get("/api/scan")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_scan_items_have_expected_fields(client: TestClient) -> None:
    r = client.get("/api/scan")
    for item in r.json():
        assert "id" in item
        assert "name" in item
        assert "type" in item
        assert item["type"] in {"docker", "process", "service"}


# ---------------------------------------------------------------------------
# MCP connection-info (starts and stops the server within the test)
# ---------------------------------------------------------------------------

_TEST_MCP_PORT = 19_766  # high port — unlikely to conflict


def test_connection_info_returns_valid_json(client: TestClient) -> None:
    # Ensure server is stopped first (idempotent)
    client.post("/api/mcp/stop")

    start = client.post(
        "/api/mcp/start",
        json={"host": "127.0.0.1", "port": _TEST_MCP_PORT},
    )
    if start.status_code == 503:
        pytest.skip(f"MCP server could not bind on port {_TEST_MCP_PORT} — skipped")

    assert start.status_code == 200, start.text

    try:
        info = client.get("/api/mcp/connection-info")
        assert info.status_code == 200, info.text
        data = info.json()

        assert "url" in data
        assert "token" in data
        assert "snippet" in data

        assert isinstance(data["url"], str) and data["url"].startswith("http")
        assert isinstance(data["token"], str) and len(data["token"]) > 0
        assert isinstance(data["snippet"], dict)
    finally:
        client.post("/api/mcp/stop")
