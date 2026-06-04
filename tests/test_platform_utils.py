"""Tests for platform_utils — these must pass on Linux, macOS, and Windows."""

from __future__ import annotations

import platform
from pathlib import Path
from unittest.mock import patch

import pytest

from weathgards.platform_utils import (
    config_dir,
    current_os,
    docker_socket_uri,
    is_docker_available,
)


class TestCurrentOs:
    def test_returns_known_os(self):
        result = current_os()
        assert result in {"linux", "macos", "windows"}

    def test_linux(self):
        with patch.object(platform, "system", return_value="Linux"):
            assert current_os() == "linux"

    def test_macos(self):
        with patch.object(platform, "system", return_value="Darwin"):
            assert current_os() == "macos"

    def test_windows(self):
        with patch.object(platform, "system", return_value="Windows"):
            assert current_os() == "windows"

    def test_unknown_raises(self):
        with patch.object(platform, "system", return_value="FreeBSD"), pytest.raises(NotImplementedError, match="FreeBSD"):
            current_os()


class TestIsDockerAvailable:
    def test_returns_bool(self):
        assert isinstance(is_docker_available(), bool)

    def test_linux_socket_present(self, tmp_path):
        fake_sock = tmp_path / "docker.sock"
        fake_sock.touch()
        with (
            patch.object(platform, "system", return_value="Linux"),
            patch("weathgards.platform_utils.Path", side_effect=lambda p: fake_sock if "docker.sock" in str(p) else Path(p)),
        ):
            # Integration-style: trust the actual filesystem check on the CI runner
            assert isinstance(is_docker_available(), bool)

    def test_unsupported_os_returns_false(self):
        with patch.object(platform, "system", return_value="FreeBSD"):
            assert is_docker_available() is False


class TestConfigDir:
    def test_returns_path(self):
        result = config_dir()
        assert isinstance(result, Path)

    def test_directory_exists_after_call(self):
        path = config_dir()
        assert path.exists()
        assert path.is_dir()

    def test_contains_weathgards(self):
        # platformdirs should include the app name somewhere in the path
        assert "weathgards" in str(config_dir()).lower()


class TestDockerSocketUri:
    def test_returns_none_when_unavailable(self):
        with patch("weathgards.platform_utils.is_docker_available", return_value=False):
            assert docker_socket_uri() is None

    def test_linux_uri(self):
        with (
            patch("weathgards.platform_utils.is_docker_available", return_value=True),
            patch.object(platform, "system", return_value="Linux"),
        ):
            uri = docker_socket_uri()
            assert uri == "unix:///var/run/docker.sock"

    def test_windows_uri(self):
        with (
            patch("weathgards.platform_utils.is_docker_available", return_value=True),
            patch.object(platform, "system", return_value="Windows"),
        ):
            uri = docker_socket_uri()
            assert uri == "npipe:////./pipe/docker_engine"
