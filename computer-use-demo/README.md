# Computer Use Agent - Backend API

**Author: Muhammed Refaat**

A production-ready FastAPI backend for Claude Computer Use agent sessions with real-time streaming, concurrent session support, and a modern web frontend.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Features](#features)
4. [Quick Start](#quick-start)
5. [API Documentation](#api-documentation)
6. [Sequence Diagrams](#sequence-diagrams)
7. [Concurrency Model](#concurrency-model)
8. [Frontend](#frontend)
9. [Development](#development)
10. [Configuration](#configuration)

---

## Overview

This project transforms the Anthropic Computer Use demo into a robust, production-ready backend API system. It removes the experimental Streamlit layer and implements:

- **FastAPI Backend**: RESTful endpoints for session management
- **SSE Streaming**: Real-time progress updates from the agent
- **Dynamic Display Allocation**: Each session gets its own virtual X11 display
- **True Concurrency**: Multiple sessions can run simultaneously without blocking
- **Database Persistence**: SQLite storage for sessions and messages
- **Modern Frontend**: Clean HTML/CSS/JS interface with VNC integration
- **Multi-LLM Support**: Works with Claude (Anthropic) or Gemini (Google)

---

## Architecture

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
                             |                   |
                             +-------------------+
                                      |
                                      v
                             +-------------------+
                             |                   |
                             |  LLM API          |
                             |  (Claude/Gemini)  |
                             +-------------------+
```

### Directory Structure

```
computer-use-demo/
├── computer_use_demo/
│   ├── api/                        # FastAPI application
│   │   ├── app.py                  # Main FastAPI entry point
│   │   ├── database.py             # Async SQLite database layer
│   │   ├── display_manager.py      # Dynamic X11/VNC allocation
│   │   ├── session_manager.py      # Session lifecycle & agent loop
│   │   ├── gemini_wrapper.py       # Google Gemini API adapter
│   │   ├── models.py               # Pydantic request/response models
│   │   └── routes/
│   │       ├── sessions.py         # Session CRUD endpoints
│   │       ├── agent.py            # Message & SSE streaming
│   │       └── vm.py               # VNC connection info
│   │
│   ├── tools/                      # Computer Use tools
│   │   ├── base.py                 # Base tool classes
│   │   ├── collection.py           # ToolCollection
│   │   ├── groups.py               # Tool version groupings
│   │   ├── bash.py                 # Bash shell tool
│   │   ├── computer.py             # Mouse/keyboard/screen tool
│   │   └── edit.py                 # File editor tool
│   │
│   └── loop.py                     # Core agent sampling loop
│
├── frontend/                       # Web UI
│   ├── index.html
│   ├── app.js
│   └── style.css
│
├── image/                          # Docker image scripts
│   ├── entrypoint.sh
│   └── start_all.sh
│
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## Features

### Core Features

| Feature | Description |
|---------|-------------|
| **Session Management** | Create, list, delete agent task sessions |
| **Real-time Streaming** | SSE-based progress updates for tool calls |
| **VNC Integration** | Per-session virtual desktop via noVNC |
| **Database Persistence** | SQLite storage for sessions and messages |
| **Concurrent Sessions** | True parallel execution with dynamic displays |
| **Multi-LLM Support** | Works with Claude (Anthropic) or Gemini (Google) |

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
| `GET` | `/api/sessions/{id}/vnc` | Get VNC connection info |
| `GET` | `/health` | Health check |

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

# OR for Google Gemini:
GEMINI_API_KEY=AIza...
```

### 2. Build and Run

```bash
# Build and start the container
docker compose up --build

# Or run in detached mode
docker compose up --build -d
```

### 3. Access the Application

- **Frontend UI**: http://localhost:8000
- **API Health**: http://localhost:8000/health

### 4. Multi-Tenant Demonstration

1. Open two side-by-side browser windows to `http://localhost:8000`
2. Click **"New Task"** in both windows to spawn two separate virtual desktops
3. Give them both commands simultaneously (e.g., "Search weather in Tokyo" and "Search weather in New York")
4. Watch both Agent loops stream tool progress in real-time, completely independently

---

## API Documentation

### Create Session

```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "Weather Search Task"}'
```

**Response:**
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

**Response:**
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
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:35:00Z",
      "vnc_info": {...}
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

eventSource.addEventListener('tool_use', (e) => {
  console.log('Tool call:', JSON.parse(e.data));
});

eventSource.addEventListener('tool_result', (e) => {
  console.log('Tool result:', JSON.parse(e.data));
});

eventSource.addEventListener('done', () => {
  console.log('Task completed');
});
```

### SSE Event Types

| Event | Description | Data |
|-------|-------------|------|
| `text` | Agent text response | `{"text": "..."}` |
| `thinking` | Agent thinking content | `{"thinking": "..."}` |
| `tool_use` | Tool invocation | `{"tool_id": "...", "name": "...", "input": {...}}` |
| `tool_result` | Tool execution result | `{"tool_id": "...", "output": "...", "error": "..."}` |
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
  "active_sessions": 2
}
```

---

## Sequence Diagrams

### Session Creation Flow

```
┌────────┐          ┌───────────────┐          ┌────────────────┐          ┌──────────┐
│ Client │          │ FastAPI       │          │ DisplayManager │          │ Database │
└───┬────┘          └──────┬────────┘          └───────┬────────┘          └────┬─────┘
    │                      │                           │                        │
    │  POST /api/sessions  │                           │                        │
    │─────────────────────>│                           │                        │
    │                      │                           │                        │
    │                      │   allocate_display()      │                        │
    │                      │──────────────────────────>│                        │
    │                      │                           │                        │
    │                      │                           │ Start Xvfb :100        │
    │                      │                           │─────────────────┐      │
    │                      │                           │<────────────────┘      │
    │                      │                           │                        │
    │                      │                           │ Start x11vnc :5810     │
    │                      │                           │─────────────────┐      │
    │                      │                           │<────────────────┘      │
    │                      │                           │                        │
    │                      │                           │ Start websockify :5910 │
    │                      │                           │─────────────────┐      │
    │                      │                           │<────────────────┘      │
    │                      │                           │                        │
    │                      │   DisplayAllocation       │                        │
    │                      │<──────────────────────────│                        │
    │                      │                           │                        │
    │                      │            create_session()                        │
    │                      │───────────────────────────────────────────────────>│
    │                      │                                                    │
    │                      │            session record                          │
    │                      │<───────────────────────────────────────────────────│
    │                      │                           │                        │
    │   SessionResponse    │                           │                        │
    │<─────────────────────│                           │                        │
    │                      │                           │                        │
```

### Agent Message Flow

```
┌────────┐          ┌───────────────┐          ┌────────────────┐          ┌─────────┐
│ Client │          │ SessionManager│          │ Agent Loop     │          │ LLM API │
└───┬────┘          └──────┬────────┘          └───────┬────────┘          └────┬────┘
    │                      │                           │                        │
    │  POST /messages      │                           │                        │
    │─────────────────────>│                           │                        │
    │                      │                           │                        │
    │                      │  asyncio.create_task()    │                        │
    │                      │──────────────────────────>│                        │
    │                      │                           │                        │
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
    │  SSE: text           │                           │                        │
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

### Concurrent Sessions Flow

```
┌──────────┐     ┌──────────┐     ┌───────────────┐     ┌────────────────┐
│ Client A │     │ Client B │     │ SessionManager│     │ DisplayManager │
└────┬─────┘     └────┬─────┘     └──────┬────────┘     └───────┬────────┘
     │                │                   │                      │
     │  Create Session A                  │                      │
     │───────────────────────────────────>│                      │
     │                │                   │                      │
     │                │                   │  allocate_display()  │
     │                │                   │─────────────────────>│
     │                │                   │                      │
     │                │                   │  Display :100        │
     │                │                   │<─────────────────────│
     │                │                   │                      │
     │  Session A (display :100)          │                      │
     │<───────────────────────────────────│                      │
     │                │                   │                      │
     │                │  Create Session B │                      │
     │                │──────────────────>│                      │
     │                │                   │                      │
     │                │                   │  allocate_display()  │
     │                │                   │─────────────────────>│
     │                │                   │                      │
     │                │                   │  Display :101        │
     │                │                   │<─────────────────────│
     │                │                   │                      │
     │                │  Session B (:101) │                      │
     │                │<──────────────────│                      │
     │                │                   │                      │
     │  Send message to A                 │                      │
     │───────────────────────────────────>│                      │
     │                │                   │                      │
     │                │                   │  create_task(agent A)│
     │                │                   │─────────────────────>│
     │                │                   │                      │
     │                │  Send message to B│                      │
     │                │──────────────────>│                      │
     │                │                   │                      │
     │                │                   │  create_task(agent B)│
     │                │                   │─────────────────────>│
     │                │                   │                      │
     │  SSE: Agent A working on :100      │                      │
     │<═══════════════════════════════════│                      │
     │                │                   │                      │
     │                │  SSE: Agent B working on :101            │
     │                │<══════════════════│                      │
     │                │                   │                      │
     │    [Both agents run SIMULTANEOUSLY]│                      │
     │                │                   │                      │
```

---

## Concurrency Model

### How Concurrent Sessions Work

1. **Dynamic Display Allocation**: Each session gets its own virtual X11 display (`:100`, `:101`, etc.) via `DisplayManager`

2. **Isolated Processes**: Per session, we spawn:
   - `Xvfb` - Virtual framebuffer
   - `x11vnc` - VNC server
   - `websockify` - WebSocket proxy for noVNC

3. **Async Agent Execution**: Agent loops run as `asyncio.Task` instances, allowing true parallel execution

4. **No Hardcoded Limits**: The system dynamically allocates displays starting from `:100`, with no fixed upper bound

5. **Thread-Safe State**: All shared state is protected by `asyncio.Lock` to prevent race conditions

### Code Example: Display Allocation

```python
# Each session gets its own display dynamically
async def allocate_display(self) -> DisplayAllocation:
    async with self._lock:
        display_num = self._next_display
        self._next_display += 1  # No limit!

        vnc_port = self._next_vnc_port()
        ws_port = self._next_ws_port()

    # Spawn isolated display processes
    await self._start_xvfb(allocation)
    await self._start_x11vnc(allocation)
    await self._start_websockify(allocation)

    return allocation
```

### Code Example: Parallel Agent Tasks

```python
# Each message triggers a new async task (non-blocking)
active.agent_task = asyncio.create_task(
    self._run_agent_loop(active),
    name=f"agent-{session_id[:8]}",
)

# The task runs independently - no blocking other sessions!
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
# OR
export GEMINI_API_KEY=AIza...

# Run the API server
python -m uvicorn computer_use_demo.api.app:app --reload --port 8000
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/
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

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes* | Anthropic Claude API key |
| `GEMINI_API_KEY` | Yes* | Google Gemini API key (alternative) |
| `ANTHROPIC_BASE_URL` | No | Custom API endpoint |
| `ANTHROPIC_MODEL` | No | Model to use (default: `claude-haiku-4-5-20251001`) |
| `WIDTH` | No | Display width (default: `1024`) |
| `HEIGHT` | No | Display height (default: `768`) |
| `DISPLAY_NUM` | No | Default display number (default: `1`) |

*At least one API key is required (either Anthropic or Gemini)

### Docker Compose Configuration

The `docker-compose.yml` exposes:

- Port `8000`: FastAPI backend + frontend
- Port `6080`: Default noVNC display
- Ports `5910-5999`: Dynamic VNC ports for concurrent sessions

---

## License

This project extends the [Anthropic Computer Use Demo](https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo) with a production-ready API layer.

---

## Demo Video

See the demo video for:
1. Repository and codebase overview
2. Service launch and endpoint functionality
3. Usage Case 1: Single session - Weather search in Dubai
4. Usage Case 2: Concurrent sessions - Tokyo + New York weather simultaneously
5. Real-time streaming demonstration
