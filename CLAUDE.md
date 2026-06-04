# WEATHGARDS — Architecture & Development Reference

## What is WEATHGARDS?

A **local, cross-OS MCP gateway** that:
1. Scans Docker containers, OS processes, and local services
2. Exposes pre-written, parameterised MCP tools over a secure network transport
3. Lets a remote LLM (same subnet) interrogate target state and logs
4. Serves a React cockpit UI from the same FastAPI process

---

## Central Architectural Principle: TEMPLATE-FIRST

> **LLMs do NOT generate MCP handler code at runtime.**

MCP tool handlers are written once by developers, parameterised, and tested.
The scanner only discovers valid target *names* and populates a registry.
Activation maps a discovered target to a handler template.

```
Scanner discovers → "nginx:8080" (a process)
Activation wires  → ProcessLogHandler(target="nginx:8080")
LLM queries       → mcp.call("get_process_logs", {"target": "nginx:8080"})
Handler executes  → psutil lookup, returns structured result
```

Never add a code-generation path that produces Python from LLM output.

---

## Directory Layout

```
WEATHGARDS/
├── src/weathgards/
│   ├── __init__.py
│   ├── __main__.py            # entry point: weathgards CLI
│   ├── platform_utils.py      # OS detection, Docker availability, config dir
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py        # Pydantic-settings model, loads .env
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── docker_scanner.py  # docker SDK, guarded by is_docker_available()
│   │   ├── process_scanner.py # psutil, truly cross-OS
│   │   └── registry.py        # DiscoveredTarget dataclass + TargetRegistry
│   ├── mcp_server/
│   │   ├── __init__.py
│   │   ├── server.py          # mcp.Server setup, transport wiring
│   │   ├── auth.py            # Bearer token middleware
│   │   └── handlers/          # one file per handler template
│   │       ├── __init__.py
│   │       ├── container_logs.py
│   │       ├── container_status.py
│   │       ├── process_info.py
│   │       └── process_logs.py
│   └── api/
│       ├── __init__.py
│       ├── app.py             # FastAPI app factory
│       ├── routers/
│       │   ├── __init__.py
│       │   ├── scan.py        # POST /api/scan, GET /api/targets
│       │   └── activation.py  # POST /api/activate, DELETE /api/activate/{id}
│       └── static.py          # serves frontend/dist at "/"
├── tests/
│   ├── conftest.py
│   ├── test_platform_utils.py
│   ├── test_scanner/
│   └── test_api/
├── frontend/                  # React + Vite + Tailwind cockpit
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
├── pyproject.toml
├── uv.lock
├── .env.example
└── CLAUDE.md
```

---

## Python Conventions

| Rule | Detail |
|------|--------|
| Python | 3.12+ only. Use `type \| None`, never `Optional[type]`. |
| Paths | `pathlib.Path` exclusively. Never string concatenation for paths. |
| Interpreter | `sys.executable` when spawning subprocesses. Never `"python"` or `"python3"`. |
| Typing | `mypy --strict` must pass. No `Any` escapes without `# type: ignore` comment explaining why. |
| Async | FastAPI routes and scanner methods are `async`. Blocking I/O (psutil, docker SDK) runs in `asyncio.to_thread()`. |
| Validation | All external data (env, API payloads, scanner output) goes through a Pydantic v2 model. |
| Logging | `structlog` only. No bare `print()` or `logging.basicConfig()`. |
| Settings | `pydantic-settings` loads `.env`. Never `os.environ["KEY"]` directly in application logic. |

---

## Cross-OS Guards — NON-NEGOTIABLE

Every platform-specific code path **must** be guarded:

```python
import platform

match platform.system():
    case "Linux" | "Darwin":
        # Unix socket path
    case "Windows":
        # named pipe path
    case _:
        raise NotImplementedError(f"Unsupported OS: {platform.system()}")
```

`is_docker_available()` in `platform_utils.py` is the single source of truth for
whether Docker scanning is enabled. It checks socket/pipe existence at runtime —
never assume Docker is present based on OS alone.

All scanner modules must degrade gracefully:
- Docker unavailable → log warning, return empty list, do not crash.
- psutil permission error → log warning, skip that process, continue scan.

---

## Network Security

The MCP server is reachable over the local network. Two layers of protection:

1. **Bearer token** (`WEATHGARDS_MCP_TOKEN`): every request to `/mcp/*` must
   carry `Authorization: Bearer <token>`. Validated in `mcp_server/auth.py`
   before any tool dispatch.

2. **IP allowlist** (`WEATHGARDS_ALLOWED_CLIENTS`): optional CIDR-based filter
   applied at the ASGI middleware level before auth. Empty = token-only mode.

Never expose the MCP endpoint on `0.0.0.0` without setting both controls.
The `.env.example` documents this requirement explicitly.

---

## Dev Commands

```bash
# Install dependencies (first time)
uv sync --extra dev

# Run the app (dev mode, auto-reload)
uv run weathgards --reload

# Lint
uv run ruff check src tests

# Format
uv run ruff format src tests

# Type check
uv run mypy src

# Tests
uv run pytest

# Tests without coverage (fast)
uv run pytest --no-cov

# Build frontend then restart
cd frontend && npm run build && cd .. && uv run weathgards
```

---

## Adding a New MCP Handler

1. Create `src/weathgards/mcp_server/handlers/<name>.py`.
2. Define a dataclass or Pydantic model for its parameters.
3. Implement the handler as an `async def` that accepts typed params and returns a `dict`.
4. Register it in `mcp_server/server.py` with a `@mcp.tool()` decorator.
5. Add tests in `tests/test_mcp_server/test_<name>.py`.
6. Do **not** generate handler code dynamically. Parameters only.

---

## Scanner → Activation → Handler Data Flow

```
[Scanner]        [Registry]          [API /activate]      [MCP Server]
   │                  │                    │                    │
   ├─ scan() ────────►│ DiscoveredTarget   │                    │
   │                  │                    │                    │
   │                  │◄─ POST /activate ──┤ ActivationRequest  │
   │                  │                    │                    │
   │                  ├─ wire template ────────────────────────►│ tool registered
   │                  │                    │                    │
   │                  │                    │    LLM call ───────►│ tool executed
```
