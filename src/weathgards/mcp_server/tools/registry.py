"""Activation registry — tracks which (tool, target) pairs are enabled.

Persists to config_dir()/tool_registry.json as a JSON array of ActivatedTool
entries. All I/O is synchronous; callers that need async wrap with
asyncio.to_thread().

Design rules:
- Activating the same (tool_name, target_name) pair is idempotent:
  returns the existing entry rather than creating a duplicate.
- Unregistering a non-existent id is a no-op (returns False).
- The registry never stores handler code — only names and metadata.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import structlog
from pydantic import BaseModel, Field

from weathgards.platform_utils import config_dir

log = structlog.get_logger(__name__)

_REGISTRY_FILENAME = "tool_registry.json"


class ActivatedTool(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str
    target_name: str
    enabled: bool = True
    activated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"frozen": True}


class ToolRegistry:
    """File-backed registry of activated (tool, target) pairs."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self._path = (data_dir or config_dir()) / _REGISTRY_FILENAME

    # ------------------------------------------------------------------
    # Private I/O
    # ------------------------------------------------------------------

    def _load(self) -> list[ActivatedTool]:
        if not self._path.exists():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return [ActivatedTool.model_validate(entry) for entry in raw]
        except Exception as exc:
            log.warning("registry.load_failed", path=str(self._path), error=str(exc))
            return []

    def _save(self, entries: list[ActivatedTool]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            [e.model_dump(mode="json") for e in entries],
            indent=2,
        )
        self._path.write_text(payload, encoding="utf-8")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, tool_name: str, target_name: str) -> ActivatedTool:
        """Activate *tool_name* for *target_name*.

        Idempotent: if the pair already exists and is enabled, returns it
        unchanged. If it was disabled, re-enables it.
        """
        entries = self._load()

        for entry in entries:
            if entry.tool_name == tool_name and entry.target_name == target_name:
                if entry.enabled:
                    log.debug("registry.already_active", tool=tool_name, target=target_name)
                    return entry
                # Re-enable a previously disabled entry
                updated = ActivatedTool(
                    id=entry.id,
                    tool_name=entry.tool_name,
                    target_name=entry.target_name,
                    enabled=True,
                    activated_at=entry.activated_at,
                )
                new_entries = [updated if e.id == entry.id else e for e in entries]
                self._save(new_entries)
                log.info("registry.re_enabled", tool=tool_name, target=target_name)
                return updated

        new_entry = ActivatedTool(tool_name=tool_name, target_name=target_name)
        entries.append(new_entry)
        self._save(entries)
        log.info("registry.registered", tool=tool_name, target=target_name, id=new_entry.id)
        return new_entry

    def unregister(self, entry_id: str) -> bool:
        """Disable the registry entry with *entry_id*. Returns False if not found."""
        entries = self._load()
        match = next((e for e in entries if e.id == entry_id), None)
        if match is None:
            log.debug("registry.not_found", id=entry_id)
            return False

        updated = ActivatedTool(
            id=match.id,
            tool_name=match.tool_name,
            target_name=match.target_name,
            enabled=False,
            activated_at=match.activated_at,
        )
        new_entries = [updated if e.id == entry_id else e for e in entries]
        self._save(new_entries)
        log.info("registry.unregistered", id=entry_id)
        return True

    def list_active(self) -> list[ActivatedTool]:
        """Return only enabled entries."""
        return [e for e in self._load() if e.enabled]

    def list_all(self) -> list[ActivatedTool]:
        """Return all entries including disabled ones."""
        return self._load()


# Module-level default instance — used by routes
_default_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Return the singleton registry backed by config_dir()."""
    return _default_registry
