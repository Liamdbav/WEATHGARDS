"""Application settings — two tiers.

Boot-time (Settings)
  Loaded once from env / .env via pydantic-settings. Controls FastAPI
  host/port, log level, Docker socket, etc. Immutable at runtime.

Runtime-mutable (AppSettings)
  Loaded from config_dir()/settings.json; updated via PUT /api/settings.
  Controls MCP server defaults, scanner toggles, auto-scan interval.
  Survives restarts; never touches env vars.
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog
from typing import Annotated

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

log = structlog.get_logger(__name__)

_APP_SETTINGS_FILE = "settings.json"


def _resolve_static_dir() -> Path:
    """Return the frontend dist directory for both dev and installed-wheel modes."""
    dev = Path("frontend/dist")
    if dev.exists():
        return dev
    # When installed as a wheel, frontend/dist is bundled under weathgards/web/
    # __file__ is .../weathgards/config/settings.py → parent.parent = .../weathgards/
    pkg_web = Path(__file__).parent.parent / "web"
    if pkg_web.exists():
        return pkg_web
    return dev  # fallback — mount_frontend will emit a warning if missing


# ---------------------------------------------------------------------------
# Boot-time settings (env / .env — immutable at runtime)
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WEATHGARDS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Server
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8765, ge=1, le=65535)
    env: str = Field(default="development", pattern="^(development|production)$")

    # Security
    mcp_token: str = Field(default="CHANGE_ME")
    allowed_clients: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Docker
    docker_host: str | None = Field(default=None)
    docker_timeout: int = Field(default=10, ge=1)

    # TLS
    tls_cert_file: str = Field(default="")
    tls_key_file: str = Field(default="")

    # Process scanner
    process_include_patterns: Annotated[list[str], NoDecode] = Field(default_factory=list)
    scan_interval: int = Field(default=30, ge=0)

    # Logging
    log_level: str = Field(
        default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"
    )
    log_format: str = Field(default="console", pattern="^(json|console)$")

    # Frontend — resolved at import time so both dev and installed-wheel work.
    # Dev:       CWD/frontend/dist  (populated by `cd frontend && npm run build`)
    # Installed: <site-packages>/weathgards/web  (bundled via pyproject force-include)
    static_dir: Path = Field(default_factory=_resolve_static_dir)

    @field_validator("allowed_clients", mode="before")
    @classmethod
    def _split_comma(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v  # type: ignore[return-value]

    @field_validator("process_include_patterns", mode="before")
    @classmethod
    def _split_patterns(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v  # type: ignore[return-value]

    @property
    def is_production(self) -> bool:
        return self.env == "production"


from functools import lru_cache


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# ---------------------------------------------------------------------------
# Runtime-mutable settings (config_dir()/settings.json)
# ---------------------------------------------------------------------------

class ScannerToggles(BaseModel):
    docker: bool = True
    processes: bool = True
    services: bool = True


class AppSettings(BaseModel):
    """Persisted, mutable runtime configuration.

    Updated via PUT /api/settings and reloaded without process restart.
    Changing MCP host/port/transport takes effect on the *next* server start.
    """

    # MCP server defaults used by POST /api/mcp/start
    mcp_host: str = Field(default="127.0.0.1")
    mcp_port: int = Field(default=9766, ge=1, le=65535)
    mcp_transport: str = Field(default="streamable-http")
    network_exposed: bool = Field(default=False)

    # Scanner behaviour
    # 0 = background auto-scan disabled (manual only)
    auto_scan_interval: int = Field(default=30, ge=0)
    scanner_toggles: ScannerToggles = Field(default_factory=ScannerToggles)


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

# Module-level cache — single writer (settings API), multiple readers.
# Safe without explicit locking: asyncio is single-threaded and all callers
# run in the event loop or in asyncio.to_thread (each owns its GIL slot).
_cached_app: AppSettings | None = None


def _app_settings_path() -> Path:
    from weathgards.platform_utils import config_dir  # local import avoids circular
    return config_dir() / _APP_SETTINGS_FILE


def get_app_settings() -> AppSettings:
    """Return the current AppSettings, loading from disk on first call."""
    global _cached_app
    if _cached_app is not None:
        return _cached_app

    path = _app_settings_path()
    if not path.exists():
        _cached_app = AppSettings()
        return _cached_app

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        _cached_app = AppSettings.model_validate(raw)
        log.debug("app_settings.loaded", path=str(path))
    except Exception as exc:
        log.warning("app_settings.load_failed", error=str(exc), path=str(path))
        _cached_app = AppSettings()

    return _cached_app


def save_app_settings(new_settings: AppSettings) -> None:
    """Persist new_settings to disk and update the in-memory cache."""
    global _cached_app
    path = _app_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_settings.model_dump_json(indent=2), encoding="utf-8")
    _cached_app = new_settings
    log.info("app_settings.saved", path=str(path))
