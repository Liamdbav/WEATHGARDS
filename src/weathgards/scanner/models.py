"""Pydantic v2 models for scanner output."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class DockerMeta(BaseModel):
    image: str
    ports: dict[str, list[str]] = Field(default_factory=dict)
    labels: dict[str, str] = Field(default_factory=dict)
    uptime_seconds: int | None = None


class ProcessMeta(BaseModel):
    pid: int
    listening_ports: list[int] = Field(default_factory=list)
    cpu_percent: float | None = None
    mem_rss_mb: float | None = None
    exe: str | None = None
    cmdline: list[str] = Field(default_factory=list)


class ServiceMeta(BaseModel):
    unit: str
    description: str = ""
    active_state: str = ""
    sub_state: str = ""
    load_state: str = ""


class ScanResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: Literal["docker", "process", "service"]
    status: str
    metadata: DockerMeta | ProcessMeta | ServiceMeta
    os_origin: str

    model_config = {"frozen": True}
