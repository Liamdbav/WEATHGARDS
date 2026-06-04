"""Tool catalog — all templates written once, frozen, never generated.

CATALOG is the single authoritative list of available MCP tools.
HANDLER_MAP wires each tool name to its pre-written async handler.
Adding a tool means editing this file and its handler module — nothing else.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel

from weathgards.mcp_server.tools.docker_tools import (
    docker_container_logs,
    docker_container_status,
    docker_list_containers,
)
from weathgards.mcp_server.tools.process_tools import process_status


class ToolParam(BaseModel):
    name: str
    type: str  # JSON Schema primitive: "string", "integer", "boolean"
    description: str
    required: bool = True
    default: str | int | None = None


class ToolDefinition(BaseModel):
    name: str
    description: str
    # Which scan type this tool applies to. "any" means no specific target required.
    target_type: Literal["docker", "process", "service", "any"]
    parameters: list[ToolParam]
    # Which parameter receives the `target_name` from an activation request.
    # None for tools that don't accept a target (e.g. docker_list_containers).
    target_param: str | None = None

    model_config = {"frozen": True}


# Handler signature: keyword args matching ToolParam names → JSON-safe dict
HandlerFn = Callable[..., Awaitable[dict[str, Any]]]

# ---------------------------------------------------------------------------
# Frozen catalog — all entries are static, authored here, never generated
# ---------------------------------------------------------------------------

CATALOG: list[ToolDefinition] = [
    ToolDefinition(
        name="docker_container_status",
        description=(
            "Indique si un container Docker est actif ou arrêté, "
            "son image, son code de sortie et ses timestamps de démarrage."
        ),
        target_type="docker",
        target_param="name",
        parameters=[
            ToolParam(
                name="name",
                type="string",
                description="Container name or short ID",
                required=True,
            ),
        ],
    ),
    ToolDefinition(
        name="docker_container_logs",
        description="Récupère les dernières lignes de logs d'un container Docker, avec leurs timestamps.",
        target_type="docker",
        target_param="name",
        parameters=[
            ToolParam(
                name="name",
                type="string",
                description="Container name or short ID",
                required=True,
            ),
            ToolParam(
                name="lines",
                type="integer",
                description="Number of log lines to return (default 50, max 500)",
                required=False,
                default=50,
            ),
        ],
    ),
    ToolDefinition(
        name="docker_list_containers",
        description=(
            "Liste tous les containers Docker présents sur la machine "
            "(actifs et arrêtés) avec leur nom, image et état. Aucune cible requise."
        ),
        target_type="any",
        target_param=None,
        parameters=[],
    ),
    ToolDefinition(
        name="process_status",
        description=(
            "Remonte l'usage CPU, la mémoire et les ports écoutés "
            "d'un processus identifié par son nom ou son PID."
        ),
        target_type="process",
        target_param="name_or_pid",
        parameters=[
            ToolParam(
                name="name_or_pid",
                type="string",
                description='Process name substring (e.g. "nginx") or numeric PID',
                required=True,
            ),
        ],
    ),
]

# ---------------------------------------------------------------------------
# Handler map — names must match CATALOG entries exactly
# ---------------------------------------------------------------------------

HANDLER_MAP: dict[str, HandlerFn] = {
    "docker_container_status": docker_container_status,
    "docker_container_logs": docker_container_logs,
    "docker_list_containers": docker_list_containers,
    "process_status": process_status,
}


def get_tool(name: str) -> ToolDefinition | None:
    """Return the ToolDefinition for *name*, or None if not in catalog."""
    return next((t for t in CATALOG if t.name == name), None)
