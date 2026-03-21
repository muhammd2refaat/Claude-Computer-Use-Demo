# Computer Use Agent - Backend API

**Author: Muhammed Refaat**

A production-ready FastAPI backend for Claude Computer Use agent sessions with real-time streaming, concurrent session support, and a modern web frontend.
---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Layered Service Architecture](#layered-service-architecture)
4. [Features](#features)
5. [Quick Start](#quick-start)
6. [API Documentation](#api-documentation)
7. [Sequence Diagrams](#sequence-diagrams)
8. [Concurrency Model](#concurrency-model)
9. [Frontend](#frontend)
10. [Development](#development)
11. [Configuration](#configuration)
12. [Evaluation Results](#evaluation-results)

---

## Overview

This project transforms the Anthropic Computer Use demo into a robust, production-ready backend API system. It removes the experimental Streamlit layer and implements:

- **FastAPI Backend**: RESTful endpoints for session management
- **SSE Streaming**: Real-time progress updates from the agent
- **Dynamic Display Allocation**: Each session gets its own virtual X11 display (unlimited)
- **True Concurrency**: Multiple sessions can run simultaneously without blocking
- **Database Persistence**: SQLite with connection pooling for sessions and messages
- **Modern Frontend**: Clean HTML/CSS/JS interface with VNC integration
- **Multi-LLM Support**: Works with Claude (Anthropic) or Gemini (Google)
- **Layered Architecture**: Clean separation between API, Services, and Infrastructure

---

## Architecture

### High-Level System Architecture

```
+------------------+         +-------------------+         +------------------+
|                  |   API   |                   |   VNC   |                  |
|  Web Frontend    | <-----> |  FastAPI Backend  | <-----> |  Virtual Desktop |
|  (HTML/JS/CSS)   |   SSE   |                   |         |  (Xvfb + VNC)    |
+------------------+         +-------------------+         +------------------+
                                      |
                                      v
                             +-------------------+
                             |                   |
                             |  SQLite Database  |
                             |  (Connection Pool)|
                             +-------------------+
                                      |
                                      v
                             +-------------------+
                             |                   |
                             |  LLM API          |
                             |  (Claude)  |
                             +-------------------+
```

---

## Layered Service Architecture

### Directory Structure and responsibilities:

```
computer-use-demo/
├── computer_use_demo/
│   │
│   ├── api/                           # API Layer (HTTP only)
│   │   ├── app.py                     # FastAPI application setup
│   │   ├── routes/
│   │   │   ├── sessions.py            # Session CRUD endpoints
│   │   │   ├── agent.py               # Message & SSE streaming
│   │   │   ├── vm.py                  # VNC connection info
│   │   │   └── files.py               # File operations
│   │   ├── database.py                # (deprecated - re-exports from db/)
│   │   ├── session_manager.py         # (deprecated - re-exports from services/)
│   │   ├── display_manager.py         # (deprecated - re-exports from services/)
│   │   └── models.py                  # (deprecated - re-exports from schemas/)
│   │
│   ├── config/                        # Configuration Layer
│   │   ├── __init__.py
│   │   └── settings.py                # Centralized environment settings
│   │
│   ├── core/                          # Core Infrastructure Layer
│   │   ├── __init__.py
│   │   └── events/
│   │       ├── __init__.py
│   │       └── publisher.py           # SSE Event publishing system
│   │
│   ├── db/                            # Database Layer
│   │   ├── __init__.py                # Exports all DB functions
│   │   ├── database.py                # Connection pooling (2-10 connections)
│   │   └── repository.py              # CRUD operations
│   │
│   ├── schemas/                       # Data Models Layer (Pydantic)
│   │   ├── __init__.py
│   │   ├── session.py                 # Session request/response models
│   │   ├── message.py                 # Message models
│   │   ├── event.py                   # SSE event models
│   │   └── models.py                  # Unified models file
│   │
│   ├── services/                      # Business Logic Layer
│   │   ├── __init__.py
│   │   │
│   │   ├── session/                   # Session Management
│   │   │   ├── __init__.py
│   │   │   ├── active_session.py      # ActiveSession dataclass (runtime state)
│   │   │   └── session_service.py     # Session lifecycle (create, delete, restore)
│   │   │
│   │   ├── agent/                     # Agent Execution
│   │   │   ├── __init__.py
│   │   │   ├── agent_service.py       # Agent orchestration (send_message, stop)
│   │   │   └── agent_runner.py        # Agent loop execution (LLM + tools)
│   │   │
│   │   └── display/                   # Display Management
│   │       ├── __init__.py
│   │       └── display_service.py     # Dynamic Xvfb/VNC allocation
│   │
│   ├── tools/                         # Computer Use Tools
│   │   ├── __init__.py
│   │   ├── base.py                    # Base tool classes
│   │   ├── collection.py              # ToolCollection
│   │   ├── groups.py                  # Tool version groupings
│   │   ├── bash.py                    # Bash shell tool
│   │   ├── computer.py                # Mouse/keyboard/screen tool
│   │   └── edit.py                    # File editor tool
│   │
│   ├── utils/                         # Shared Utilities
│   │   ├── __init__.py
│   │   └── logger.py                  # Centralized logging
│   │
│   └── loop.py                        # Core agent sampling loop
│
├── frontend/                          # Web UI
│   ├── index.html
│   ├── app.js
│   └── style.css
│
├── tests/                             # Test Suite
│   ├── conftest.py
│   ├── tools/
│   │   ├── bash_test.py
│   │   ├── computer_test.py
│   │   └── edit_test.py
│   └── streamlit_test.py
│
├── docker-compose.yml
├── Dockerfile
├── CODE_ANALYSIS_REPORT.md
├── EVALUATION_REPORT.md
└── README.md
```

### Layer Responsibilities

| Layer | Directory | Responsibility |
|-------|-----------|----------------|
| **API** | `api/` | HTTP routes, request/response handling |
| **Config** | `config/` | Environment variables, settings |
| **Core** | `core/` | Infrastructure (event publishing) |
| **Database** | `db/` | Connection pooling, CRUD operations |
| **Schemas** | `schemas/` | Pydantic models, data contracts |
| **Services** | `services/` | Business logic, orchestration |
| **Tools** | `tools/` | Computer Use tool implementations |
| **Utils** | `utils/` | Shared utilities (logging) |

### Service Layer Detail

```
services/
├── session/
│   ├── active_session.py     # 37 lines  - Runtime session state dataclass
│   └── session_service.py    # 229 lines - Session lifecycle management
│
├── agent/
│   ├── agent_service.py      # 108 lines - Agent orchestration
│   └── agent_runner.py       # 325 lines - Agent loop execution
│
└── display/
    └── display_service.py    # 294 lines - Virtual display management
```

**Benefits of architecture:**
- ✅ Single Responsibility Principle
- ✅ Easy to test individual components
- ✅ Clear dependency injection points
- ✅ Reusable service layer
- ✅ No circular dependencies

---

## Features

### Core Features

| Feature | Description | Implementation |
|---------|-------------|----------------|
| **Session Management** | Create, list, delete agent task sessions | `services/session/` |
| **Real-time Streaming** | SSE-based progress updates for tool calls | `core/events/publisher.py` |
| **VNC Integration** | Per-session virtual desktop via noVNC | `services/display/` |
| **Database Persistence** | SQLite with connection pooling (WAL mode) | `db/database.py` |
| **Concurrent Sessions** | True parallel execution with dynamic displays | `asyncio.create_task()` |
| **Multi-LLM Support** | Works with Claude (Anthropic) or Gemini (Google) | `services/agent/` |

### Concurrency Features (Critical)

| Feature | Status | Implementation |
|---------|--------|----------------|
| **True Parallelism** | ✅ | `asyncio.create_task()` per agent |
| **No Hardcoded Limits** | ✅ | Dynamic display allocation |
| **Race Condition Prevention** | ✅ | 4 `asyncio.Lock()` mechanisms |
| **Non-Blocking** | ✅ | Second request starts immediately |
| **Resource Isolation** | ✅ | Separate Xvfb/VNC per session |

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/sessions` | Create a new session |
| `GET` | `/api/sessions` | List all sessions |
| `GET` | `/api/sessions/{id}` | Get session details |
| `DELETE` | `/api/sessions/{id}` | Delete a session |
| `POST` | `/api/sessions/{id}/messages` | Send a message to agent |
| `GET` | `/api/sessions/{id}/messages` | Get chat history |
| `GET` | `/api/sessions/{id}/stream` | SSE event stream |
| `POST` | `/api/sessions/{id}/stop` | Stop running agent |
| `POST` | `/api/sessions/{id}/restore` | Restore session from DB |
| `GET` | `/api/sessions/{id}/vnc` | Get VNC connection info |
| `GET` | `/health` | Health check with pool stats |
| `GET` | `/docs` | Swagger UI documentation |

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Anthropic API Key or Google Gemini API Key

### 1. Clone and Configure

```bash
cd computer-use-demo

# Copy environment template
cp .env.example .env

# Edit .env and add your API key
# For Anthropic Claude:
ANTHROPIC_API_KEY=sk-ant-...



### 2. Build and Run

```bash
# Build and start the container
docker compose up --build

# Or run in detached mode
docker compose up --build -d
```

### 3. Access the Application

- **Frontend UI**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 4. Multi-Tenant Demonstration

1. Open two side-by-side browser windows to `http://localhost:8000`
2. Click **"New Task"** in both windows to spawn two separate virtual desktops
3. Give them both commands simultaneously:
   - Window A: "Search weather in Tokyo"
   - Window B: "Search weather in New York"
4. Watch both Agent loops stream tool progress in real-time, completely independently
5. Verify two separate Firefox automation windows are running simultaneously

---

## API Documentation

### Create Session

```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "Weather Search Task"}'
```

**Response (201 Created):**
```json
{
  "id": "abc123...",
  "title": "Weather Search Task",
  "status": "created",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "vnc_info": {
    "display_num": 100,
    "vnc_port": 5910,
    "novnc_url": "/vnc/?port=5910&autoconnect=true&resize=scale"
  }
}
```

### Send Message

```bash
curl -X POST http://localhost:8000/api/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"text": "Search the weather in Dubai"}'
```

**Response (202 Accepted):**
```json
{
  "message_id": "msg123...",
  "status": "processing"
}
```

### List Sessions

```bash
curl http://localhost:8000/api/sessions
```

**Response:**
```json
{
  "sessions": [
    {
      "id": "abc123...",
      "title": "Weather Search Task",
      "status": "idle",
      "vnc_info": {
        "display_num": 100,
        "vnc_port": 5910,
        "novnc_url": "/vnc/?port=5910&autoconnect=true&resize=scale"
      }
    }
  ],
  "total": 1
}
```

### Get Chat History

```bash
curl http://localhost:8000/api/sessions/{session_id}/messages
```

**Response:**
```json
{
  "messages": [
    {
      "id": "msg1",
      "session_id": "abc123",
      "role": "user",
      "content": "Search the weather in Dubai",
      "created_at": "2024-01-15T10:30:00Z"
    },
    {
      "id": "msg2",
      "session_id": "abc123",
      "role": "assistant",
      "content": {"type": "text", "text": "I'll search for the weather in Dubai..."},
      "created_at": "2024-01-15T10:30:05Z"
    }
  ],
  "total": 2
}
```

### SSE Stream Events

Connect to the SSE endpoint to receive real-time updates:

```javascript
const eventSource = new EventSource('/api/sessions/{session_id}/stream');

eventSource.addEventListener('text', (e) => {
  console.log('Agent text:', JSON.parse(e.data).text);
});

eventSource.addEventListener('thinking', (e) => {
  console.log('Agent thinking:', JSON.parse(e.data).thinking);
});

eventSource.addEventListener('tool_use', (e) => {
  console.log('Tool call:', JSON.parse(e.data));
});

eventSource.addEventListener('tool_result', (e) => {
  console.log('Tool result:', JSON.parse(e.data));
});

eventSource.addEventListener('status', (e) => {
  console.log('Status:', JSON.parse(e.data).status);
});

eventSource.addEventListener('error', (e) => {
  console.error('Error:', JSON.parse(e.data).message);
});

eventSource.addEventListener('done', () => {
  console.log('Task completed');
  eventSource.close();
});
```

### SSE Event Types

| Event | Description | Data |
|-------|-------------|------|
| `text` | Agent text response | `{"text": "..."}` |
| `thinking` | Agent thinking content | `{"thinking": "..."}` |
| `tool_use` | Tool invocation | `{"tool_id": "...", "name": "...", "input": {...}}` |
| `tool_result` | Tool execution result | `{"tool_id": "...", "output": "...", "has_screenshot": true}` |
| `status` | Status change | `{"status": "running"}` |
| `error` | Error occurred | `{"message": "..."}` |
| `done` | Agent loop completed | `{"status": "completed"}` |

### Health Check

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "active_sessions": 2,
  "database": {
    "pool_size": 2,
    "available": 2,
    "in_use": 0,
    "max_size": 10,
    "total_acquired": 238,
    "health_checks": 239
  }
}
```

---

## Sequence Diagrams

### Session Creation Flow

```
┌────────┐          ┌───────────────┐          ┌────────────────┐          ┌──────────┐
│ Client │          │ SessionService│          │ DisplayService │          │ Database │
└───┬────┘          └──────┬────────┘          └───────┬────────┘          └────┬─────┘
    │                      │                           │                        │
    │  POST /api/sessions  │                           │                        │
    │─────────────────────>│                           │                        │
    │                      │                           │                        │
    │                      │   allocate_display()      │                        │
    │                      │──────────────────────────>│                        │
    │                      │                           │                        │
    │                      │                           │ async with _lock:      │
    │                      │                           │ display_num = 100      │
    │                      │                           │ Start Xvfb :100        │
    │                      │                           │─────────────────┐      │
    │                      │                           │<────────────────┘      │
    │                      │                           │                        │
    │                      │                           │ Start x11vnc :5910     │
    │                      │                           │─────────────────┐      │
    │                      │                           │<────────────────┘      │
    │                      │                           │                        │
    │                      │                           │ Start websockify :5920 │
    │                      │                           │─────────────────┐      │
    │                      │                           │<────────────────┘      │
    │                      │                           │                        │
    │                      │   DisplayAllocation       │                        │
    │                      │<──────────────────────────│                        │
    │                      │                           │                        │
    │                      │   async with _env_lock:   │                        │
    │                      │   _create_tools(display)  │                        │
    │                      │──────────────┐            │                        │
    │                      │<─────────────┘            │                        │
    │                      │                           │                        │
    │                      │            create_session()                        │
    │                      │───────────────────────────────────────────────────>│
    │                      │                                                    │
    │                      │            session record                          │
    │                      │<───────────────────────────────────────────────────│
    │                      │                           │                        │
    │   201 Created        │                           │                        │
    │   SessionResponse    │                           │                        │
    │<─────────────────────│                           │                        │
    │                      │                           │                        │
```

### Agent Message Flow

```
┌────────┐          ┌───────────────┐          ┌────────────────┐          ┌─────────┐
│ Client │          │ AgentService  │          │ AgentRunner    │          │ LLM API │
└───┬────┘          └──────┬────────┘          └───────┬────────┘          └────┬────┘
    │                      │                           │                        │
    │  POST /messages      │                           │                        │
    │─────────────────────>│                           │                        │
    │                      │                           │                        │
    │                      │  asyncio.create_task()    │                        │
    │                      │──────────────────────────>│                        │
    │                      │                           │  (runs in background)  │
    │  202 Accepted        │                           │                        │
    │<─────────────────────│                           │                        │
    │                      │                           │                        │
    │  GET /stream (SSE)   │                           │                        │
    │─────────────────────>│                           │                        │
    │                      │                           │                        │
    │                      │                           │   API Call             │
    │                      │                           │──────────────────────> │
    │                      │                           │                        │
    │                      │                           │   Response + tools     │
    │                      │                           │<───────────────────────│
    │                      │                           │                        │
    │  SSE: text           │     _push_event()         │                        │
    │<═══════════════════════════════════════════════─│                        │
    │                      │                           │                        │
    │  SSE: tool_use       │      Execute tool         │                        │
    │<═══════════════════════════════════════════════─│                        │
    │                      │                           │                        │
    │  SSE: tool_result    │                           │                        │
    │<═══════════════════════════════════════════════─│                        │
    │                      │                           │                        │
    │                      │                           │   [Loop continues...]  │
    │                      │                           │                        │
    │  SSE: done           │                           │                        │
    │<═══════════════════════════════════════════════─│                        │
    │                      │                           │                        │
```

### Concurrent Sessions Flow (Critical)

```
┌──────────┐     ┌──────────┐     ┌───────────────┐     ┌────────────────┐
│ Client A │     │ Client B │     │ SessionService│     │ DisplayService │
└────┬─────┘     └────┬─────┘     └──────┬────────┘     └───────┬────────┘
     │                │                   │                      │
     │  Create Session A                  │                      │
     │───────────────────────────────────>│                      │
     │                │                   │                      │
     │                │                   │  async with _lock:   │
     │                │                   │  allocate_display()  │
     │                │                   │─────────────────────>│
     │                │                   │                      │
     │                │                   │  Display :100        │
     │                │                   │<─────────────────────│
     │                │                   │                      │
     │  Session A (display :100, vnc 5910)│                      │
     │<───────────────────────────────────│                      │
     │                │                   │                      │
     │                │  Create Session B │                      │
     │                │──────────────────>│                      │
     │                │                   │                      │
     │                │                   │  async with _lock:   │
     │                │                   │  allocate_display()  │
     │                │                   │─────────────────────>│
     │                │                   │                      │
     │                │                   │  Display :101        │
     │                │                   │<─────────────────────│
     │                │                   │                      │
     │                │  Session B (:101, vnc 5911)              │
     │                │<──────────────────│                      │
     │                │                   │                      │
     │  Send message to A (Tokyo)         │                      │
     │───────────────────────────────────>│                      │
     │                │                   │                      │
     │                │                   │  create_task(agent A)│
     │                │                   │─────────────────────>│
     │                │                   │  (non-blocking!)     │
     │  202 Accepted  │                   │                      │
     │<───────────────────────────────────│                      │
     │                │                   │                      │
     │                │  Send message to B (NYC)                 │
     │                │──────────────────>│                      │
     │                │                   │                      │
     │                │                   │  create_task(agent B)│
     │                │                   │─────────────────────>│
     │                │                   │  (starts immediately!)│
     │                │  202 Accepted     │                      │
     │                │<──────────────────│                      │
     │                │                   │                      │
     │  SSE: Agent A working on :100      │                      │
     │<═══════════════════════════════════│                      │
     │                │                   │                      │
     │                │  SSE: Agent B working on :101            │
     │                │<══════════════════│                      │
     │                │                   │                      │
     │    [Both agents run SIMULTANEOUSLY with isolated Firefox] │
     │                │                   │                      │
```

---

## Concurrency Model

### How Concurrent Sessions Work

1. **Dynamic Display Allocation**: Each session gets its own virtual X11 display (`:100`, `:101`, etc.) via `DisplayService`

2. **Isolated Processes**: Per session, we spawn:
   - `Xvfb` - Virtual framebuffer
   - `mutter` - Window manager
   - `tint2` - Taskbar
   - `x11vnc` - VNC server
   - `websockify` - WebSocket proxy for noVNC

3. **Async Agent Execution**: Agent loops run as `asyncio.Task` instances, allowing true parallel execution

4. **No Hardcoded Limits**: The system dynamically allocates displays starting from `:100`, with no fixed upper bound

5. **Thread-Safe State**: All shared state is protected by multiple `asyncio.Lock` instances

### Lock Mechanisms (Race Condition Prevention)

```python
# 1. Display Allocation Lock
class DisplayService:
    def __init__(self):
        self._lock = asyncio.Lock()

    async def allocate_display(self):
        async with self._lock:  # Atomic display number assignment
            display_num = self._next_display
            self._next_display += 1

# 2. Session Registry Lock
class SessionService:
    def __init__(self):
        self._lock = asyncio.Lock()

    async def create_session(self):
        async with self._lock:  # Protect active_sessions dict
            self._active_sessions[session_id] = active

# 3. Environment Lock (Critical for tool creation)
class SessionService:
    def __init__(self):
        self._env_lock = asyncio.Lock()

    async def _create_tools_for_display(self, display_num):
        async with self._env_lock:  # Safe os.environ manipulation
            os.environ["DISPLAY_NUM"] = str(display_num)
            tool_collection = ToolCollection(...)
            # Restore immediately

# 4. Database Pool Lock
class ConnectionPool:
    def __init__(self):
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:  # Atomic connection acquisition
            return await self._pool.get()
```

### Code Example: Parallel Agent Tasks

```python
# Each message triggers a new async task (non-blocking)
# File: services/agent/agent_service.py

async def send_message(self, session_id: str, text: str) -> str:
    active = session_service.get_active_session(session_id)

    # Launch agent loop as a BACKGROUND TASK
    active.agent_task = asyncio.create_task(
        agent_runner.run_agent_loop(active),
        name=f"agent-{session_id[:8]}",
    )

    # Returns IMMEDIATELY - task runs independently!
    return msg["id"]
```

### Dynamic System Prompt per Display

```python
# File: services/agent/agent_runner.py

# Each session gets its display in the system prompt
dynamic_system_prompt = SYSTEM_PROMPT.replace(
    "DISPLAY=:1",  # Original hardcoded value
    f"DISPLAY=:{active.display.display_num}"  # Dynamic per session
)
```

---

## Frontend

The frontend is a clean HTML/CSS/JavaScript application with:

- **Left Sidebar**: Task history with session list
- **Middle Panel**: VNC viewer showing the virtual desktop
- **Right Panel**: Real-time chat with SSE streaming

### Key Features

- Real-time SSE event display
- noVNC iframe integration
- Responsive design
- Dark theme UI

### Streamlit-like Behavior

- When a task is submitted, the AI agent streams real-time progress for each intermediate step
- Tool calls are displayed with input parameters
- Tool results show output or errors
- Once the task is complete, the UI prompts the user to enter a new task

---

## Development

### Running Locally (Without Docker)

```bash
# Install dependencies
pip install -r computer_use_demo/requirements.txt

# Set environment variables
export ANTHROPIC_API_KEY=sk-ant-...


# Run the API server
python -m uvicorn computer_use_demo.api.app:app --reload --port 8000
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/ -v
```

### Docker Build

```bash
# Build the image
docker build -t computer-use-api .

# Run the container
docker run -p 8000:8000 -p 6080:6080 -p 5910-5999:5910-5999 \
  -e ANTHROPIC_API_KEY=your-key \
  computer-use-api
```

---

## Configuration

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Yes* | Anthropic Claude API key | - |
| `GEMINI_API_KEY` | Yes* | Google Gemini API key (alternative) | - |
| `ANTHROPIC_BASE_URL` | No | Custom API endpoint | - |
| `ANTHROPIC_MODEL` | No | Model to use | `claude-sonnet-4-5-20250929` |
| `WIDTH` | No | Display width | `1024` |
| `HEIGHT` | No | Display height | `768` |
| `DB_PATH` | No | Database file path | `/data/sessions.db` |
| `DB_POOL_MIN_SIZE` | No | Min pool connections | `2` |
| `DB_POOL_MAX_SIZE` | No | Max pool connections | `10` |
| `LOG_LEVEL` | No | Logging level | `INFO` |

*At least one API key is required (either Anthropic or Gemini)

### Docker Compose Configuration

The `docker-compose.yml` exposes:

- Port `8000`: FastAPI backend + frontend
- Port `6080`: Default noVNC display
- Ports `5910-5999`: Dynamic VNC ports for concurrent sessions

---


### Key Achievements

- ✅ **True Parallelism** - No queuing, unlimited concurrent sessions
- ✅ **Dynamic Allocation** - No hardcoded display/port limits
- ✅ **Race Condition Prevention** - 4 lock mechanisms
- ✅ **Clean Architecture** - Layered service-oriented design
- ✅ **Production Ready** - Connection pooling, error handling, logging

### Full Reports

- [CODE_ANALYSIS_REPORT.md](./CODE_ANALYSIS_REPORT.md) - Technical deep dive
- [EVALUATION_REPORT.md](./EVALUATION_REPORT.md) - Comprehensive evaluation

---



## License

This project extends the [Anthropic Computer Use Demo](https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo) with a production-ready API layer.

---


### Docker Build Issues

```bash
# Clean build
docker compose down -v
docker compose build --no-cache
docker compose up
```

### API Key Issues

```bash
# Verify API key is set
docker exec computer-use-demo-computer-use-1 env | grep API_KEY
```

### Port Conflicts

```bash
# Check if ports are in use
lsof -i :8000
lsof -i :5910
```

### Check Logs

```bash
# View container logs
docker logs computer-use-demo-computer-use-1

# View application logs
docker exec computer-use-demo-computer-use-1 tail -100 /tmp/api_stdout.log
```

---

