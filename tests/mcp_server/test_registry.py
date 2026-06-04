"""Tests for ToolRegistry — uses a tmp_path, never touches config_dir()."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from weathgards.mcp_server.tools.registry import ActivatedTool, ToolRegistry


@pytest.fixture
def registry(tmp_path: Path) -> ToolRegistry:
    return ToolRegistry(data_dir=tmp_path)


class TestRegister:
    def test_register_creates_entry(self, registry: ToolRegistry) -> None:
        entry = registry.register("docker_container_status", "nginx")
        assert isinstance(entry, ActivatedTool)
        assert entry.tool_name == "docker_container_status"
        assert entry.target_name == "nginx"
        assert entry.enabled is True
        assert entry.id  # non-empty UUID string

    def test_register_is_idempotent(self, registry: ToolRegistry) -> None:
        e1 = registry.register("docker_container_logs", "api")
        e2 = registry.register("docker_container_logs", "api")
        assert e1.id == e2.id

    def test_register_different_targets_creates_separate_entries(
        self, registry: ToolRegistry
    ) -> None:
        e1 = registry.register("docker_container_status", "web")
        e2 = registry.register("docker_container_status", "db")
        assert e1.id != e2.id

    def test_register_different_tools_same_target(self, registry: ToolRegistry) -> None:
        e1 = registry.register("docker_container_status", "web")
        e2 = registry.register("docker_container_logs", "web")
        assert e1.id != e2.id

    def test_re_register_disabled_re_enables(self, registry: ToolRegistry) -> None:
        e1 = registry.register("process_status", "nginx")
        registry.unregister(e1.id)

        active = registry.list_active()
        assert not any(e.id == e1.id for e in active)

        e2 = registry.register("process_status", "nginx")
        assert e2.id == e1.id
        assert e2.enabled is True


class TestUnregister:
    def test_unregister_existing_returns_true(self, registry: ToolRegistry) -> None:
        entry = registry.register("docker_container_status", "web")
        result = registry.unregister(entry.id)
        assert result is True

    def test_unregister_nonexistent_returns_false(self, registry: ToolRegistry) -> None:
        result = registry.unregister("00000000-0000-0000-0000-000000000000")
        assert result is False

    def test_unregistered_entry_not_in_list_active(self, registry: ToolRegistry) -> None:
        entry = registry.register("docker_container_status", "nginx")
        registry.unregister(entry.id)
        active_ids = [e.id for e in registry.list_active()]
        assert entry.id not in active_ids

    def test_unregister_only_disables_target_entry(self, registry: ToolRegistry) -> None:
        e1 = registry.register("docker_container_status", "web")
        e2 = registry.register("docker_container_status", "db")
        registry.unregister(e1.id)

        active_ids = [e.id for e in registry.list_active()]
        assert e1.id not in active_ids
        assert e2.id in active_ids


class TestListActive:
    def test_empty_registry_returns_empty_list(self, registry: ToolRegistry) -> None:
        assert registry.list_active() == []

    def test_only_enabled_entries_returned(self, registry: ToolRegistry) -> None:
        e1 = registry.register("docker_container_status", "web")
        e2 = registry.register("docker_container_logs", "api")
        registry.unregister(e2.id)

        active = registry.list_active()
        active_ids = [e.id for e in active]
        assert e1.id in active_ids
        assert e2.id not in active_ids


class TestPersistence:
    def test_entries_survive_new_instance(self, tmp_path: Path) -> None:
        r1 = ToolRegistry(data_dir=tmp_path)
        entry = r1.register("process_status", "nginx")

        r2 = ToolRegistry(data_dir=tmp_path)
        active = r2.list_active()
        assert any(e.id == entry.id for e in active)

    def test_json_file_is_valid(self, tmp_path: Path) -> None:
        registry = ToolRegistry(data_dir=tmp_path)
        registry.register("docker_container_status", "web")

        registry_file = tmp_path / "tool_registry.json"
        assert registry_file.exists()

        data = json.loads(registry_file.read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["tool_name"] == "docker_container_status"
        assert data[0]["enabled"] is True

    def test_corrupt_file_returns_empty_list(self, tmp_path: Path) -> None:
        registry_file = tmp_path / "tool_registry.json"
        registry_file.write_text("not valid json", encoding="utf-8")

        registry = ToolRegistry(data_dir=tmp_path)
        assert registry.list_active() == []
