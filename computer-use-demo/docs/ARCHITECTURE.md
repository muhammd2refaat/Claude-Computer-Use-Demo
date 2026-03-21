# Architecture

> Deep-dive into system design, component responsibilities, data flow, and external integrations.

---

## Table of Contents

1. [System Design Philosophy](#1-system-design-philosophy)
2. [Layered Architecture](#2-layered-architecture)
3. [Component Breakdown](#3-component-breakdown)
4. [Data Flow](#4-data-flow)
5. [Concurrency Model](#5-concurrency-model)
6. [Database Design](#6-database-design)
7. [External Integrations](#7-external-integrations)
8. [Process Model Inside the Container](#8-process-model-inside-the-container)
9. [Security Considerations](#9-security-considerations)

---

## 1. System Design Philosophy

This system follows several core architectural principles:

| Principle | Implementation |
|---|---|
| **Single Responsibility** | Each service layer has exactly one concern — routes handle HTTP, services handle business logic, DB handles persistence |
| **Dependency Inversion** | Services depend on abstractions (`ToolCollection`, `ConnectionPool`) not concrete implementations |
| **Event-Driven Communication** | Agent progress is published via an in-process pub/sub (`EventPublisher` → `asyncio.Queue` → SSE generator) |
| **Resource Isolation** | Each session owns its display stack, tool instances, and event queue — no shared mutable state between sessions |
| **Graceful Degradation** | Tool errors are captured and streamed as `error` events; they don't crash the agent loop |

---

## 2. Layered Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      API Layer (api/)                        │
│  Routes: sessions.py, agent.py, vm.py, files.py             │
│  Concern: HTTP request parsing, validation, response shapes │
├──────────────────────────────────────────────────────────────┤
│                   Schemas Layer (schemas/)                    │
│  Pydantic models: session.py, message.py, event.py, models.py│
│  Concern: Data contracts, enums, validation rules            │
├──────────────────────────────────────────────────────────────┤
│                  Service Layer (services/)                    │
│  session/ → SessionService (lifecycle, tool creation)        │
│  agent/   → AgentService (orchestration), AgentRunner (loop) │
│  display/ → DisplayService (Xvfb/VNC allocation)             │
│  Concern: Business logic, orchestration, state management    │
├──────────────────────────────────────────────────────────────┤
│                    Core Layer (core/)                         │
│  events/publisher.py → EventPublisher                        │
│  Concern: Infrastructure primitives (pub/sub, cross-cutting) │
├──────────────────────────────────────────────────────────────┤
│                     Tools Layer (tools/)                      │
│  computer.py, bash.py, edit.py, collection.py, groups.py     │
│  Concern: LLM tool implementations (Anthropic protocol)      │
├──────────────────────────────────────────────────────────────┤
│                  Database Layer (db/)                         │
│  database.py → ConnectionPool, schema init                   │
│  repository.py → CRUD operations (sessions, messages)        │
│  Concern: Persistence, connection lifecycle, SQL queries      │
├──────────────────────────────────────────────────────────────┤
│                   Config Layer (config/)                      │
│  settings.py → Settings dataclass (env vars)                 │
│  Concern: Centralized configuration, environment abstraction │
├──────────────────────────────────────────────────────────────┤
│                   Utils Layer (utils/)                        │
│  logger.py → setup_logger(), get_logger()                    │
│  Concern: Cross-cutting utilities                            │
└──────────────────────────────────────────────────────────────┘
```

### Dependency Direction

Dependencies flow **downward only** — the API layer imports from Services, Services import from DB/Core/Tools, none of them import upward. The exception is a single deferred import in `AgentService` where `event_publisher` is imported inline to avoid circular dependency.

---

## 3. Component Breakdown

### 3.1 API Layer (`api/`)

#### `app.py` — FastAPI Application Entry Point

- Registers all route modules via `include_router()`
- Configures CORS middleware (currently permissive `allow_origins=["*"]` for development)
- Defines the `lifespan` context manager for startup/shutdown:
  - **Startup**: Creates `/data` directory, initializes DB schema and connection pool
  - **Shutdown**: Calls `session_service.shutdown()` (cancels all tasks, releases displays), `display_service.release_all()`, `db.close_db()`
- Mounts static file directories: `/vnc` → noVNC static files, `/static` → frontend files
- Serves the main frontend at `GET /` and a concurrent test page at `GET /test`

#### `routes/sessions.py` — Session CRUD

| Endpoint | Handler | Service Call |
|---|---|---|
| `POST /api/sessions` | `create_session()` | `session_service.create_session(title)` |
| `GET /api/sessions` | `list_sessions()` | `session_service.list_sessions()` |
| `GET /api/sessions/{id}` | `get_session()` | `session_service.get_session_info(id)` |
| `DELETE /api/sessions/{id}` | `delete_session()` | `session_service.delete_session(id)` |

HTTP-only concerns: maps DB dicts to `SessionResponse` Pydantic models, constructs `VNCInfo` with `novnc_url` for browser iframe embedding.

#### `routes/agent.py` — Agent Interaction & SSE

| Endpoint | Handler | Notes |
|---|---|---|
| `POST .../messages` | `send_message()` | Returns `202 Accepted`; agent runs in background |
| `GET .../messages` | `get_messages()` | Returns persisted chat history from DB |
| `GET .../stream` | `stream_events()` | SSE endpoint using `EventSourceResponse`. Auto-restores sessions if not in memory. |
| `POST .../stop` | `stop_agent()` | Cancels `asyncio.Task` |
| `POST .../restore` | `restore_session()` | Rehydrates from DB with fresh display |

The SSE generator (`event_generator()`) reads from `active.event_queue` and yields `{event, data}` dicts. It checks `request.is_disconnected()` on each iteration for clean client disconnect handling.

#### `routes/vm.py` — VNC Connection Info

Returns the WebSocket port and noVNC URL for a session's virtual display.

#### `routes/files.py` — File Operations

Provides endpoints for listing and downloading files from the agent's working directory inside the container.

#### `gemini_wrapper.py` — Gemini Protocol Translation

Acts as a **translation layer** between Anthropic's message format and Google's Gemini API:

- `_convert_messages_to_gemini()`: Converts `BetaMessageParam` → Gemini `contents` (handles `text`, `image`, `tool_use`, `tool_result` block types)
- `run_gemini_sampling()`: Makes a single Gemini API call with `functionDeclarations`, parses `functionCall` responses back into Anthropic-style `tool_use` blocks
- Gemini-specific system prompt nudge appended to encourage autonomous tool chaining

---

### 3.2 Service Layer (`services/`)

#### `session/session_service.py` — SessionService

**Singleton instance:** `session_service`

The central orchestrator for session lifecycle. Key responsibilities:

| Method | Purpose | Critical Details |
|---|---|---|
| `create_session()` | Full session bootstrap | Allocates display → creates DB record → creates tools → builds `ActiveSession` → registers in `_active_sessions` |
| `_create_tools_for_display()` | Thread-safe tool factory | **CRITICAL**: Uses `_env_lock` to atomically set `os.environ["DISPLAY_NUM"]`, construct tool instances, then restore env. This is necessary because `ComputerTool.__init__()` and `BashTool.__init__()` read from `os.environ` synchronously. |
| `delete_session()` | Full teardown | Cancels agent task → awaits task completion → releases display → signals SSE clients → deletes DB record |
| `restore_session()` | Post-restart rehydration | Allocates fresh display → updates DB → recreates tools → replays user messages from DB into Anthropic format |
| `shutdown()` | Graceful shutdown | Iterates all active sessions and deletes each |

**Lock inventory:**
- `_lock` (`asyncio.Lock`) — protects `_active_sessions` dict mutations
- `_env_lock` (`asyncio.Lock`) — protects `os.environ` manipulation during tool creation

#### `session/active_session.py` — ActiveSession

A `@dataclass` holding the **runtime state** for a live session:

```python
@dataclass
class ActiveSession:
    session_id: str
    display: DisplayAllocation          # Xvfb/VNC process info
    messages: list                      # Anthropic API message history (in-memory)
    event_queue: asyncio.Queue          # SSE event buffer
    tool_collection: ToolCollection     # Pre-created tools bound to this display
    agent_task: asyncio.Task | None     # Background agent loop task
    is_running: bool                    # Guard against double-sends
```

This dataclass is the **single source of truth** for all in-flight session state. It is created on `create_session()` and destroyed on `delete_session()`.

#### `agent/agent_service.py` — AgentService

**Singleton instance:** `agent_service`

Thin orchestration layer:

- `send_message()`: Guards against concurrent sends (`active.is_running`), persists user message to DB, appends to Anthropic message format, spawns `asyncio.create_task(agent_runner.run_agent_loop(active))`, returns immediately.
- `stop_agent()`: Cancels the background task, updates status.
- `get_event_stream()`: Async generator that yields from `active.event_queue` until `None` sentinel.

#### `agent/agent_runner.py` — AgentRunner

**Singleton instance:** `agent_runner`

The **heart of the system** — implements the Anthropic Computer Use sampling loop:

```
┌─────────────────────────────────────────────────────────┐
│                   Agent Sampling Loop                    │
│                                                         │
│  1. Construct dynamic system prompt (per-display)       │
│  2. Create Anthropic client with API key and config     │
│  3. Inject prompt caching + image truncation            │
│  4. Call LLM API (Anthropic or Gemini)                  │
│  5. Parse response → SSE events (text, thinking, tools) │
│  6. For each tool_use block:                            │
│     a. Execute tool via tool_collection.run()           │
│     b. Stream tool_result SSE event                     │
│     c. Persist to DB                                    │
│  7. If no tool calls → loop ends (agent is done)        │
│  8. Append tool_results as user message → goto step 3   │
└─────────────────────────────────────────────────────────┘
```

Key implementation details:

- **Pre-created tools**: Uses `active.tool_collection` (created at session creation time with correct `DISPLAY_NUM`), not the generic `loop.py` version. This avoids runtime env manipulation.
- **Dynamic system prompt**: Replaces hardcoded `DISPLAY=:1` with `DISPLAY=:{active.display.display_num}` so the agent's bash commands target the correct framebuffer.
- **Error isolation**: API errors, tool errors, and unexpected exceptions are all caught, streamed as `error` events, and logged — the agent loop fails gracefully without crashing the server.
- **Gemini branching**: Checks `settings.is_using_gemini()` and routes through `run_gemini_sampling()` when the API key is a Google key.

#### `display/display_service.py` — DisplayService

**Singleton instance:** `display_service`

Manages the full lifecycle of **per-session virtual display stacks**:

| Process | Port/Resource | Purpose |
|---|---|---|
| `Xvfb :{N}` | — | Virtual X11 framebuffer (1024×768×24, no network listeners) |
| `mutter --replace --sm-disable` | — | Compositing window manager (env: `DISPLAY=:{N}`) |
| `tint2 -c ~/.config/tint2/tint2rc` | — | Lightweight taskbar (env: `DISPLAY=:{N}`) |
| `x11vnc -display :{N} -forever -shared -rfbport {P}` | Port `P` (5810+) | VNC server exposing the framebuffer |
| `novnc_proxy --vnc localhost:{P} --listen {WS}` | Port `WS` (5910+) | WebSocket proxy for browser-based VNC |

**Process startup validation:**
- `Xvfb`: Polls for `/tmp/.X{N}-lock` file (up to 10 seconds)
- `x11vnc` & `websockify`: Polls TCP port availability via `asyncio.open_connection()` (up to 10 seconds)
- `mutter` / `tint2`: Fixed sleep delays (1.5s / 0.5s)

**Cleanup (`release_display`):**
- Kills processes in reverse order (`SIGTERM`)
- Removes X11 lock file (`/tmp/.X{N}-lock`)
- Frees port reservations from tracking sets

---

### 3.3 Core Layer (`core/`)

#### `events/publisher.py` — EventPublisher

**Singleton instance:** `event_publisher`

In-process pub/sub for SSE streaming:

```python
class EventPublisher:
    _event_queues: dict[str, asyncio.Queue]  # session_id → queue (optional registry)

    async def publish_to_queue(event_queue, event_type, data):
        # Directly enqueues {"type", "data", "timestamp"} dicts
```

In practice, `AgentRunner` calls `publish_to_queue()` directly with the session's `event_queue` reference, bypassing the registry lookup. The registry-based `publish()` is available for future use (e.g., admin broadcasts).

---

### 3.4 Tools Layer (`tools/`)

#### Tool Class Hierarchy

```
BaseAnthropicTool (abstract)
├── BaseComputerTool
│   ├── ComputerTool20241022
│   ├── ComputerTool20250124
│   └── ComputerTool20251124 (adds zoom)
├── BashTool20241022
├── BashTool20250124
└── EditTool20250728
```

#### `ToolCollection`

Aggregates multiple tool instances, provides:
- `to_params()` → Converts all tools to Anthropic API tool parameter format
- `run(name, tool_input)` → Dispatches to the correct tool by name, wraps `ToolError` into `ToolResult`

#### `ToolGroup`

Static configuration binding a tool version string to a set of tool classes and an API beta flag. Stored in `TOOL_GROUPS_BY_VERSION` dict for lookup.

#### Concurrency-Aware Tool Design

- **ComputerTool**: Reads `DISPLAY_NUM` from `os.environ` at `__init__` and caches `self._display_prefix = f"DISPLAY=:{display_num} "`. All shell commands (`xdotool`, `scrot`, `convert`) are prefixed with this.
- **BashTool**: Captures `DISPLAY`, `DISPLAY_NUM`, `WIDTH`, `HEIGHT` from env at `__init__` into `self._env_override`. The `_BashSession` subprocess is spawned with these overrides, ensuring shell commands target the correct display.
- **Key insight**: Tools are **created once per session** with the correct env, then their display binding is immutable. This is thread-safe.

---

### 3.5 Database Layer (`db/`)

#### `database.py` — ConnectionPool

Custom async connection pool for SQLite (aiosqlite):

```
┌─────────────────────────────────────────────────┐
│              ConnectionPool                      │
│                                                  │
│  asyncio.Queue[aiosqlite.Connection]             │
│  ├── Pre-creates min_size connections on init    │
│  ├── Grows up to max_size on demand              │
│  ├── Health checks before each acquire           │
│  ├── Automatic replacement of dead connections   │
│  ├── Timeout on acquire (configurable)           │
│  └── Statistics tracking for /health endpoint    │
│                                                  │
│  SQLite Configuration:                           │
│  ├── PRAGMA journal_mode=WAL                     │
│  ├── PRAGMA foreign_keys=ON                      │
│  ├── PRAGMA synchronous=NORMAL                   │
│  ├── PRAGMA cache_size=-64000 (64MB)             │
│  └── PRAGMA busy_timeout=30000 (30s)             │
└─────────────────────────────────────────────────┘
```

#### `repository.py` — CRUD Operations

Pure data access functions (no business logic):

| Function | Table | Operation |
|---|---|---|
| `create_session()` | `sessions` | INSERT with UUID, timestamps |
| `get_session()` | `sessions` | SELECT by ID |
| `list_sessions()` | `sessions` | SELECT all, ORDER BY created_at DESC |
| `update_session_status()` | `sessions` | UPDATE status + updated_at |
| `update_session_display()` | `sessions` | UPDATE display_num, vnc_port |
| `delete_session()` | `sessions` | DELETE (cascades to messages) |
| `add_message()` | `messages` | INSERT with JSON serialization |
| `get_messages()` | `messages` | SELECT by session_id, ORDER BY created_at ASC |

---

## 4. Data Flow

### 4.1 Session Creation

```
Client                    API Layer              SessionService           DisplayService           DB
  │                          │                        │                        │                    │
  │ POST /api/sessions       │                        │                        │                    │
  │─────────────────────────►│                        │                        │                    │
  │                          │ create_session(title)   │                        │                    │
  │                          │───────────────────────►│                        │                    │
  │                          │                        │ allocate_display()      │                    │
  │                          │                        │───────────────────────►│                    │
  │                          │                        │                        │ start Xvfb         │
  │                          │                        │                        │ start mutter        │
  │                          │                        │                        │ start tint2         │
  │                          │                        │                        │ start x11vnc        │
  │                          │                        │                        │ start websockify    │
  │                          │                        │ DisplayAllocation      │                    │
  │                          │                        │◄───────────────────────│                    │
  │                          │                        │                        │                    │
  │                          │                        │ _create_tools_for_display()                 │
  │                          │                        │──── async with _env_lock ────►              │
  │                          │                        │  set DISPLAY_NUM env                        │
  │                          │                        │  construct ToolCollection                    │
  │                          │                        │  restore env                                │
  │                          │                        │                        │                    │
  │                          │                        │ db.create_session()     │                    │
  │                          │                        │─────────────────────────────────────────────►│
  │                          │                        │ session record          │                    │
  │                          │                        │◄─────────────────────────────────────────────│
  │                          │                        │                        │                    │
  │                          │                        │ register ActiveSession  │                    │
  │                          │                        │──── async with _lock ────                    │
  │                          │                        │                        │                    │
  │                          │ SessionResponse         │                        │                    │
  │ 201 Created              │◄──────────────────────│                        │                    │
  │◄─────────────────────────│                        │                        │                    │
```

### 4.2 Agent Execution (Message Send → Tool Loop → Done)

```
Client                  AgentService           AgentRunner             LLM API            Tools
  │                          │                      │                      │                  │
  │ POST .../messages        │                      │                      │                  │
  │─────────────────────────►│                      │                      │                  │
  │                          │ persist user msg to DB│                      │                  │
  │                          │ append to messages[]  │                      │                  │
  │                          │ asyncio.create_task() │                      │                  │
  │                          │─────────────────────►│                      │                  │
  │ 202 Accepted             │  (non-blocking)       │                      │                  │
  │◄─────────────────────────│                      │                      │                  │
  │                          │                      │                      │                  │
  │ GET .../stream (SSE)     │                      │                      │                  │
  │═══════════════════════════════════════════════▶   │                      │                  │
  │                          │                      │                      │                  │
  │                          │                      │ create Anthropic client│                  │
  │                          │                      │ inject prompt caching  │                  │
  │                          │                      │ API call ─────────────►│                  │
  │                          │                      │                      │                  │
  │                          │                      │ response (text+tools) │                  │
  │                          │                      │◄─────────────────────│                  │
  │                          │                      │                      │                  │
  │ SSE: {type: "text"}      │                      │ _on_output() → push   │                  │
  │◄═══════════════════════════════════════════════─│                      │                  │
  │                          │                      │                      │                  │
  │ SSE: {type: "tool_use"}  │                      │ _on_output() → push   │                  │
  │◄═══════════════════════════════════════════════─│                      │                  │
  │                          │                      │                      │                  │
  │                          │                      │ tool_collection.run() │                  │
  │                          │                      │──────────────────────────────────────────►│
  │                          │                      │                      │  execute on :N   │
  │                          │                      │ ToolResult            │                  │
  │                          │                      │◄──────────────────────────────────────────│
  │                          │                      │                      │                  │
  │ SSE: {type:"tool_result"}│                      │ _on_tool_output()     │                  │
  │◄═══════════════════════════════════════════════─│                      │                  │
  │                          │                      │                      │                  │
  │                          │                      │ ── LOOP repeats ──    │                  │
  │                          │                      │                      │                  │
  │ SSE: {type: "done"}      │                      │ No more tool calls    │                  │
  │◄═══════════════════════════════════════════════─│                      │                  │
```

### 4.3 SSE Event Pipeline (Internal)

```
AgentRunner._on_output()──►EventPublisher.publish_to_queue()──►active.event_queue──►
                                                                                    │
    ┌───────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
agent_service.get_event_stream() (async generator)──►routes/agent.py event_generator()──►
                                                                                          │
    ┌─────────────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
EventSourceResponse──►HTTP SSE stream──►Browser EventSource API──►Frontend UI
```

---

## 5. Concurrency Model

### 5.1 Async Architecture

The entire system runs on a **single-threaded `asyncio` event loop** (Python 3.11, Uvicorn). Concurrency is cooperative, not preemptive:

- HTTP handler coroutines yield to the event loop on I/O (DB queries, HTTP calls, `asyncio.sleep`)
- Agent loops run as **detached `asyncio.Task` instances** — they don't block the HTTP handlers
- Tool execution (`xdotool`, `scrot`, etc.) uses `asyncio.create_subprocess_exec/shell` for non-blocking subprocess management

### 5.2 Lock Inventory

| Lock | Owner | Protects | Contention Notes |
|---|---|---|---|
| `DisplayService._lock` | `display_service` | `_next_display`, `_allocations`, port sets | Held briefly during allocation; no I/O inside critical section |
| `SessionService._lock` | `session_service` | `_active_sessions` dict | Held briefly for dict operations |
| `SessionService._env_lock` | `session_service` | `os.environ` during tool creation | **MOST CONTENTION-PRONE**: Serializes tool construction. If many sessions are created simultaneously, this becomes a bottleneck. |
| `ConnectionPool._lock` | DB pool | `_size` counter, pool initialization | Held during connection creation (I/O inside — could block briefly) |

### 5.3 Why `asyncio.Lock` and Not `threading.Lock`?

Since the entire app runs in one thread on one event loop, `asyncio.Lock` is sufficient. `threading.Lock` would be inappropriate — it would block the event loop thread, halting all concurrent coroutines.

### 5.4 Race Condition Prevention

```
Scenario: Two clients create sessions at the same time.

Without locks:
  Task A reads _next_display = 100
  Task B reads _next_display = 100  ← CONFLICT!
  Both spawn Xvfb on :100 → crash

With DisplayService._lock:
  Task A acquires lock → reads 100, increments to 101 → releases lock
  Task B acquires lock → reads 101, increments to 102 → releases lock
  ✅ No conflict
```

---

## 6. Database Design

### 6.1 Schema

```sql
CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,        -- UUID hex string
    title       TEXT NOT NULL,           -- Human-readable session name
    status      TEXT NOT NULL DEFAULT 'created',  -- Enum: created|running|idle|completed|error
    display_num INTEGER,                 -- Xvfb display number (e.g., 100)
    vnc_port    INTEGER,                 -- WebSocket port for noVNC (e.g., 5910)
    created_at  TEXT NOT NULL,           -- ISO 8601 UTC timestamp
    updated_at  TEXT NOT NULL            -- ISO 8601 UTC timestamp
);

CREATE TABLE messages (
    id          TEXT PRIMARY KEY,        -- UUID hex string
    session_id  TEXT NOT NULL,           -- FK → sessions.id (CASCADE delete)
    role        TEXT NOT NULL,           -- Enum: user|assistant|tool
    content     TEXT NOT NULL,           -- JSON string or plain text
    created_at  TEXT NOT NULL,           -- ISO 8601 UTC timestamp
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX idx_messages_session_id ON messages(session_id, created_at);
```

### 6.2 Data Storage Decisions

| Decision | Rationale |
|---|---|
| **SQLite over Postgres** | Single-container deployment; no external DB dependency. WAL mode provides adequate concurrent read/write performance. |
| **JSON content in messages** | Tool results and assistant responses have polymorphic shapes; JSON serialization avoids schema proliferation. |
| **No base64 images in DB** | Screenshots are streamed via SSE with `has_screenshot: true` flag but not persisted — saves significant disk space. The live VNC feed serves as the visual record. |
| **CASCADE delete** | Deleting a session automatically purges all its messages. |

### 6.3 Connection Pool Configuration

| Parameter | Default | Env Var |
|---|---|---|
| Min connections | 2 | `DB_POOL_MIN_SIZE` |
| Max connections | 10 | `DB_POOL_MAX_SIZE` |
| Acquire timeout | 30s | `DB_POOL_ACQUIRE_TIMEOUT` |

---

## 7. External Integrations

### 7.1 Anthropic Claude API

| Aspect | Detail |
|---|---|
| **SDK** | `anthropic` Python package (≥0.39.0) |
| **Endpoint** | Default: `https://api.anthropic.com`, configurable via `ANTHROPIC_BASE_URL` |
| **Model** | Default: `claude-sonnet-4-5-20250929`, configurable via `ANTHROPIC_MODEL` |
| **Auth** | API key in `ANTHROPIC_API_KEY` env var |
| **Features Used** | Beta tool use, prompt caching (`prompt-caching-2024-07-31`), extended thinking, token-efficient tools |
| **Retry Policy** | `max_retries=4` (SDK built-in exponential backoff) |
| **Tool Protocol** | Versioned: `computer_use_20241022`, `computer_use_20250124`, `computer_use_20250429`, `computer_use_20251124` |

### 7.2 Google Gemini API

| Aspect | Detail |
|---|---|
| **Protocol** | Direct HTTP via `httpx.AsyncClient` (no SDK) |
| **Endpoint** | `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent` |
| **Auth** | API key as URL query parameter |
| **Translation** | Custom `gemini_wrapper.py` converts Anthropic message format ↔ Gemini contents format |
| **Timeout** | 60 seconds per API call |
| **Tool Support** | `functionDeclarations` / `functionCall` / `functionResponse` |

### 7.3 noVNC / websockify

| Aspect | Detail |
|---|---|
| **noVNC** | v1.5.0, cloned into `/opt/noVNC` at build time |
| **websockify** | v0.12.0, used as `novnc_proxy` script |
| **Protocol** | Client connects via WebSocket on port `5910+N`, proxied to VNC on port `5810+N` |
| **Integration** | Frontend embeds `<iframe>` pointing to `/vnc/?port={ws_port}&autoconnect=true&resize=scale` |

---

## 8. Process Model Inside the Container

```
PID 1: entrypoint.sh
├── Xvfb :1 (default display)
├── tint2 (default taskbar)
├── mutter (default window manager)
├── x11vnc (default VNC on :5800)
├── novnc_proxy (default noVNC on :6080)
├── uvicorn (FastAPI on :8000)
│   └── asyncio event loop
│       ├── Session A agent task
│       │   └── tool subprocesses (xdotool, bash, scrot, firefox)
│       ├── Session B agent task
│       │   └── tool subprocesses
│       └── ... N concurrent tasks
├── Xvfb :100 (Session A display)
├── mutter (Session A)
├── tint2 (Session A)
├── x11vnc :5810 (Session A VNC)
├── novnc_proxy :5910 (Session A WebSocket)
├── Xvfb :101 (Session B display)
├── mutter (Session B)
├── ... etc.
└── tail -f /dev/null (keeps container alive)
```

---

## 9. Security Considerations

| Concern | Current State | Recommendation for Production |
|---|---|---|
| **API Authentication** | None — open access | Add JWT/API key auth middleware |
| **CORS** | `allow_origins=["*"]` | Restrict to known frontend origins |
| **Container Privileges** | `seccomp:unconfined`, `apparmor:unconfined` | Required for Xvfb/mutter. Isolate via network policies. |
| **API Key Exposure** | Keys passed via env vars | Use secrets manager (Vault, AWS Secrets Manager) |
| **Resource Limits** | Docker Compose: 4 CPU, 4GB RAM | Scale based on expected concurrent sessions (each session ≈ 5 processes) |
| **Input Sanitization** | Pydantic validation on requests | Agent bash commands are arbitrary by design — sandboxing is at the container level |
| **VNC Access** | No VNC authentication | Add VNC passwords or restrict ports via network policy |
