"""Scan and health API routes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from weathgards.platform_utils import current_os, is_docker_available
from weathgards.scanner.models import ScanResult
from weathgards.scanner.orchestrator import scan_environment

router = APIRouter(prefix="/api", tags=["scan"])


class HealthResponse(BaseModel):
    status: str
    os: str
    docker_available: bool


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        os=current_os(),
        docker_available=is_docker_available(),
    )


@router.get("/scan", response_model=list[ScanResult])
async def scan() -> list[ScanResult]:
    return await scan_environment()
