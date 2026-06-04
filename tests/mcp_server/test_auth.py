"""Tests for auth.py — TokenStore, _RateLimiter, BearerAuthMiddleware."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from weathgards.mcp_server.auth import (
    BearerAuthMiddleware,
    TokenStore,
    _RateLimiter,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def token_store(tmp_path: Path) -> TokenStore:
    return TokenStore(data_dir=tmp_path)


def _make_app(token_store: TokenStore, max_rps: int = 1000) -> Starlette:
    """Minimal Starlette app with BearerAuthMiddleware for testing."""

    async def ping(request: Request) -> PlainTextResponse:
        return PlainTextResponse("pong")

    app = Starlette(routes=[Route("/ping", ping)])
    app.add_middleware(BearerAuthMiddleware, token_store=token_store, rate_limiter=_RateLimiter(max_rps))
    return app


# ---------------------------------------------------------------------------
# TokenStore
# ---------------------------------------------------------------------------

class TestTokenStore:
    def test_generates_token_on_first_run(self, tmp_path: Path) -> None:
        store = TokenStore(data_dir=tmp_path)
        assert store.get_token()
        assert len(store.get_token()) > 20

    def test_token_persisted_to_file(self, tmp_path: Path) -> None:
        store = TokenStore(data_dir=tmp_path)
        token_file = tmp_path / "mcp.token"
        assert token_file.exists()
        assert store.get_token() in token_file.read_text()

    def test_loads_existing_token(self, tmp_path: Path) -> None:
        # Pre-write a token
        token_file = tmp_path / "mcp.token"
        token_file.write_text("my_existing_token\n", encoding="utf-8")

        store = TokenStore(data_dir=tmp_path)
        assert store.get_token() == "my_existing_token"

    def test_generates_new_token_when_file_empty(self, tmp_path: Path) -> None:
        token_file = tmp_path / "mcp.token"
        token_file.write_text("", encoding="utf-8")

        store = TokenStore(data_dir=tmp_path)
        assert store.get_token()  # non-empty

    def test_verify_correct_token(self, token_store: TokenStore) -> None:
        assert token_store.verify(token_store.get_token()) is True

    def test_verify_wrong_token(self, token_store: TokenStore) -> None:
        assert token_store.verify("wrong-token") is False

    def test_is_configured_true(self, token_store: TokenStore) -> None:
        assert token_store.is_configured() is True

    def test_two_stores_same_dir_share_token(self, tmp_path: Path) -> None:
        s1 = TokenStore(data_dir=tmp_path)
        s2 = TokenStore(data_dir=tmp_path)
        assert s1.get_token() == s2.get_token()


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def test_allows_up_to_max(self) -> None:
        limiter = _RateLimiter(max_requests=3, window_sec=60)
        for _ in range(3):
            assert limiter.is_allowed("1.2.3.4") is True

    def test_blocks_after_max(self) -> None:
        limiter = _RateLimiter(max_requests=2, window_sec=60)
        limiter.is_allowed("1.2.3.4")
        limiter.is_allowed("1.2.3.4")
        assert limiter.is_allowed("1.2.3.4") is False

    def test_different_ips_are_independent(self) -> None:
        limiter = _RateLimiter(max_requests=1, window_sec=60)
        assert limiter.is_allowed("1.1.1.1") is True
        assert limiter.is_allowed("2.2.2.2") is True
        assert limiter.is_allowed("1.1.1.1") is False
        assert limiter.is_allowed("2.2.2.2") is False


# ---------------------------------------------------------------------------
# BearerAuthMiddleware
# ---------------------------------------------------------------------------

class TestBearerAuthMiddleware:
    def test_request_without_auth_returns_401(self, token_store: TokenStore) -> None:
        client = TestClient(_make_app(token_store), raise_server_exceptions=False)
        resp = client.get("/ping")
        assert resp.status_code == 401
        assert "Authorization" in resp.json()["error"]

    def test_request_with_wrong_token_returns_401(self, token_store: TokenStore) -> None:
        client = TestClient(_make_app(token_store), raise_server_exceptions=False)
        resp = client.get("/ping", headers={"Authorization": "Bearer wrong-token"})
        assert resp.status_code == 401
        assert "Invalid token" in resp.json()["error"]

    def test_request_with_correct_token_passes(self, token_store: TokenStore) -> None:
        client = TestClient(_make_app(token_store), raise_server_exceptions=False)
        resp = client.get(
            "/ping",
            headers={"Authorization": f"Bearer {token_store.get_token()}"},
        )
        assert resp.status_code == 200
        assert resp.text == "pong"

    def test_bearer_prefix_required(self, token_store: TokenStore) -> None:
        client = TestClient(_make_app(token_store), raise_server_exceptions=False)
        resp = client.get(
            "/ping",
            headers={"Authorization": token_store.get_token()},  # missing "Bearer "
        )
        assert resp.status_code == 401

    def test_rate_limit_returns_429(self, token_store: TokenStore) -> None:
        # max_rps=1 so the 2nd request is blocked
        app = _make_app(token_store, max_rps=1)
        client = TestClient(app, raise_server_exceptions=False)
        token = token_store.get_token()
        headers = {"Authorization": f"Bearer {token}"}

        resp1 = client.get("/ping", headers=headers)
        assert resp1.status_code == 200

        resp2 = client.get("/ping", headers=headers)
        assert resp2.status_code == 429
        assert "Retry-After" in resp2.headers
