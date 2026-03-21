# Domain Model

> Business domain concepts, entity relationships, workflows, and rules that govern the Computer Use Agent system.

---

## Table of Contents

1. [Domain Overview](#1-domain-overview)
2. [Core Entities](#2-core-entities)
3. [Workflows](#3-workflows)
4. [Business Rules](#4-business-rules)
5. [State Machines](#5-state-machines)
6. [Event Model](#6-event-model)
7. [Glossary](#7-glossary)

---

## 1. Domain Overview

The Computer Use Agent operates in the domain of **autonomous desktop automation via conversational AI**. A human operator provides a natural-language task, and the system orchestrates an AI agent that interacts with a full Linux desktop — clicking, typing, browsing, and running commands — to accomplish the task.

### Domain Boundary

```
┌──────────────────────────────────────────────────────────────────┐
│                          System Boundary                         │
│                                                                  │
│  ┌─────────┐    ┌──────────┐    ┌────────────┐    ┌──────────┐  │
│  │ Session  │ ──►│  Agent   │ ──►│   Tool     │ ──►│ Desktop  │  │
│  │ (User)   │    │  (LLM)   │    │ (Computer/ │    │ (Xvfb +  │  │
│  │          │    │          │    │  Bash/Edit)│    │  Firefox) │  │
│  └─────────┘    └──────────┘    └────────────┘    └──────────┘  │
│       ▲              │                                    │      │
│       │              ▼                                    │      │
│       │         ┌──────────┐                              │      │
│       └─────────│  Events  │◄─────────────────────────────┘      │
│                 │  (SSE)   │                                     │
│                 └──────────┘                                     │
└──────────────────────────────────────────────────────────────────┘
```

The system mediates between **three trust domains**:

| Domain | Entity | Trust Level |
|---|---|---|
| **Human Operator** | Browser client, API consumer | Trusted — initiates tasks, views results |
| **AI Agent** | Claude / Gemini LLM | Semi-trusted — generates tool calls, bounded by tool capabilities |
| **Desktop Environment** | Xvfb, Firefox, shell | Sandboxed — isolated per session inside a container |

---

## 2. Core Entities

### 2.1 Session

A **Session** is the top-level aggregate root. It represents a single operator task lifecycle — from creation through execution to completion.

```
Session
├── id: UUID (hex)                 # Immutable identifier
├── title: string                  # Human-readable label (e.g., "Search Weather in Tokyo")
├── status: SessionStatus          # Finite state machine (see §5)
├── display_num: int               # Xvfb display number (e.g., 100)
├── vnc_port: int                  # WebSocket port for noVNC (e.g., 5910)
├── created_at: datetime (UTC)     # Creation timestamp
├── updated_at: datetime (UTC)     # Last status change
│
├── HAS-MANY: Messages             # Ordered conversation history
├── HAS-ONE: DisplayAllocation     # Runtime display process group (in-memory only)
├── HAS-ONE: ToolCollection        # Pre-built tools bound to this session's display
└── HAS-ONE: AgentTask             # Background asyncio.Task (in-memory only)
```

**Persistence boundary:** `id`, `title`, `status`, `display_num`, `vnc_port`, `created_at`, `updated_at` are persisted in SQLite. `DisplayAllocation`, `ToolCollection`, and `AgentTask` are **runtime-only state** held in the `ActiveSession` dataclass.

### 2.2 Message

A **Message** is an immutable record in the conversation history between the human operator, the AI agent, and the tool system.

```
Message
├── id: UUID (hex)                 # Immutable identifier
├── session_id: FK → Session.id    # Parent session
├── role: MessageRole              # "user" | "assistant" | "tool"
├── content: string | JSON         # Text or structured content block
└── created_at: datetime (UTC)     # When the message was created
```

**Content polymorphism:**

| Role | Content Shape | Example |
|---|---|---|
| `user` | Plain text string | `"Search the weather in Dubai"` |
| `assistant` | JSON: `{"type": "text", "text": "..."}` | Agent's natural language response |
| `assistant` | JSON: `{"type": "tool_use", "name": "bash", "input": {...}}` | Tool invocation intent |
| `tool` | JSON: `{"type": "tool_result", "tool_id": "...", "output": "...", "error": "..."}` | Tool execution result |

### 2.3 Display Allocation

A **DisplayAllocation** is a runtime value object representing the process group for a session's virtual desktop.

```
DisplayAllocation
├── display_num: int               # Xvfb display number
├── vnc_port: int                  # x11vnc RFB port
├── ws_port: int                   # websockify WebSocket port
├── xvfb_pid: int?                 # Xvfb process ID
├── x11vnc_pid: int?               # x11vnc process ID
├── websockify_pid: int?           # websockify process ID
├── mutter_pid: int?               # Window manager process ID
└── tint2_pid: int?                # Taskbar process ID
```

**Lifecycle:** Created on session creation, destroyed on session deletion. **Not persisted** — display/VNC info in the DB is metadata only. On server restart, sessions are restored with **new** display allocations.

### 2.4 Event

An **Event** is a transient message published through the SSE pipeline during agent execution.

```
Event
├── type: SSEEventType             # "text" | "thinking" | "tool_use" | "tool_result" | "status" | "error" | "done"
├── data: dict                     # Type-specific payload
└── timestamp: datetime (UTC)      # When the event was emitted
```

**Events are ephemeral** — they are consumed once by the SSE stream and not persisted.

### 2.5 Tool

A **Tool** is a capability exposed to the LLM agent for interacting with the desktop.

```
Tool (abstract)
├── name: string                   # "computer" | "bash" | "str_replace_editor"
├── api_type: string               # Version-qualified type identifier
├── to_params() → dict             # Anthropic API tool parameter format
└── __call__(**kwargs) → ToolResult # Execute the tool action
```

**ToolResult:**
```
ToolResult
├── output: string?                # Stdout or success text
├── error: string?                # Stderr or error message
├── base64_image: string?          # Screenshot (PNG, base64-encoded)
└── system: string?                # System-level prefix message
```

---

## 3. Workflows

### 3.1 Primary Workflow: Task Execution

This is the main workflow — from user task input to completed execution.

```
┌─────────────────────────────────────────────────────────────┐
│                    Task Execution Workflow                    │
│                                                             │
│  1. OPERATOR creates a session                              │
│     └──► System allocates display + VNC                     │
│          System creates DB record                           │
│          System pre-builds tools for this display            │
│          Status: CREATED                                    │
│                                                             │
│  2. OPERATOR submits a task via message                     │
│     └──► System persists user message                       │
│          System spawns background agent task                 │
│          Status: RUNNING                                    │
│          Returns immediately (202 Accepted)                  │
│                                                             │
│  3. OPERATOR connects SSE stream                            │
│     └──► System yields events from agent queue               │
│                                                             │
│  4. AGENT LOOP (repeating):                                 │
│     a. Agent calls LLM with conversation history            │
│     b. LLM returns text + tool_use blocks                   │
│     c. System streams text/tool_use events                  │
│     d. For each tool_use:                                   │
│        i.   System executes tool on the virtual desktop     │
│        ii.  System streams tool_result event                │
│        iii. System persists tool result to DB                │
│     e. System appends tool_results to conversation          │
│     f. IF tools were called → GOTO step (a)                 │
│        ELSE → agent is done                                 │
│                                                             │
│  5. AGENT LOOP COMPLETES                                    │
│     └──► System streams "done" event                        │
│          Status: IDLE                                       │
│          Agent task ends naturally                           │
│                                                             │
│  6. OPERATOR can submit another task (goto step 2)          │
│     OR delete the session (cleanup)                         │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Session Restore Workflow

When the server restarts, all in-memory state is lost. Sessions can be restored from the database.

```
┌─────────────────────────────────────────────────────────────┐
│                  Session Restore Workflow                     │
│                                                             │
│  Trigger: Client accesses a session that exists in DB        │
│           but is NOT in the active sessions registry         │
│                                                             │
│  1. System looks up session in DB                           │
│     └──► If not found → 404 error                            │
│                                                             │
│  2. System allocates a NEW display (old one is gone)        │
│     └──► New display_num, new vnc_port                       │
│                                                             │
│  3. System updates DB with new display info                 │
│                                                             │
│  4. System creates new ToolCollection for the new display    │
│                                                             │
│  5. System replays user messages from DB                    │
│     └──► Only user messages are replayed                     │
│          (Tool results contain no images — screenshots       │
│           are not persisted)                                 │
│                                                             │
│  6. System registers ActiveSession in memory                 │
│     └──► Status: IDLE                                       │
│                                                             │
│  7. Session is ready for new messages                        │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Concurrent Execution Workflow

```
┌─────────────────────────────────────────────────────────────┐
│             Concurrent Execution Workflow                     │
│                                                             │
│  Two operators, two sessions, same server.                   │
│                                                             │
│  Operator A:                     Operator B:                 │
│  ┌───────────────┐               ┌───────────────┐          │
│  │ Create Session │               │ Create Session │          │
│  │ → display :100 │               │ → display :101 │          │
│  │ → VNC 5910     │               │ → VNC 5911     │          │
│  └───────┬───────┘               └───────┬───────┘          │
│          │                                │                  │
│  ┌───────▼───────┐               ┌───────▼───────┐          │
│  │ Send message   │               │ Send message   │          │
│  │ "Search Tokyo" │               │ "Search NYC"   │          │
│  │ → 202 Accepted │               │ → 202 Accepted │          │
│  └───────┬───────┘               └───────┬───────┘          │
│          │                                │                  │
│          ▼                                ▼                  │
│  ┌──────────────────────────────────────────────┐           │
│  │           asyncio Event Loop                  │           │
│  │                                               │           │
│  │  Task A (agent-abc123)   Task B (agent-def456)│           │
│  │  ├── LLM call            ├── LLM call         │           │
│  │  ├── bash on :100        ├── bash on :101     │           │
│  │  ├── firefox profile-100 ├── firefox profile-101│         │
│  │  ├── screenshot :100     ├── screenshot :101  │           │
│  │  └── SSE → Queue A       └── SSE → Queue B   │           │
│  │                                               │           │
│  │  [FULLY PARALLEL — cooperative multitasking]   │           │
│  └──────────────────────────────────────────────┘           │
│          │                                │                  │
│  ┌───────▼───────┐               ┌───────▼───────┐          │
│  │ SSE stream A   │               │ SSE stream B   │          │
│  │ → Operator A   │               │ → Operator B   │          │
│  └───────────────┘               └───────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Business Rules

### 4.1 Session Rules

| # | Rule | Enforcement | Consequence of Violation |
|---|---|---|---|
| SR-1 | A session MUST have a unique display number | `DisplayService._lock` serializes allocation | Display conflict → Xvfb crash |
| SR-2 | A session MUST NOT accept a new message while an agent is running | `active.is_running` guard in `AgentService.send_message()` | Returns `409 Conflict` |
| SR-3 | A session MUST be restored before accepting messages after a restart | Auto-restore in `stream_events()` and `send_message()` | `KeyError` → auto-restore attempt |
| SR-4 | Deleting a session MUST cancel any running agent task | `SessionService.delete_session()` calls `task.cancel()` | Orphaned tasks consuming resources |
| SR-5 | Deleting a session MUST release all display processes | `SessionService.delete_session()` calls `display_service.release_display()` | Zombie Xvfb/x11vnc processes |
| SR-6 | Deleting a session MUST cascade-delete all messages | `ON DELETE CASCADE` in DB schema | Orphaned message records |
| SR-7 | Session titles are optional; system generates a default | `"Task HH:MM"` format in `session_service.create_session()` | — |
| SR-8 | Display allocation starts at display `:100` | `settings.BASE_DISPLAY_NUM = 100` | Avoids conflict with default display `:1` |

### 4.2 Agent Rules

| # | Rule | Enforcement | Consequence of Violation |
|---|---|---|---|
| AR-1 | The agent loop terminates when the LLM returns no tool calls | `if not tool_result_content: return messages` | Infinite loop |
| AR-2 | Tool errors MUST NOT crash the agent loop | `try/except` in `AgentRunner` wraps all tool execution | Server crash |
| AR-3 | API errors MUST be streamed as SSE error events | `_on_api_response()` catches and publishes errors | Silent failures, client hangs |
| AR-4 | Agent loops are cancellable via `POST /stop` | `asyncio.Task.cancel()` + `CancelledError` handler | Uninterruptible agents |
| AR-5 | Each agent loop gets a dynamically-patched system prompt | `SYSTEM_PROMPT.replace("DISPLAY=:1", ...)` | Agent commands go to wrong display |
| AR-6 | Screenshots MUST NOT be persisted in the database | Only `has_screenshot: true` flag is stored | Database bloat (each screenshot is ~100KB base64) |
| AR-7 | An API key MUST be present or the agent emits an error event and returns | Checked at start of `run_agent_loop()` | Cryptic LLM SDK error |

### 4.3 Display Rules

| # | Rule | Enforcement | Consequence of Violation |
|---|---|---|---|
| DR-1 | VNC port allocation MUST be unique | Port tracking sets + lock | Port conflict → x11vnc crash |
| DR-2 | WebSocket port allocation MUST be unique | Port tracking sets + lock | Port conflict → websockify crash |
| DR-3 | Display processes are killed in reverse startup order | `release_display()` kills websockify → x11vnc → tint2 → mutter → Xvfb | Orphan processes blocking ports |
| DR-4 | Xvfb startup MUST be validated | Polls `/tmp/.X{N}-lock` for up to 10s | Agent executes against nonexistent display |
| DR-5 | VNC and WebSocket startup MUST be validated | TCP port probe for up to 10s | Frontend shows dead VNC iframe |
| DR-6 | Firefox MUST run with `--no-remote --profile` | `firefox_wrapper.sh` installed as `/usr/local/bin/firefox` | "Firefox is already running" error |

### 4.4 Database Rules

| # | Rule | Enforcement | Consequence of Violation |
|---|---|---|---|
| DBR-1 | WAL journal mode for concurrent access | `PRAGMA journal_mode=WAL` on every connection | Write locks blocking reads |
| DBR-2 | Connection health is verified before use | `SELECT 1` probe on acquire | Queries fail on stale connections |
| DBR-3 | Unhealthy connections are replaced, not requeued | Pool creates new connection | Client errors propagate |
| DBR-4 | Pool MUST NOT exceed max_size | Lock-protected size counter | Resource exhaustion |
| DBR-5 | Messages content MUST be JSON-serialized for complex types | `json.dumps()` in `add_message()` | Deserialization failures on read |

---

## 5. State Machines

### 5.1 Session Status State Machine

```
                    ┌──────────────────────────────────────────┐
                    │                                          │
                    ▼                                          │
              ┌──────────┐                                     │
    ──────────►│ CREATED  │                                     │
    (create)   └────┬─────┘                                    │
                    │                                          │
                    │ send_message()                            │
                    ▼                                          │
              ┌──────────┐   agent loop error                  │
              │ RUNNING  │──────────────────────►┌─────────┐  │
              └────┬─────┘                       │  ERROR  │  │
                    │                            └────┬────┘  │
                    │ agent loop completes             │       │
                    │ OR stop_agent()                   │       │
                    ▼                                  │       │
              ┌──────────┐                             │       │
              │   IDLE   │◄────────────────────────────┘       │
              └────┬─────┘                                     │
                    │                                          │
                    │ send_message()                            │
                    └──────────────────────────────────────────┘
                    │
                    │ agent loop completes normally
                    ▼
              ┌──────────────┐
              │  COMPLETED   │  (terminal — rarely used in practice;
              └──────────────┘   sessions typically stay IDLE for reuse)
```

**Transitions:**

| From | To | Trigger |
|---|---|---|
| `—` | `CREATED` | `session_service.create_session()` |
| `CREATED` / `IDLE` | `RUNNING` | `agent_service.send_message()` |
| `RUNNING` | `IDLE` | Agent loop completes successfully, or `agent_service.stop_agent()` |
| `RUNNING` | `ERROR` | Unhandled exception in agent loop |
| `ERROR` | `IDLE` | Session restored, or new message sent |

### 5.2 Agent Task Lifecycle

```
              ┌───────────┐
              │   None    │  (no agent_task)
              └─────┬─────┘
                    │ asyncio.create_task()
                    ▼
              ┌───────────┐
              │  Running  │  (task.done() == False)
              └─────┬─────┘
                    │
           ┌───────┴───────┐
           │               │
      natural end      task.cancel()
           │               │
           ▼               ▼
     ┌───────────┐  ┌─────────────┐
     │   Done    │  │  Cancelled  │
     └───────────┘  └─────────────┘
```

---

## 6. Event Model

### 6.1 Event Flow Through the System

```
LLM Response
    │
    ├── text block ──────── _on_output() ──► SSE: "text"
    │                                        DB: messages (role=assistant)
    │
    ├── thinking block ──── _on_output() ──► SSE: "thinking"
    │                                        (not persisted)
    │
    ├── tool_use block ──── _on_output() ──► SSE: "tool_use"
    │                                        DB: messages (role=assistant)
    │                   │
    │                   └── tool_collection.run()
    │                          │
    │                          └── ToolResult
    │                                 │
    │                                 └── _on_tool_output() ──► SSE: "tool_result"
    │                                                           DB: messages (role=tool)
    │
    └── (no tool calls) ────────────────────► SSE: "done"

Error during LLM call ─────────────────────► SSE: "error"

Status change ─────────────────────────────► SSE: "status"
```

### 6.2 Event Ordering Guarantees

Within a single session:

1. **`status: running`** is always the first event after a message is sent
2. **`text`** and **`tool_use`** events appear in the order they are in the LLM response
3. **`tool_result`** always follows its corresponding **`tool_use`**
4. **`done`** is always the last event (if execution completes normally)
5. **`error`** replaces **`done`** if execution fails
6. Events from different sessions are **completely independent** — they flow through separate queues

---

## 7. Glossary

| Term | Definition |
|---|---|
| **Session** | A long-lived context for an operator's task, comprising a virtual display, message history, and agent state. |
| **Agent** | The AI entity (Claude or Gemini) that interprets tasks and generates tool calls. |
| **Agent Loop** | The iterative cycle: call LLM → parse tools → execute tools → append results → repeat until done. |
| **Sampling Loop** | Synonym for Agent Loop (from Anthropic's terminology). |
| **Tool** | A capability exposed to the LLM: `computer` (mouse/keyboard), `bash` (shell), `str_replace_editor` (file editing). |
| **Tool Call / Tool Use** | An LLM response block requesting execution of a specific tool with given parameters. |
| **Tool Result** | The output of executing a tool call — may include text output, error, or a screenshot. |
| **Display Allocation** | The process group (Xvfb + mutter + tint2 + x11vnc + websockify) providing an isolated virtual desktop. |
| **SSE (Server-Sent Events)** | A unidirectional HTTP streaming protocol used to push real-time agent events to the browser. |
| **noVNC** | A browser-based VNC client that connects via WebSocket. Embedded as an iframe in the frontend. |
| **Xvfb** | X Virtual Framebuffer — a display server that performs all graphical operations in memory without physical display hardware. |
| **VNC** | Virtual Network Computing — a protocol for remote GUI access. Used here to let operators watch the agent's desktop. |
| **websockify** | A proxy that bridges WebSocket connections to TCP (VNC) connections, enabling noVNC to connect via HTTP. |
| **ActiveSession** | The in-memory runtime state for a session (display, tools, messages, event queue). Not persisted. |
| **Connection Pool** | The managed set of reusable SQLite database connections (2–10 by default). |
| **WAL Mode** | Write-Ahead Logging — a SQLite journal mode that allows concurrent readers and a single writer. |
| **Prompt Caching** | An Anthropic feature that caches system/conversation context across API calls, reducing cost by up to 90%. |
| **Beta Flag** | A string identifier (e.g., `computer-use-2025-01-24`) sent in API requests to enable experimental Anthropic features. |
| **ToolGroup** | A versioned bundle of tool classes and their corresponding beta flag. |
| **ToolCollection** | A runtime container that holds instantiated tool objects and dispatches execution by tool name. |
| **Display Number** | The X11 display identifier (e.g., `:100`). Each session gets a unique number starting from 100. |
| **Firefox Profile Isolation** | Each session's Firefox runs with `--no-remote --profile /path/profile-display-N`, preventing concurrent instance conflicts. |
