"""Bearer token authentication and rate limiting for the MCP server.

Security contract
-----------------
- Token is auto-generated on first launch with secrets.token_urlsafe(32),
  persisted to config_dir()/mcp.token (chmod 600), logged ONCE so the
  operator can copy it into the LLM client config.
- BearerAuthMiddleware validates Authorization: Bearer <token> on every
  request using constant-time comparison (no timing-oracle).
- Rate limiter: 60 requests / 60 seconds per client IP. Returns 429 with
  Retry-After header when the window is exceeded.
- MCPServerManager refuses to bind to 0.0.0.0 when the token is empty.
"""

from __future__ import annotations

import secrets
import time
from collections import deque
from pathlib import Path
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from weathgards.platform_utils import config_dir

log = structlog.get_logger(__name__)

_TOKEN_FILENAME = "mcp.token"
_RATE_WINDOW_SEC: float = 60.0
_RATE_MAX_REQUESTS: int = 60


# ---------------------------------------------------------------------------
# Token store
# ---------------------------------------------------------------------------

class TokenStore:
    """Load-or-generate the MCP bearer token and persist it safely."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self._path: Path = (data_dir or config_dir()) / _TOKEN_FILENAME
        self._token: str = self._load_or_generate()

    def _load_or_generate(self) -> str:
        if self._path.exists():
            token = self._path.read_text(encoding="utf-8").strip()
            if token:
                log.debug("mcp.token.loaded", path=str(self._path))
                return token

        token = secrets.token_urlsafe(32)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(token + "\n", encoding="utf-8")
        try:
            self._path.chmod(0o600)
        except OSError:
            pass  # Windows doesn't support Unix permissions
        # Log token once — operator copies it into LLM client configuration
        log.info(
            "mcp.token.generated",
            path=str(self._path),
            token=token,
        )
        return token

    def get_token(self) -> str:
        return self._token

    def is_configured(self) -> bool:
        """Return True when the token is a non-empty, non-placeholder value."""
        return bool(self._token)

    def verify(self, presented: str) -> bool:
        """Constant-time comparison — prevents timing-oracle attacks."""
        return secrets.compare_digest(presented, self._token)


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class _RateLimiter:
    """Sliding-window counter: max N requests per window per client IP."""

    def __init__(
        self,
        max_requests: int = _RATE_MAX_REQUESTS,
        window_sec: float = _RATE_WINDOW_SEC,
    ) -> None:
        self._max = max_requests
        self._window = window_sec
        self._buckets: dict[str, deque[float]] = {}

    def is_allowed(self, client_ip: str) -> bool:
        now = time.monotonic()
        bucket = self._buckets.setdefault(client_ip, deque())
        while bucket and now - bucket[0] > self._window:
            bucket.popleft()
        if len(bucket) >= self._max:
            return False
        bucket.append(now)
        return True


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Require a valid Bearer token on every MCP request."""

    def __init__(
        self,
        app: ASGIApp,
        token_store: TokenStore,
        rate_limiter: _RateLimiter | None = None,
    ) -> None:
        super().__init__(app)
        self._store = token_store
        self._limiter = rate_limiter or _RateLimiter()

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        client_ip = request.client.host if request.client else "unknown"

        if not self._limiter.is_allowed(client_ip):
            log.warning("mcp.auth.rate_limited", ip=client_ip, path=request.url.path)
            return JSONResponse(
                {"error": "Too many requests"},
                status_code=429,
                headers={"Retry-After": str(int(_RATE_WINDOW_SEC))},
            )

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            log.warning("mcp.auth.missing_token", ip=client_ip, path=request.url.path)
            return JSONResponse(
                {"error": "Authorization header with Bearer token required"},
                status_code=401,
            )

        presented = auth_header[len("Bearer "):]
        if not self._store.verify(presented):
            log.warning("mcp.auth.invalid_token", ip=client_ip)
            return JSONResponse({"error": "Invalid token"}, status_code=401)

        return await call_next(request)
