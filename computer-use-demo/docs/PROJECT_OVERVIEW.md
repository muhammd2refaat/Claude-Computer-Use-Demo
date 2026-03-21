# Project Overview

> **Computer Use Agent — API Backend**
> Author: Muhammed Refaat

---

## 1. What the System Does

The Computer Use Agent is a **production-grade backend system** that enables autonomous AI agents (Claude by Anthropic, Gemini by Google) to interact with a full Linux desktop environment — including mouse, keyboard, screen capture, bash shell, and a file editor — via a RESTful API with real-time Server-Sent Events (SSE) streaming.

Each user request spins up a **completely isolated virtual desktop** (Xvfb + x11vnc + noVNC), giving the AI its own Firefox browser, file manager, and terminal. The agent loop orchestrates LLM ↔ tool interactions iteratively until the task is complete, streaming fine-grained progress events to the connected UI.

### Core Value Proposition

| Capability | Description |
|---|---|
| **Autonomous Desktop Control** | An AI agent that sees, clicks, types, and navigates a real Linux GUI |
| **True Session Concurrency** | Multiple human operators can run independent agent sessions in parallel — no display collisions, no browser lock conflicts |
| **Real-Time Observability** | Every LLM thought, tool invocation, and tool result is streamed live to the frontend over SSE |
| **Persistent State** | All sessions and messages are persisted in SQLite with connection pooling — sessions survive server restarts |
| **Multi-LLM Flexibility** | Swap between Anthropic Claude and Google Gemini by changing a single environment variable |

---

## 2. Business Goal

This project transforms the official [Anthropic Computer Use Demo](https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo) from a **single-user Streamlit prototype** into a **multi-tenant, production-ready API service**.

### Key Business Objectives

1. **Multi-Tenancy** — Support simultaneous users, each with their own isolated virtual desktop and agent session. The original demo was hardcoded to a single display (`:1`), making concurrent sessions impossible.
2. **API-First Architecture** — Replace the tightly-coupled Streamlit UI with a decoupled REST/SSE API, enabling integrations with arbitrary frontends, CI/CD pipelines, or programmatic clients.
3. **Operational Reliability** — Introduce connection pooling, graceful shutdown, health monitoring, and database persistence — capabilities missing from the prototype.
4. **Developer Experience** — Provide a clean layered architecture with testable service boundaries, centralized configuration, and structured logging.

---

## 3. Key Features

### 3.1 Session Lifecycle Management

- **Create** → Allocates a virtual display (`Xvfb` → `mutter` → `tint2` → `x11vnc` → `websockify`), persists session in SQLite, and returns VNC connection details.
- **List / Get** → Query all sessions or a specific session with status, timestamps, and VNC info.
- **Delete** → Cancels the running agent task, kills all display processes, cleans up X11 lock files, and purges the DB record.
- **Restore** → Rehydrates a persisted session after server restart by allocating a fresh display and replaying message history.

### 3.2 Agent Loop Execution

- Implements the **Anthropic Computer Use sampling loop**: an iterative cycle of `LLM Call → Parse Response → Execute Tools → Append Results → Repeat`.
- Agent loops run as **background `asyncio.Task` instances**, meaning the HTTP endpoint returns `202 Accepted` immediately while the agent processes asynchronously.
- Supports dynamic system prompt injection per session (each session's `DISPLAY=:N` is patched into the prompt).

### 3.3 Real-Time SSE Streaming

Seven distinct event types flow over the SSE channel:

| Event | Payload | Purpose |
|---|---|---|
| `text` | `{"text": "..."}` | Agent's natural-language response |
| `thinking` | `{"thinking": "..."}` | Agent's internal reasoning (extended thinking) |
| `tool_use` | `{"tool_id", "name", "input"}` | Tool invocation intent |
| `tool_result` | `{"tool_id", "output", "error", "has_screenshot"}` | Tool execution result |
| `status` | `{"status": "running\|stopped\|idle"}` | Session state transitions |
| `error` | `{"message": "..."}` | Error during agent execution |
| `done` | `{"status": "completed"}` | Agent loop finished |

### 3.4 Computer Use Tools

| Tool | File | Description |
|---|---|---|
| **ComputerTool** | `tools/computer.py` | Mouse clicks, drags, keypresses, screenshots, cursor position, scrolling, zoom. Supports three API versions: `20241022`, `20250124`, `20251124`. |
| **BashTool** | `tools/bash.py` | Persistent bash shell session with async I/O, 120s timeout, sentinel-based output parsing. Each session gets its own subprocess with display-specific env vars. |
| **EditTool** | `tools/edit.py` | File create, view, `str_replace`-based editing, and undo. Operates on the agent's filesystem. |

### 3.5 Concurrent Session Isolation

Concurrency is the **architectural centrepiece** of this project:

- **Display-level isolation**: Each session spawns its own `Xvfb` framebuffer, window manager (`mutter`), taskbar (`tint2`), VNC server (`x11vnc`), and WebSocket proxy (`websockify`).
- **Firefox profile isolation**: A custom `firefox_wrapper.sh` creates a per-display Firefox profile (`~/.mozilla/firefox/profile-display-N`), eliminating "Firefox is already running" errors.
- **Env-safe tool construction**: Tools read `DISPLAY_NUM` / `WIDTH` / `HEIGHT` from `os.environ` at init time. `SessionService._create_tools_for_display()` uses an `asyncio.Lock` to atomically set/restore these env vars during synchronous tool `__init__`.

### 3.6 Multi-LLM Support

- **Anthropic (Claude)**: Native SDK integration via `anthropic.Anthropic`, with prompt caching, beta flags, and extended thinking support.
- **Google (Gemini)**: A custom wrapper (`api/gemini_wrapper.py`) translates Anthropic's message/tool format to Gemini's `functionCall`/`functionResponse` protocol. Auto-detected by API key prefix (`AIza...`).

---

## 4. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Docker Container                              │
│                                                                            │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────────┐  │
│  │   Web Frontend   │    │  FastAPI Server   │    │  Default Desktop     │  │
│  │  (HTML/JS/CSS)   │◄──►│  :8000            │    │  Xvfb :1 + noVNC    │  │
│  │  Served as       │    │                   │    │  :6080               │  │
│  │  Static Files    │    │  Routes:          │    └──────────────────────┘  │
│  └──────────────────┘    │  /api/sessions    │                             │
│                          │  /api/sessions/   │    ┌──────────────────────┐  │
│                          │    {id}/messages   │    │  Session A Desktop   │  │
│                          │    {id}/stream     │    │  Xvfb :100           │  │
│                          │    {id}/vnc        │    │  VNC :5810 → WS:5910│  │
│                          │    {id}/stop       │    └──────────────────────┘  │
│                          │    {id}/restore    │                             │
│                          │  /health          │    ┌──────────────────────┐  │
│                          │  /docs            │    │  Session B Desktop   │  │
│                          │                   │    │  Xvfb :101           │  │
│                          └────────┬──────────┘    │  VNC :5811 → WS:5911│  │
│                                   │               └──────────────────────┘  │
│                          ┌────────▼──────────┐                             │
│                          │  SQLite (WAL)      │        ... N sessions      │
│                          │  /data/sessions.db │                             │
│                          │  Pool: 2–10 conns  │                             │
│                          └───────────────────┘                             │
│                                   │                                        │
└───────────────────────────────────┼────────────────────────────────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │   LLM API (External)          │
                    │                               │
                    │  • Anthropic Claude API       │
                    │    (claude-sonnet-4-5-*)       │
                    │                               │
                    │  • Google Gemini API           │
                    │    (gemini-2.5-flash)          │
                    └───────────────────────────────┘
```

### Request Flow Summary

1. Client creates a session → `POST /api/sessions` → allocates virtual display + DB record
2. Client sends a task → `POST /api/sessions/{id}/messages` → returns `202`, spawns background `asyncio.Task`
3. Client connects SSE → `GET /api/sessions/{id}/stream` → receives real-time events
4. Agent loop: calls LLM → parses tool calls → executes tools on the virtual desktop → streams results → loops until done
5. Client watches VNC via embedded noVNC iframe at `/vnc/?port=<ws_port>&autoconnect=true`

---

## 5. Tech Stack

| Category | Technology | Version | Purpose |
|---|---|---|---|
| **Runtime** | Python | 3.11.6 (via pyenv) | Application logic |
| **API Framework** | FastAPI | ≥0.104.0 | RESTful API with async support |
| **ASGI Server** | Uvicorn | ≥0.24.0 | Production async HTTP server |
| **Database** | SQLite + aiosqlite | ≥0.19.0 | Async persistence with WAL mode |
| **Data Validation** | Pydantic | ≥2.0.0 | Request/response schema validation |
| **SSE Streaming** | sse-starlette | ≥1.8.0 | Server-Sent Events for real-time updates |
| **HTTP Client** | httpx | ≥0.25.0 | Async HTTP for LLM API calls |
| **AI SDK** | anthropic | ≥0.39.0 | Claude API with beta tool support |
| **Virtual Display** | Xvfb | System | Headless X11 framebuffer |
| **Window Manager** | mutter | System | Compositing window manager |
| **Taskbar** | tint2 | System | Lightweight desktop panel |
| **VNC Server** | x11vnc | System | Screen sharing over RFB protocol |
| **VNC Web Client** | noVNC | v1.5.0 | Browser-based VNC via WebSocket |
| **WebSocket Proxy** | websockify | v0.12.0 | TCP → WebSocket bridge for VNC |
| **Browser** | Firefox ESR | System | AI-controlled web browser |
| **Input Automation** | xdotool | System | Mouse/keyboard simulation |
| **Screenshot** | scrot / gnome-screenshot | System | Screen capture |
| **Image Processing** | ImageMagick (convert) | System | Screenshot scaling and cropping |
| **Container** | Docker + Docker Compose | — | Reproducible deployment |
| **Base Image** | Ubuntu 22.04 | — | Host OS inside container |
| **Linting** | Ruff | 0.6.7 | Fast Python linter and formatter |
| **Testing** | pytest + pytest-asyncio | 8.3.3 / 0.23.6 | Async test framework |
| **Frontend** | Vanilla HTML/CSS/JS | — | SPA-style UI with SSE + noVNC integration |
