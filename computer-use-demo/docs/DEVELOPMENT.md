# Development Guide

> How to develop, test, debug, and contribute to the Computer Use Agent.

---

## Table of Contents

1. [Running the Backend](#1-running-the-backend)
2. [Running the Frontend](#2-running-the-frontend)
3. [Running Tests](#3-running-tests)
4. [Code Structure](#4-code-structure)
5. [Linting & Formatting](#5-linting--formatting)
6. [Debugging Tips](#6-debugging-tips)
7. [Adding New Tools](#7-adding-new-tools)
8. [Adding New API Endpoints](#8-adding-new-api-endpoints)

---

## 1. Running the Backend

### Option A: Inside Docker (Recommended)

The standard workflow is to develop using Docker, which provides the full X11/VNC stack:

```bash
# Build and run with live log output
docker compose up --build

# Watch for Python errors
docker compose logs -f | grep -i "error\|exception\|traceback"
```

**Hot-reload is NOT enabled** in the Docker setup (Uvicorn runs without `--reload`). To pick up code changes:

```bash
# Rebuild and restart
docker compose down && docker compose up --build
```

**Pro tip:** For faster iteration, mount the source code as a volume and add `--reload`:

```yaml
# Add to docker-compose.yml (development only)
services:
  computer-use:
    volumes:
      - ./computer_use_demo:/home/computeruse/computer_use_demo
    command: >
      python -m uvicorn computer_use_demo.api.app:app
      --host 0.0.0.0 --port 8000 --reload
```

### Option B: Local Development (Linux Only)

> ⚠️ Local development requires a Linux system with X11 display dependencies. macOS/Windows users should use Docker.

```bash
# 1. Set up the virtual environment
bash setup.sh
source .venv/bin/activate

# 2. Set required environment variables
export ANTHROPIC_API_KEY=sk-ant-api03-...
export WIDTH=1024
export HEIGHT=768
export DISPLAY_NUM=1

# 3. Start Xvfb (if not already running)
Xvfb :1 -ac -screen 0 1024x768x24 &

# 4. Run the API server with hot-reload
python -m uvicorn computer_use_demo.api.app:app \
  --reload \
  --port 8000 \
  --log-level debug
```

**Note:** Without the full Docker environment, the `DisplayService` will fail to spawn `Xvfb`/`mutter`/`tint2` processes for new sessions. Local development is best suited for working on API routes, schemas, and business logic — not testing actual computer use.

---

## 2. Running the Frontend

The frontend is a **static SPA** (no build step, no npm, no bundler):

```
frontend/
├── index.html    ← Main entry point (13KB)
├── app.js        ← Application logic (25KB)
└── style.css     ← Styles (22KB)
```

### In Docker

The frontend is automatically served by FastAPI:
- **`GET /`** → Serves `frontend/index.html`
- **`/static/**`** → Serves all files in `frontend/` directory

### Local Development

If you want to edit the frontend independently:

```bash
# Option 1: Python HTTP server (for standalone testing)
cd frontend
python3 -m http.server 3000

# Option 2: Just edit files — they're served from the Docker container
# If you mounted the source directory as a volume, changes are immediate.
```

### Frontend Architecture

The frontend communicates with the backend via:

| Mechanism | Endpoint | Purpose |
|---|---|---|
| **REST (fetch)** | `POST /api/sessions` | Create sessions |
| **REST (fetch)** | `POST /api/sessions/{id}/messages` | Send messages |
| **REST (fetch)** | `GET /api/sessions` | List sessions |
| **SSE (EventSource)** | `GET /api/sessions/{id}/stream` | Real-time agent events |
| **iframe** | `/vnc/?port={ws_port}&autoconnect=true` | Embedded VNC viewer |

---

## 3. Running Tests

### Test Suite Overview

```
tests/
├── conftest.py                  ← Shared fixtures (mocks DISPLAY env)
├── loop_test.py                 ← Agent sampling loop tests
├── streamlit_test.py            ← Legacy Streamlit tests
├── test_api.py                  ← API connectivity test (Gemini)
├── test_concurrent_sessions.py  ← Concurrency integration tests
├── run_all_tests.py             ← Comprehensive test runner
└── tools/
    ├── bash_test.py             ← BashTool unit tests
    ├── computer_test.py         ← ComputerTool unit tests
    └── edit_test.py             ← EditTool unit tests
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest tests/ -v

# Run specific test module
pytest tests/tools/bash_test.py -v

# Run specific test by name
pytest tests/ -v -k "test_create_session"

# Run with print output visible
pytest tests/ -v -s

# Run the comprehensive test runner (with detailed reporting)
python tests/run_all_tests.py
```

### Test Configuration

The `conftest.py` provides an `autouse` fixture that mocks screen dimensions:

```python
@pytest.fixture(autouse=True)
def mock_screen_dimensions():
    with mock.patch.dict(
        os.environ, {"HEIGHT": "768", "WIDTH": "1024", "DISPLAY_NUM": "1"}
    ):
        yield
```

This ensures all tool tests have the required environment variables without needing a real X11 display.

### Testing Concurrent Sessions

The `test_concurrent_sessions.py` file tests the critical concurrency features:

```bash
# Run against a running Docker container
python tests/test_concurrent_sessions.py
```

This test:
1. Creates two sessions simultaneously
2. Sends messages to both
3. Verifies both agent loops run in parallel
4. Checks that display numbers are unique
5. Validates VNC port isolation

### Writing New Tests

```python
# tests/test_my_feature.py
import pytest
from unittest import mock

@pytest.mark.asyncio
async def test_session_creation():
    """Test that session creation allocates a display."""
    from computer_use_demo.services.session import session_service

    # Mock the display service to avoid spawning real processes
    with mock.patch.object(
        session_service._display_service, 'allocate_display'
    ) as mock_alloc:
        mock_alloc.return_value = DisplayAllocation(
            display_num=100, vnc_port=5810, ws_port=5910
        )
        session = await session_service.create_session(title="Test")
        assert session["display_num"] == 100
```

---

## 4. Code Structure

### Backend Module Map

```
computer_use_demo/
│
├── __init__.py                          # Package marker
├── loop.py                              # Original Anthropic sampling loop (331 lines)
│                                        # Used as reference; the production loop is in
│                                        # services/agent/agent_runner.py
│
├── streamlit.py                         # Legacy Streamlit UI (retained for reference)
│
├── requirements.txt                     # Production Python dependencies
│
├── config/
│   └── settings.py                      # Settings dataclass — all env vars centralized
│                                        # Access via: from config.settings import settings
│
├── api/
│   ├── app.py                           # FastAPI app, CORS, lifespan, static mounts
│   ├── gemini_wrapper.py                # Anthropic ↔ Gemini format translation
│   ├── database.py                      # DEPRECATED — re-exports from db/
│   ├── session_manager.py               # DEPRECATED — re-exports from services/
│   ├── display_manager.py               # DEPRECATED — re-exports from services/
│   ├── models.py                        # DEPRECATED — re-exports from schemas/
│   └── routes/
│       ├── sessions.py                  # Session CRUD endpoints
│       ├── agent.py                     # Message send + SSE stream endpoints
│       ├── vm.py                        # VNC connection info endpoint
│       └── files.py                     # File operation endpoints
│
├── schemas/
│   ├── __init__.py                      # Exports all models
│   ├── session.py                       # SessionStatus, VNCInfo, CreateSessionRequest, etc.
│   ├── message.py                       # SendMessageRequest, MessageResponse, etc.
│   ├── event.py                         # SSEEvent, SSEEventType
│   └── models.py                        # Unified models file (all-in-one)
│
├── services/
│   ├── __init__.py                      # Exports all services
│   ├── session/
│   │   ├── active_session.py            # ActiveSession dataclass (runtime state)
│   │   └── session_service.py           # SessionService (lifecycle, tool creation)
│   ├── agent/
│   │   ├── agent_service.py             # AgentService (send message, stop, stream)
│   │   └── agent_runner.py              # AgentRunner (LLM + tool execution loop)
│   └── display/
│       └── display_service.py           # DisplayService (Xvfb/VNC allocation)
│
├── core/
│   └── events/
│       └── publisher.py                 # EventPublisher (SSE event pub/sub)
│
├── db/
│   ├── __init__.py                      # Exports init_db, close_db, CRUD functions
│   ├── database.py                      # ConnectionPool, schema init, pool utilities
│   └── repository.py                    # Session & message CRUD operations
│
├── tools/
│   ├── __init__.py                      # Exports all tools and groups
│   ├── base.py                          # BaseAnthropicTool, ToolResult, ToolError
│   ├── collection.py                    # ToolCollection (dispatch by name)
│   ├── groups.py                        # ToolGroup, TOOL_GROUPS_BY_VERSION
│   ├── computer.py                      # ComputerTool (mouse, keyboard, screenshots)
│   ├── bash.py                          # BashTool (persistent shell sessions)
│   ├── edit.py                          # EditTool (str_replace file editing)
│   └── run.py                           # Shell command runner utility
│
└── utils/
    └── logger.py                        # setup_logger() and get_logger()
```

### Key Import Patterns

```python
# Settings (use the global singleton)
from computer_use_demo.config.settings import settings

# Database operations (use the db package exports)
from computer_use_demo import db
await db.init_db()
await db.create_session(title="...")
await db.get_messages(session_id)

# Services (use global singletons)
from computer_use_demo.services.session import session_service
from computer_use_demo.services.agent import agent_service
from computer_use_demo.services.display import display_service

# Schemas
from computer_use_demo.schemas import (
    CreateSessionRequest, SessionResponse, SendMessageRequest
)

# Tools
from computer_use_demo.tools import ToolCollection, TOOL_GROUPS_BY_VERSION

# Events
from computer_use_demo.core.events import event_publisher

# Logging
from computer_use_demo.utils.logger import setup_logger
logger = setup_logger(__name__)
```

### Deprecated Files

The following files in `api/` are **deprecated shims** that re-export from the newer module locations. They exist for backward compatibility but should not be used in new code:

| Deprecated | Replacement |
|---|---|
| `api/database.py` | `db/database.py` + `db/repository.py` |
| `api/session_manager.py` | `services/session/session_service.py` |
| `api/display_manager.py` | `services/display/display_service.py` |
| `api/models.py` | `schemas/models.py` |

---

## 5. Linting & Formatting

### Ruff (Linter + Formatter)

The project uses [Ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
# Install (included in dev-requirements.txt)
pip install ruff==0.6.7

# Lint
ruff check .

# Lint and auto-fix
ruff check --fix .

# Format
ruff format .

# Check formatting without changes
ruff format --check .
```

### Ruff Configuration (`ruff.toml`)

```toml
extend-exclude = [".venv"]

[format]
docstring-code-format = true

[lint]
select = [
    "A",       # flake8-builtins
    "ASYNC",   # flake8-async
    "B",       # flake8-bugbear
    "E",       # pycodestyle errors
    "F",       # pyflakes
    "I",       # isort
    "PIE",     # flake8-pie
    "RUF200",  # ruff-specific rules
    "T20",     # flake8-print
    "UP",      # pyupgrade
    "W",       # pycodestyle warnings
]
ignore = ["E501", "ASYNC230"]   # Line length, async file ops

[lint.isort]
combine-as-imports = true
```

### Pre-commit Hooks

If you ran `setup.sh`, pre-commit hooks are installed:

```bash
# Run all hooks manually
pre-commit run --all-files

# Install hooks (if not already)
pre-commit install
```

---

## 6. Debugging Tips

### 6.1 Container Log Monitoring

```bash
# Full logs
docker compose logs -f

# Filter for errors
docker compose logs -f 2>&1 | grep -i "error\|exception\|traceback"

# Filter for a specific session
docker compose logs -f 2>&1 | grep "session_id_prefix"

# View the API stdout log inside the container
docker compose exec computer-use cat /tmp/api_stdout.log
```

### 6.2 Interactive Container Shell

```bash
# Shell into the running container
docker compose exec computer-use bash

# Check running processes
ps aux | grep -E "Xvfb|x11vnc|mutter|tint2|uvicorn|websockify"

# Check allocated displays
ls /tmp/.X*-lock

# Test a VNC port
nc -zv localhost 5910

# Check database manually
sqlite3 /data/sessions.db "SELECT id, status, display_num FROM sessions"

# Test an API endpoint from inside the container
curl http://localhost:8000/health
```

### 6.3 Debug Agent Loop

The `agent_runner.py` includes `print(f"[DEBUG]...")` statements that output to the container's stdout log. Key debug points:

```python
print(f"[DEBUG] Starting agent loop for session {session_id}", flush=True)
print(f"[DEBUG] Using API key starting with: {api_key[:15]}...", flush=True)
print(f"[DEBUG] Using Anthropic API with model: {settings.ANTHROPIC_MODEL}", flush=True)
print(f"[DEBUG] Got response from Anthropic API", flush=True)
```

To see these:
```bash
docker compose logs -f | grep "\[DEBUG\]"
```

### 6.4 Debug SSE Events

Use `curl` to watch the raw SSE stream:

```bash
# Replace SESSION_ID with an actual session ID
curl -N http://localhost:8000/api/sessions/SESSION_ID/stream
```

Example output:
```
event: status
data: {"status": "running"}

event: text
data: {"text": "I'll open Firefox and search for 'hello world'."}

event: tool_use
data: {"tool_id": "toolu_01Abc...", "name": "bash", "input": {"command": "(DISPLAY=:100 firefox &)"}}

event: tool_result
data: {"tool_id": "toolu_01Abc...", "output": "", "has_screenshot": false}

event: tool_use
data: {"tool_id": "toolu_02Def...", "name": "computer", "input": {"action": "screenshot"}}

event: tool_result
data: {"tool_id": "toolu_02Def...", "has_screenshot": true}

event: done
data: {"status": "completed"}
```

### 6.5 Debug Display Allocation

```bash
# Inside the container:

# List all X displays
ls -la /tmp/.X*-lock

# Check which ports are listening
ss -tlnp | grep -E "5810|5811|5910|5911"

# Manually take a screenshot on a specific display
DISPLAY=:100 scrot /tmp/test_screenshot.png
```

### 6.6 Debug Database

```bash
# Inside the container:

# Open the database
sqlite3 /data/sessions.db

# See all active sessions with their displays
SELECT id, title, status, display_num, vnc_port FROM sessions WHERE status != 'completed';

# Count messages per session
SELECT session_id, COUNT(*) as msg_count FROM messages GROUP BY session_id;

# Find error messages
SELECT * FROM messages WHERE content LIKE '%error%' ORDER BY created_at DESC LIMIT 10;

# Check DB file size
ls -lh /data/sessions.db
```

### 6.7 Common Debug Workflow

When something goes wrong with an agent task:

1. **Check the health endpoint**: `curl http://localhost:8000/health` — verify the server is up and pool is healthy
2. **Check session status**: `curl http://localhost:8000/api/sessions/SESSION_ID` — look at `status` field
3. **Check logs**: `docker compose logs -f | grep SESSION_ID_PREFIX`
4. **Check SSE stream**: `curl -N http://localhost:8000/api/sessions/SESSION_ID/stream` — look for `error` events
5. **Check display**: Verify the VNC port is accessible and Xvfb is running
6. **Check DB**: Verify messages are being persisted correctly

---

## 7. Adding New Tools

To add a new tool that the AI agent can use:

### Step 1: Create the Tool Class

```python
# computer_use_demo/tools/my_tool.py
from typing import Literal
from .base import BaseAnthropicTool, ToolResult, ToolError

class MyTool(BaseAnthropicTool):
    api_type: Literal["my_tool_20250101"] = "my_tool_20250101"
    name: Literal["my_tool"] = "my_tool"

    def to_params(self):
        return {
            "type": self.api_type,
            "name": self.name,
        }

    async def __call__(self, *, param1: str, param2: int = 0, **kwargs):
        try:
            result = do_something(param1, param2)
            return ToolResult(output=result)
        except Exception as e:
            raise ToolError(str(e))
```

### Step 2: Register in a ToolGroup

```python
# computer_use_demo/tools/groups.py
from .my_tool import MyTool

TOOL_GROUPS: list[ToolGroup] = [
    ToolGroup(
        version="computer_use_20250124",
        tools=[ComputerTool20250124, EditTool20250728, BashTool20250124, MyTool],
        beta_flag="computer-use-2025-01-24",
    ),
    # ...
]
```

### Step 3: Export from `__init__.py`

```python
# computer_use_demo/tools/__init__.py
from .my_tool import MyTool
```

---

## 8. Adding New API Endpoints

### Step 1: Create the Route Module

```python
# computer_use_demo/api/routes/my_feature.py
from fastapi import APIRouter, HTTPException
from computer_use_demo.schemas import MyRequest, MyResponse

router = APIRouter(prefix="/api/my-feature", tags=["my-feature"])

@router.post("", response_model=MyResponse, status_code=201)
async def create_thing(request: MyRequest):
    # Business logic goes in a service, not here
    result = await my_service.do_something(request.param)
    return MyResponse(id=result["id"])
```

### Step 2: Define Schemas

```python
# computer_use_demo/schemas/my_feature.py
from pydantic import BaseModel, Field

class MyRequest(BaseModel):
    param: str = Field(..., min_length=1, description="...")

class MyResponse(BaseModel):
    id: str
```

### Step 3: Register the Router

```python
# computer_use_demo/api/app.py
from .routes import sessions, agent, vm, files, my_feature

app.include_router(my_feature.router)
```
