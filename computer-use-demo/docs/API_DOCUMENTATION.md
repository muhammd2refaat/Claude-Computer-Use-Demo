# Computer Use Agent - API Documentation

**Author: Muhammed Refaat**

---

## 📖 How to Use This Documentation

This documentation explains how to interact with the Computer Use Agent API - a system that lets you control AI agents that can see and interact with computer screens.

### Who Is This For?

| Role | What You'll Find |
|------|------------------|
| **Frontend Developers** | JavaScript examples, SSE integration, response handling |
| **Backend Developers** | API design, error handling, async patterns |
| **QA Engineers** | cURL commands, expected responses, error scenarios |
| **Product Managers** | Capability overview, use case examples |

### Quick Start (5 Minutes)

```bash
# 1. Create a session (get a virtual desktop)
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "My First Task"}'

# 2. Send a message (tell the agent what to do)
curl -X POST http://localhost:8000/api/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"text": "Open Firefox and search for weather in Dubai"}'

# 3. Watch the agent work (real-time updates)
curl -N http://localhost:8000/api/sessions/{session_id}/stream
```

---

## 📚 Glossary

| Term | What It Means | Example |
|------|---------------|---------|
| **Session** | An isolated workspace with its own virtual screen | Like opening a new browser window |
| **Agent** | The AI that controls the computer | Claude AI with computer vision |
| **Display** | A virtual screen (X11) the agent sees | DISPLAY=:111 |
| **VNC** | Remote desktop viewing technology | Watch the agent's screen in your browser |
| **SSE** | Server-Sent Events for live updates | Like a Twitter feed of agent actions |
| **Tool** | An action the agent can perform | screenshot, click, type, scroll |
| **Message** | Text you send to the agent | "Search for weather in Dubai" |

---

## Table of Contents

1. [API Overview](#api-overview)
2. [Base URL & Paths](#base-url--paths)
3. [Session Endpoints](#session-endpoints)
   - [Create Session](#1-create-session)
   - [List Sessions](#2-list-sessions)
   - [Get Session](#3-get-session)
   - [Delete Session](#4-delete-session)
4. [Message Endpoints](#message-endpoints)
   - [Send Message](#5-send-message)
   - [Get Messages](#6-get-messages)
   - [Stop Agent](#7-stop-agent)
   - [Restore Session](#8-restore-session)
5. [Streaming Endpoints](#streaming-endpoints)
   - [SSE Event Stream](#9-sse-event-stream)
6. [System Endpoints](#system-endpoints)
   - [Health Check](#10-health-check)
7. [Data Models](#data-models)
8. [Error Handling](#error-handling)
9. [Quick Reference](#quick-reference)

---

## API Overview

### 🎯 What Does This API Do?

The Computer Use Agent API lets you:

1. **Create Virtual Workspaces** - Each session gets its own isolated screen
2. **Send Tasks to AI Agents** - Natural language instructions
3. **Watch Agents Work** - Real-time streaming of actions
4. **Manage Multiple Agents** - Run several tasks in parallel

**Real-world analogy:** Like hiring virtual assistants, each with their own computer, who you can watch work through a remote desktop.

### Design Principles

| Principle | What It Means | Benefit |
|-----------|---------------|---------|
| **RESTful** | URLs represent resources (`/sessions`, `/messages`) | Predictable, easy to learn |
| **Async-First** | Long tasks return immediately with 202 | No timeout issues |
| **Real-time** | SSE streaming for live updates | Watch progress instantly |
| **Stateless** | Each request is self-contained | Easy to scale |

### Request Flow Overview

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Create  │────▶│  Send   │────▶│ Stream  │────▶│ Delete  │
│ Session │     │ Message │     │ Events  │     │ Session │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
   201            202              200              204
```

---

## Base URL & Paths

### Base URL

```
http://localhost:8000
```

For Docker deployments, use the container's host and port.

### Available Paths

| Path | Purpose | Example |
|------|---------|---------|
| `/api/sessions` | Create and list sessions | `POST /api/sessions` |
| `/api/sessions/{id}` | Get, delete specific session | `GET /api/sessions/abc123` |
| `/api/sessions/{id}/messages` | Send and get messages | `POST .../messages` |
| `/api/sessions/{id}/stream` | Real-time event stream | Connect with EventSource |
| `/api/sessions/{id}/stop` | Stop running agent | `POST .../stop` |
| `/api/sessions/{id}/restore` | Restore after restart | `POST .../restore` |
| `/health` | System health check | `GET /health` |
| `/docs` | Interactive Swagger UI | Open in browser |

---

## Session Endpoints

### 1. Create Session

#### 🎯 What Is This?

Creates a new isolated workspace where an AI agent can operate. Each session gets its own virtual screen (like opening a new desktop).

**Real-world analogy:** Like renting a private computer in a lab - you get your own screen, and nobody else can see or interfere with your work.

#### 📋 When to Use

- Starting a new task
- Need a fresh, clean desktop
- Want to run tasks in parallel (create multiple sessions)

#### 🔄 How It Works

```http
POST /api/sessions
Content-Type: application/json
```

**Request Body:**
```json
{
  "title": "Weather Search Task"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `title` | string | No | "Task HH:MM" | Friendly name for the session |

#### ✅ Success Response

**Status:** `201 Created`

```json
{
  "id": "a1b2c3d4e5f6",
  "title": "Weather Search Task",
  "status": "created",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "vnc_info": {
    "display_num": 111,
    "vnc_port": 5911,
    "novnc_url": "/vnc/?port=5911&autoconnect=true&resize=scale"
  }
}
```

**What each field means:**

| Field | Description | How to Use |
|-------|-------------|------------|
| `id` | Unique session identifier | Use this in all future requests |
| `status` | Current state (`created`, `running`, `idle`) | Know when to send messages |
| `vnc_info.display_num` | Virtual display number (e.g., 111) | For debugging |
| `vnc_info.vnc_port` | WebSocket port for VNC | Connect noVNC viewer |
| `vnc_info.novnc_url` | Ready-to-use URL path | Embed in iframe or link |

#### 📝 Step-by-Step Example

**1. Send the request:**
```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "Search for Hotels"}'
```

**2. Save the session ID from response:**
```bash
# Response:
{
  "id": "abc123def456",  # <-- Save this!
  ...
}
```

**3. View the virtual desktop:**
- Open browser to: `http://localhost:8000/vnc/?port=5911&autoconnect=true`
- You'll see a virtual desktop (starts empty)

**4. You're ready to send messages!**

#### ❌ Error Scenarios

| Error | Status | Cause | Solution |
|-------|--------|-------|----------|
| Database unavailable | 503 | Database not running | Check `GET /health` |
| Display allocation failed | 500 | Xvfb not installed | Check Docker setup |

#### 💡 Tips

- **Create sessions early**: Creation takes 300-500ms (display startup)
- **Reuse sessions**: Don't create a new session for each message
- **Clean up**: Delete sessions when done to free resources

---

### 2. List Sessions

#### 🎯 What Is This?

Retrieves all sessions you've created, with their current status and VNC info.

**Real-world analogy:** Like viewing all the tabs you have open in your browser.

#### 📋 When to Use

- Dashboard showing all active agents
- Finding a session ID you forgot
- Monitoring system usage

#### 🔄 How It Works

```http
GET /api/sessions
```

**No request body needed.**

#### ✅ Success Response

**Status:** `200 OK`

```json
{
  "sessions": [
    {
      "id": "abc123def456",
      "title": "Weather Search",
      "status": "running",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:35:00Z",
      "vnc_info": {
        "display_num": 111,
        "vnc_port": 5911,
        "novnc_url": "/vnc/?port=5911&autoconnect=true"
      }
    },
    {
      "id": "def456ghi789",
      "title": "Email Task",
      "status": "idle",
      "created_at": "2024-01-15T10:32:00Z",
      "updated_at": "2024-01-15T10:36:00Z",
      "vnc_info": {
        "display_num": 112,
        "vnc_port": 5912,
        "novnc_url": "/vnc/?port=5912&autoconnect=true"
      }
    }
  ],
  "total": 2
}
```

#### 📝 Example

```bash
curl http://localhost:8000/api/sessions
```

**Using in JavaScript:**
```javascript
const response = await fetch('/api/sessions');
const { sessions, total } = await response.json();

sessions.forEach(session => {
  console.log(`${session.title}: ${session.status}`);
  // "Weather Search: running"
  // "Email Task: idle"
});
```

#### 💡 Tips

- **Filter by status**: Currently returns all - filter client-side
- **No pagination yet**: For many sessions, consider archiving old ones

---

### 3. Get Session

#### 🎯 What Is This?

Retrieves details about a specific session by its ID.

**Real-world analogy:** Like clicking on a specific tab to see its details.

#### 📋 When to Use

- Checking if a session is still running
- Getting VNC connection info
- Refreshing session status

#### 🔄 How It Works

```http
GET /api/sessions/{session_id}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `session_id` | string | The ID returned when you created the session |

#### ✅ Success Response

**Status:** `200 OK`

```json
{
  "id": "abc123def456",
  "title": "Weather Search Task",
  "status": "running",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:35:00Z",
  "vnc_info": {
    "display_num": 111,
    "vnc_port": 5911,
    "novnc_url": "/vnc/?port=5911&autoconnect=true"
  }
}
```

#### 📝 Example

```bash
curl http://localhost:8000/api/sessions/abc123def456
```

#### ❌ Error Scenarios

| Error | Status | Cause | Solution |
|-------|--------|-------|----------|
| Session not found | 404 | Invalid ID or deleted | Check ID, create new session |

---

### 4. Delete Session

#### 🎯 What Is This?

Permanently deletes a session and releases all its resources (display, VNC, memory).

**Real-world analogy:** Like closing a browser tab and all its processes.

#### 📋 When to Use

- Task is complete
- Session is stuck or errored
- Freeing up system resources

#### ⚠️ Warning

- **Irreversible**: All session data is permanently deleted
- **Stops agent**: If agent is running, it will be cancelled
- **Closes VNC**: Anyone watching will be disconnected

#### 🔄 How It Works

```http
DELETE /api/sessions/{session_id}
```

#### ✅ Success Response

**Status:** `204 No Content`

No response body (that's normal for DELETE).

#### 📝 Step-by-Step Example

**1. Delete the session:**
```bash
curl -X DELETE http://localhost:8000/api/sessions/abc123def456
```

**2. Verify it's gone:**
```bash
curl http://localhost:8000/api/sessions/abc123def456
# Returns: 404 Not Found
```

#### ❌ Error Scenarios

| Error | Status | Cause | Solution |
|-------|--------|-------|----------|
| Session not found | 404 | Already deleted or wrong ID | Check ID |

#### 💡 Tips

- **Clean up regularly**: Each session uses ~80MB RAM
- **Delete completed sessions**: Don't leave them running indefinitely
- **Check status first**: Use GET to see if agent is still working

---

## Message Endpoints

### 5. Send Message

#### 🎯 What Is This?

Sends a task to the AI agent, which will then control the virtual computer to complete it.

**Real-world analogy:** Like telling an assistant "Please search for hotels in Paris" - they'll open a browser, type, and do the search.

#### 📋 When to Use

- Starting a new task
- Continuing a conversation
- Giving follow-up instructions

#### ⚡ Important Behavior

- **Returns immediately**: You get `202 Accepted` in ~50ms
- **Runs in background**: Agent works while you wait
- **Use SSE to watch**: Connect to `/stream` to see progress
- **One at a time**: Can't send new message while agent is working

#### 🔄 How It Works

```http
POST /api/sessions/{session_id}/messages
Content-Type: application/json
```

**Request Body:**
```json
{
  "text": "Search the weather in Dubai"
}
```

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| `text` | string | Yes | Min 1 char | What you want the agent to do |

#### ✅ Success Response

**Status:** `202 Accepted`

```json
{
  "message_id": "msg_a1b2c3d4",
  "status": "processing"
}
```

**What happens next:**
1. Agent receives your message
2. Agent thinks about what to do
3. Agent uses tools (screenshot, click, type, etc.)
4. Events stream via SSE
5. Agent marks task as `done`

#### 📝 Complete Example Workflow

**Step 1: Send the message**
```bash
curl -X POST http://localhost:8000/api/sessions/abc123/messages \
  -H "Content-Type: application/json" \
  -d '{"text": "Open Firefox and go to google.com"}'
```

**Step 2: Connect to SSE stream (in another terminal)**
```bash
curl -N http://localhost:8000/api/sessions/abc123/stream
```

**Step 3: Watch the events flow:**
```
event: text
data: {"text": "I'll open Firefox and navigate to Google."}

event: tool_use
data: {"name": "computer", "input": {"action": "key", "text": "super"}}

event: tool_result
data: {"output": "Key pressed successfully"}

event: tool_use
data: {"name": "computer", "input": {"action": "type", "text": "firefox"}}

event: tool_result
data: {"output": "Typed successfully"}

event: done
data: {"status": "completed"}
```

**Step 4: Now you can send another message!**

#### ❌ Error Scenarios

| Error | Status | Cause | Solution |
|-------|--------|-------|----------|
| Session not found | 404 | Invalid session ID | Check ID, create session |
| Already running | 409 | Agent is busy with previous task | Wait for `done` event, then retry |
| Empty message | 422 | Text is empty | Provide actual instructions |

#### 💡 Tips

- **Be specific**: "Click the search button" is better than "search"
- **One task at a time**: Wait for `done` before sending next message
- **Watch via VNC**: See exactly what the agent sees
- **Use context**: "Now click the second result" - agent remembers previous actions

---

### 6. Get Messages

#### 🎯 What Is This?

Retrieves the complete chat history between you and the agent.

**Real-world analogy:** Like scrolling up in a chat app to see previous messages.

#### 📋 When to Use

- Building a chat UI
- Reviewing what was said
- Debugging agent behavior
- Resuming after page refresh

#### 🔄 How It Works

```http
GET /api/sessions/{session_id}/messages
```

#### ✅ Success Response

**Status:** `200 OK`

```json
{
  "messages": [
    {
      "id": "msg_001",
      "session_id": "abc123def456",
      "role": "user",
      "content": "Search the weather in Dubai",
      "created_at": "2024-01-15T10:30:00Z"
    },
    {
      "id": "msg_002",
      "session_id": "abc123def456",
      "role": "assistant",
      "content": {
        "type": "text",
        "text": "I'll search for the weather in Dubai."
      },
      "created_at": "2024-01-15T10:30:05Z"
    },
    {
      "id": "msg_003",
      "session_id": "abc123def456",
      "role": "assistant",
      "content": {
        "type": "tool_use",
        "name": "computer",
        "input": {"action": "screenshot"}
      },
      "created_at": "2024-01-15T10:30:06Z"
    }
  ],
  "total": 3
}
```

**Message roles:**

| Role | Who | Example Content |
|------|-----|-----------------|
| `user` | You | Plain text string |
| `assistant` | AI Agent | Object with `type` field |
| `tool` | Tool result | Object with output data |

#### 📝 Example

```bash
curl http://localhost:8000/api/sessions/abc123def456/messages
```

**Using in React:**
```javascript
function ChatHistory({ sessionId }) {
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    fetch(`/api/sessions/${sessionId}/messages`)
      .then(res => res.json())
      .then(data => setMessages(data.messages));
  }, [sessionId]);

  return (
    <div>
      {messages.map(msg => (
        <div key={msg.id} className={msg.role}>
          {msg.role === 'user' ? msg.content : msg.content.text}
        </div>
      ))}
    </div>
  );
}
```

---

### 7. Stop Agent

#### 🎯 What Is This?

Immediately stops a running agent task. Use this when the agent is stuck, taking too long, or doing something wrong.

**Real-world analogy:** Like pressing Ctrl+C to stop a program.

#### 📋 When to Use

- Agent is stuck in a loop
- Task is taking too long
- Agent is doing something unintended
- You want to cancel and give new instructions

#### ⚠️ Warning

- **Immediate stop**: Current action may be interrupted mid-way
- **No undo**: Partially completed actions remain
- **Safe to retry**: You can send a new message after stopping

#### 🔄 How It Works

```http
POST /api/sessions/{session_id}/stop
```

#### ✅ Success Response

**Status:** `200 OK`

```json
{
  "status": "stopped",
  "message": "Agent task cancelled"
}
```

#### 📝 Example

```bash
# Agent is stuck, let's stop it
curl -X POST http://localhost:8000/api/sessions/abc123def456/stop

# Now we can send a new message
curl -X POST http://localhost:8000/api/sessions/abc123def456/messages \
  -H "Content-Type: application/json" \
  -d '{"text": "Try a different approach..."}'
```

---

### 8. Restore Session

#### 🎯 What Is This?

Restores a session after the server restarts. Re-creates the virtual display and reconnects to the database record.

**Real-world analogy:** Like recovering browser tabs after a computer restart.

#### 📋 When to Use

- After server restart/deployment
- Session shows as "inactive" but exists in database
- VNC connection dropped

#### 🔄 How It Works

```http
POST /api/sessions/{session_id}/restore
```

#### ✅ Success Response

**Status:** `200 OK`

```json
{
  "status": "restored",
  "session": {
    "id": "abc123def456",
    "title": "Weather Search Task",
    "status": "idle",
    "vnc_info": {
      "display_num": 115,
      "vnc_port": 5915,
      "novnc_url": "/vnc/?port=5915&autoconnect=true"
    }
  }
}
```

**Note:** Display number may change after restore (new allocation).

#### 📝 Example

```bash
# After server restart, restore your session
curl -X POST http://localhost:8000/api/sessions/abc123def456/restore
```

#### 💡 Tips

- **Check health first**: `GET /health` to verify server is ready
- **New VNC port**: Display may be on different port after restore
- **Messages preserved**: Chat history is kept in database

---

## Streaming Endpoints

### 9. SSE Event Stream

#### 🎯 What Is This?

A real-time stream of events showing what the agent is doing. Uses Server-Sent Events (SSE) - a standard web technology for live updates.

**Real-world analogy:** Like watching a live sports game instead of reading about it the next day.

#### 📋 When to Use

- **Always!** Connect before sending a message
- Building a live chat UI
- Debugging agent behavior
- Showing progress indicators

#### ⚡ How SSE Works

```
┌─────────┐                  ┌─────────┐
│ Browser │◀─────────────────│ Server  │
│         │  Long-lived      │         │
│         │  connection      │         │
│         │                  │         │
│         │◀── event: text   │         │
│         │◀── event: tool   │         │
│         │◀── event: done   │         │
└─────────┘                  └─────────┘
```

- Connection stays open (doesn't close after each message)
- Server pushes events as they happen
- No polling needed
- Auto-reconnects if dropped

#### 🔄 How It Works

```http
GET /api/sessions/{session_id}/stream
Accept: text/event-stream
```

**Response:** `200 OK` with `Content-Type: text/event-stream`

#### 📝 Event Types Explained

| Event | When It Fires | What It Contains | Example |
|-------|---------------|------------------|---------|
| `status` | Session state changes | Current status | `{"status": "running"}` |
| `text` | Agent speaks | Text message | `{"text": "I'll help..."}` |
| `thinking` | Agent reasons (optional) | Thinking text | `{"thinking": "Let me..."}` |
| `tool_use` | Agent starts using tool | Tool name + input | `{"name": "computer", "input": {...}}` |
| `tool_result` | Tool finished | Output + screenshot flag | `{"output": "Success"}` |
| `error` | Something went wrong | Error message | `{"message": "Rate limit"}` |
| `done` | Task completed | Final status | `{"status": "completed"}` |

#### 📝 Raw Event Format

```
event: text
data: {"text": "I'll search for the weather in Dubai."}

event: tool_use
data: {"tool_id": "toolu_123", "name": "computer", "input": {"action": "screenshot"}}

event: tool_result
data: {"tool_id": "toolu_123", "output": "Screenshot captured", "has_screenshot": true}

event: done
data: {"status": "completed"}
```

#### 📝 JavaScript Integration (Recommended)

```javascript
// Connect to stream
const sessionId = 'abc123def456';
const eventSource = new EventSource(`/api/sessions/${sessionId}/stream`);

// Handle agent text
eventSource.addEventListener('text', (event) => {
  const data = JSON.parse(event.data);
  addMessage('assistant', data.text);
});

// Handle tool usage (show "Agent is taking screenshot...")
eventSource.addEventListener('tool_use', (event) => {
  const data = JSON.parse(event.data);
  showProgress(`Using ${data.name}: ${data.input.action}`);
});

// Handle tool result
eventSource.addEventListener('tool_result', (event) => {
  const data = JSON.parse(event.data);
  if (data.has_screenshot) {
    // Refresh VNC viewer or fetch screenshot
  }
  hideProgress();
});

// Handle completion
eventSource.addEventListener('done', (event) => {
  showSuccess('Task completed!');
  enableMessageInput();  // Allow next message
  // Don't close - stay connected for next task
});

// Handle errors
eventSource.addEventListener('error', (event) => {
  const data = JSON.parse(event.data);
  showError(data.message);
});

// Handle connection errors
eventSource.onerror = () => {
  console.log('Connection lost, reconnecting...');
  // EventSource auto-reconnects
};
```

#### 📝 React Hook Example

```javascript
function useAgentStream(sessionId) {
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState('idle');

  useEffect(() => {
    const es = new EventSource(`/api/sessions/${sessionId}/stream`);

    es.addEventListener('status', (e) => {
      setStatus(JSON.parse(e.data).status);
    });

    es.addEventListener('text', (e) => {
      const data = JSON.parse(e.data);
      setEvents(prev => [...prev, { type: 'text', ...data }]);
    });

    es.addEventListener('tool_use', (e) => {
      const data = JSON.parse(e.data);
      setEvents(prev => [...prev, { type: 'tool_use', ...data }]);
    });

    es.addEventListener('tool_result', (e) => {
      const data = JSON.parse(e.data);
      setEvents(prev => [...prev, { type: 'tool_result', ...data }]);
    });

    es.addEventListener('done', () => {
      setStatus('idle');
    });

    return () => es.close();
  }, [sessionId]);

  return { events, status };
}

// Usage in component
function AgentChat({ sessionId }) {
  const { events, status } = useAgentStream(sessionId);

  return (
    <div>
      <span>Status: {status}</span>
      {events.map((event, i) => (
        <div key={i}>{event.type}: {JSON.stringify(event)}</div>
      ))}
    </div>
  );
}
```

#### 📝 cURL Example (For Testing)

```bash
# -N disables buffering (required for SSE)
curl -N http://localhost:8000/api/sessions/abc123def456/stream
```

You'll see events appear in real-time as the agent works.

#### 💡 Tips

- **Connect before sending**: Connect to stream first, then send message
- **Don't close on done**: Keep connection for next task
- **Handle reconnection**: EventSource auto-reconnects, but you may miss events
- **Multiple clients OK**: Many clients can watch the same session

---

## System Endpoints

### 10. Health Check

#### 🎯 What Is This?

Returns the system's health status including database connection pool statistics.

**Real-world analogy:** Like checking the dashboard lights in your car.

#### 📋 When to Use

- Monitoring/alerting systems
- Before creating sessions (pre-check)
- Debugging connection issues
- Load balancer health checks

#### 🔄 How It Works

```http
GET /health
```

#### ✅ Success Response

**Status:** `200 OK`

```json
{
  "status": "healthy",
  "active_sessions": 3,
  "database": {
    "pool_size": 2,
    "available": 2,
    "in_use": 0,
    "max_size": 10,
    "total_acquired": 1547,
    "health_checks": 1548
  }
}
```

**What each field means:**

| Field | Description | Healthy Range |
|-------|-------------|---------------|
| `status` | Overall health | `"healthy"` |
| `active_sessions` | Sessions in memory | 0-100 |
| `database.pool_size` | Current connections | 1-10 |
| `database.available` | Ready to use | > 0 |
| `database.in_use` | Currently busy | < max_size |
| `database.max_size` | Maximum allowed | 10 |
| `database.total_acquired` | Lifetime usage | Increases |
| `database.health_checks` | Validation count | Increases |

#### ❌ Unhealthy Response

**Status:** `503 Service Unavailable`

```json
{
  "status": "unhealthy",
  "error": "Database connection failed"
}
```

#### 📝 Example

```bash
# Quick health check
curl http://localhost:8000/health

# With jq for parsing
curl -s http://localhost:8000/health | jq '.status'
```

#### 💡 Monitoring Tips

```bash
# Simple monitoring loop
while true; do
  status=$(curl -s http://localhost:8000/health | jq -r '.status')
  if [ "$status" != "healthy" ]; then
    echo "ALERT: Service unhealthy!"
  fi
  sleep 30
done
```

---

## Data Models

### Session Status Values

| Status | Meaning | Can Send Message? |
|--------|---------|-------------------|
| `created` | Just created, never used | Yes |
| `running` | Agent is working | No (409 error) |
| `idle` | Waiting for input | Yes |
| `completed` | Task finished | Yes |
| `error` | Error occurred | Yes (might recover) |

### Message Roles

| Role | Source | Content Format |
|------|--------|----------------|
| `user` | You | Plain string |
| `assistant` | AI Agent | Object with `type` |
| `tool` | Tool execution | Object with `output` |

### VNC Info Object

```json
{
  "display_num": 111,
  "vnc_port": 5911,
  "novnc_url": "/vnc/?port=5911&autoconnect=true&resize=scale"
}
```

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `display_num` | integer | X11 display (DISPLAY=:111) | 111 |
| `vnc_port` | integer | WebSocket port | 5911 |
| `novnc_url` | string | URL path for viewer | Use with base URL |

### Tool Input Actions

The agent can use these tools:

| Action | Description | Input Example |
|--------|-------------|---------------|
| `screenshot` | Capture screen | `{"action": "screenshot"}` |
| `click` | Click at coordinates | `{"action": "click", "coordinate": [500, 300]}` |
| `type` | Type text | `{"action": "type", "text": "hello"}` |
| `key` | Press key | `{"action": "key", "text": "Return"}` |
| `scroll` | Scroll direction | `{"action": "scroll", "coordinate": [500, 300], "direction": "down"}` |
| `move` | Move mouse | `{"action": "mouse_move", "coordinate": [500, 300]}` |

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | When It Happens |
|------|---------|-----------------|
| `200 OK` | Success | GET requests, successful actions |
| `201 Created` | Resource created | POST /sessions |
| `202 Accepted` | Processing started | POST /messages |
| `204 No Content` | Deleted | DELETE /sessions/{id} |
| `404 Not Found` | Resource missing | Invalid session ID |
| `409 Conflict` | Can't do that now | Message while agent running |
| `422 Unprocessable` | Invalid input | Empty message text |
| `503 Unavailable` | System error | Database down |

### Error Response Format

All errors return JSON:

```json
{
  "detail": "Human-readable error message"
}
```

### Common Errors and Solutions

#### 404: Session Not Found

```json
{"detail": "Session not found"}
```

**Causes:**
- Session ID is wrong
- Session was deleted
- Session never existed

**Solutions:**
```bash
# List all sessions to find correct ID
curl http://localhost:8000/api/sessions

# Create a new session if needed
curl -X POST http://localhost:8000/api/sessions
```

#### 409: Already Running

```json
{"detail": "Session already running"}
```

**Causes:**
- Agent is still processing previous message
- You sent two messages too quickly

**Solutions:**
```bash
# Wait for the 'done' event in SSE stream

# Or stop the current task
curl -X POST http://localhost:8000/api/sessions/{id}/stop

# Then send your message
curl -X POST http://localhost:8000/api/sessions/{id}/messages \
  -d '{"text": "new task"}'
```

#### 422: Validation Error

```json
{"detail": [{"loc": ["body", "text"], "msg": "field required", "type": "value_error.missing"}]}
```

**Causes:**
- Missing required field
- Invalid field type
- Value too short/long

**Solutions:**
```bash
# Include required fields
curl -X POST http://localhost:8000/api/sessions/{id}/messages \
  -H "Content-Type: application/json" \
  -d '{"text": "Your message here"}'  # Don't forget "text" field!
```

#### 503: Service Unavailable

```json
{"detail": "Database unavailable"}
```

**Causes:**
- Database not running
- Connection pool exhausted
- System overloaded

**Solutions:**
```bash
# Check health endpoint
curl http://localhost:8000/health

# Wait and retry
sleep 5 && curl http://localhost:8000/api/sessions
```

---

## Quick Reference

### All Endpoints at a Glance

| Method | Endpoint | Status | Description |
|--------|----------|--------|-------------|
| `POST` | `/api/sessions` | 201 | Create new session |
| `GET` | `/api/sessions` | 200 | List all sessions |
| `GET` | `/api/sessions/{id}` | 200 | Get session details |
| `DELETE` | `/api/sessions/{id}` | 204 | Delete session |
| `POST` | `/api/sessions/{id}/messages` | 202 | Send message to agent |
| `GET` | `/api/sessions/{id}/messages` | 200 | Get chat history |
| `GET` | `/api/sessions/{id}/stream` | 200 | SSE event stream |
| `POST` | `/api/sessions/{id}/stop` | 200 | Stop running agent |
| `POST` | `/api/sessions/{id}/restore` | 200 | Restore session |
| `GET` | `/health` | 200 | Health check |

### Common Workflows

#### Basic Task Execution

```bash
# 1. Create session
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/sessions | jq -r '.id')

# 2. Start SSE listener (background)
curl -N http://localhost:8000/api/sessions/$SESSION_ID/stream &

# 3. Send task
curl -X POST http://localhost:8000/api/sessions/$SESSION_ID/messages \
  -H "Content-Type: application/json" \
  -d '{"text": "Open Firefox and search for weather"}'

# 4. Wait for done event, then clean up
curl -X DELETE http://localhost:8000/api/sessions/$SESSION_ID
```

#### Multi-Session Parallel Execution

```bash
# Create two sessions
SESSION1=$(curl -s -X POST http://localhost:8000/api/sessions -d '{"title":"Task 1"}' | jq -r '.id')
SESSION2=$(curl -s -X POST http://localhost:8000/api/sessions -d '{"title":"Task 2"}' | jq -r '.id')

# Send tasks to both (they run in parallel!)
curl -X POST http://localhost:8000/api/sessions/$SESSION1/messages -d '{"text":"Task 1..."}'
curl -X POST http://localhost:8000/api/sessions/$SESSION2/messages -d '{"text":"Task 2..."}'

# Both agents work simultaneously on different displays
```

---

**Author:** Muhammed Refaat
**Version:** 2.0.0 - Enhanced for Clarity
**Last Updated:** March 2026
