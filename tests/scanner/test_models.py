"""Tests for scanner Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from weathgards.scanner.models import DockerMeta, ProcessMeta, ScanResult, ServiceMeta


class TestDockerMeta:
    def test_defaults(self):
        m = DockerMeta(image="nginx:latest")
        assert m.ports == {}
        assert m.labels == {}
        assert m.uptime_seconds is None

    def test_full(self):
        m = DockerMeta(
            image="redis:7",
            ports={"6379/tcp": ["0.0.0.0:6379"]},
            labels={"env": "dev"},
            uptime_seconds=3600,
        )
        assert m.uptime_seconds == 3600


class TestProcessMeta:
    def test_defaults(self):
        m = ProcessMeta(pid=1234)
        assert m.listening_ports == []
        assert m.cpu_percent is None
        assert m.mem_rss_mb is None

    def test_with_ports(self):
        m = ProcessMeta(pid=999, listening_ports=[8080, 8443])
        assert 8080 in m.listening_ports


class TestServiceMeta:
    def test_defaults(self):
        m = ServiceMeta(unit="nginx.service")
        assert m.description == ""
        assert m.active_state == ""


class TestScanResult:
    def test_docker_result(self):
        r = ScanResult(
            name="my-container",
            type="docker",
            status="running",
            metadata=DockerMeta(image="alpine:3"),
            os_origin="linux",
        )
        assert r.type == "docker"
        assert r.id  # auto-generated UUID

    def test_process_result(self):
        r = ScanResult(
            name="uvicorn",
            type="process",
            status="running",
            metadata=ProcessMeta(pid=42, listening_ports=[8000]),
            os_origin="linux",
        )
        assert isinstance(r.metadata, ProcessMeta)
        assert r.metadata.pid == 42

    def test_service_result(self):
        r = ScanResult(
            name="nginx.service",
            type="service",
            status="active",
            metadata=ServiceMeta(unit="nginx.service", active_state="active"),
            os_origin="linux",
        )
        assert r.type == "service"

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            ScanResult(
                name="x",
                type="unknown",  # type: ignore[arg-type]
                status="?",
                metadata=ProcessMeta(pid=1),
                os_origin="linux",
            )

    def test_frozen(self):
        r = ScanResult(
            name="test",
            type="process",
            status="ok",
            metadata=ProcessMeta(pid=1),
            os_origin="linux",
        )
        with pytest.raises((TypeError, ValidationError)):
            r.name = "mutated"  # type: ignore[misc]

    def test_unique_ids(self):
        a = ScanResult(
            name="a", type="process", status="ok",
            metadata=ProcessMeta(pid=1), os_origin="linux",
        )
        b = ScanResult(
            name="b", type="process", status="ok",
            metadata=ProcessMeta(pid=2), os_origin="linux",
        )
        assert a.id != b.id
