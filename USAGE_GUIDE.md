# Computer Use Agent - Usage Guide

## ✅ System Architecture

This system implements a **fully concurrent, dynamically scalable** Computer-Use agent with NO hardcoded session limits.

### Core Features

- ✅ **Dynamic Worker Spawning**: Each new session automatically spawns:
  - Isolated Xvfb display (`:100`, `:101`, `:102`, ...)
  - Dedicated x11vnc server (ports 5810, 5811, ...)
  - WebSocket proxy (ports 5910, 5911, ...)

- ✅ **True Parallelism**: Tasks run simultaneously in separate asyncio Tasks with isolated displays
- ✅ **Real-time Streaming**: SSE events stream progress for each step
- ✅ **Session Persistence**: SQLite database stores all chat history
- ✅ **Firefox Support**: Each session can launch Firefox independently

---

## 🚀 Quick Start

### Prerequisites

```bash
# Set API key in .env file
echo "ANTHROPIC_API_KEY=your_key_here" > .env
# OR for Gemini
echo "GEMINI_API_KEY=your_google_api_key" > .env
```

### Build and Run

```bash
# Build Docker image
cd computer-use-demo
docker build -t computer-use-agent .

# Run container
docker run -d \
  -p 8000:8000 \
  -p 6080:6080 \
  -p 5810-5899:5810-5899 \
  -p 5910-5999:5910-5999 \
  --env-file .env \
  --name computer-use \
  computer-use-agent

# Access the UI
open http://localhost:8000
```

---

## 📋 Usage Case 1: Single Session with Firefox

### Steps:

1. **Open the UI**: Navigate to `http://localhost:8000`

2. **Create New Session**: Click **"+ New Task"** button in the left sidebar

3. **Send Prompt**: In the chat input (right panel), type:
   ```
   Search the weather in Dubai
   ```
   Press **Send** or hit **Enter**

4. **Observe Real-time Execution**:
   - **Right Panel (Chat)**: Shows streaming updates:
     - 🤖 Agent thinking
     - 🔧 Tool calls (bash, computer)
     - 📸 Screenshots
     - ✅ Results

   - **Middle Panel (VNC)**: Watch the virtual desktop live:
     - Firefox opens automatically
     - Google search executes
     - Weather results appear

5. **View Result**: Agent summarizes the weather in Dubai in the chat

### Expected Behavior:

- ✅ Firefox-esr launches in the VNC window
- ✅ Google search executes for "weather in Dubai"
- ✅ Agent extracts and summarizes weather information
- ✅ All steps stream in real-time to the chat panel
- ✅ Status changes: `created` → `running` → `idle`

---

## 🔥 Usage Case 2: CONCURRENT PARALLEL Sessions (Critical!)

This demonstrates **TRUE PARALLELISM** - NOT queuing!

### Setup:

1. Open **TWO browser windows** side-by-side (e.g., Chrome Tab 1 and Chrome Tab 2)
2. Navigate both to `http://localhost:8000`

### Execution:

**In Browser Window 1:**
1. Click **"+ New Task"**
2. Type: `Search the weather in Tokyo`
3. Click **Send**
4. ⏱️ **IMMEDIATELY** (don't wait for completion), proceed to Window 2

**In Browser Window 2:**
1. Click **"+ New Task"**
2. Type: `Search the weather in New York`
3. Click **Send**

### Visual Verification ✅

You should observe **SIMULTANEOUSLY**:

| Window 1 (Tokyo Session) | Window 2 (NY Session) |
|--------------------------|----------------------|
| VNC shows Firefox opening on Display `:100` | VNC shows Firefox opening on Display `:101` |
| Chat streams "Using bash to launch firefox" | Chat streams "Using bash to launch firefox" |
| Google search for Tokyo weather | Google search for NY weather |
| Status: `running` | Status: `running` |

### Critical Requirements:

- ⚠️ **BOTH tasks MUST start processing immediately**
- ⚠️ **Second task CANNOT wait for first to finish**
- ⚠️ **Each session MUST have its own Firefox window** (different displays)
- ⚠️ **Both VNC viewers show different screens**

### System Logs Verification:

```bash
# Check that displays are allocated dynamically
docker logs computer-use 2>&1 | grep "Allocated display"
# Expected output:
# Allocated display :100 with VNC on port 5810 -> WS on port 5910
# Allocated display :101 with VNC on port 5811 -> WS on port 5911
```

---

## 🎨 UI Layout (as per requirements)

```
┌────────────────────────────────────────────────────────────────┐
│  Left Panel (280px)        │  Middle Panel   │  Right Panel    │
│  ─────────────────────     │  ────────────   │  ────────────   │
│  🤖 Computer Use           │                 │  Agent Chat     │
│  [+ New Task]              │                 │  Status: Idle   │
│                            │                 │                 │
│  Task History:             │  Virtual        │  ┌────────────┐ │
│  ┌──────────────────┐      │  Desktop        │  │ Chat       │ │
│  │ ● Tokyo Weather  │      │  (VNC iframe)   │  │ Messages   │ │
│  │   running • 2:15 │      │                 │  │            │ │
│  └──────────────────┘      │  [Live screen]  │  │ 👤 You:    │ │
│  ┌──────────────────┐      │                 │  │ Search...  │ │
│  │ ○ NY Weather     │      │                 │  │            │ │
│  │   idle • 2:14    │      │                 │  │ 🤖 Agent:  │ │
│  └──────────────────┘      │                 │  │ Using...   │ │
│                            │                 │  └────────────┘ │
│  Status: Connected         │  Display: :100  │  ┌────────────┐ │
│  (2 active sessions)       │                 │  │ [Input]    │ │
│                            │                 │  └────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Firefox Launch Commands

The agent can launch Firefox using the bash tool:

```bash
# Agent automatically executes:
DISPLAY=:100 firefox-esr "https://www.google.com/search?q=weather+in+Dubai" &
```

**Manual trigger** (if you want to test Firefox directly):
```bash
docker exec -it computer-use bash
DISPLAY=:100 firefox-esr &
```

---

## 📊 Concurrent Session Architecture

```
User Request → FastAPI → SessionManager.create_session()
                              ↓
                    DisplayManager.allocate_display()
                              ↓
                    ┌─────────────────────────┐
                    │ Spawn Xvfb :100         │
                    │ Spawn x11vnc :5810      │
                    │ Spawn websockify :5910  │
                    └─────────────────────────┘
                              ↓
                    Create ToolCollection (DISPLAY=:100)
                              ↓
                    asyncio.create_task(run_agent_loop)
                              │
                              │ (Runs in parallel)
                              │
                    SSE stream → Frontend

                    (Multiple sessions = Multiple tasks running simultaneously)
```

---

## ✅ Verification Checklist

- [ ] Can create multiple sessions without delays
- [ ] Each session has unique display number (`:100`, `:101`, ...)
- [ ] VNC viewers show different screens for different sessions
- [ ] Tasks process in parallel (not queued)
- [ ] Firefox launches successfully in each session
- [ ] Real-time SSE updates work for all sessions
- [ ] Chat history persists in database
- [ ] Cleanup works (displays released on session delete)

---

## 🐛 Troubleshooting

### Firefox doesn't open
```bash
# Check if Firefox is installed in container
docker exec computer-use which firefox-esr
# Expected: /usr/bin/firefox-esr

# Manually test
docker exec -it computer-use bash
DISPLAY=:100 firefox-esr &
```

### Second session waits for first
**This is a FAILURE!** The system should handle concurrent sessions.
- Check logs: `docker logs computer-use`
- Verify: Each session should show `asyncio.create_task(agent-...)`

### VNC connection fails
```bash
# Check websockify processes
docker exec computer-use ps aux | grep websockify
# Should show multiple processes on different ports
```

---

## 📝 Notes

- **No session limit**: System dynamically spawns workers for unlimited concurrent sessions
- **Automatic cleanup**: Displays are released when sessions are deleted
- **Resource usage**: Each session uses ~200MB RAM (Xvfb + Firefox)
- **Port range**: Port exposure in docker run ensures VNC accessibility

---

## 🎯 Success Criteria

✅ **Usage Case 1**: Single session opens Firefox and completes Google search with real-time updates

✅ **Usage Case 2**: Two concurrent sessions run simultaneously without blocking, each with independent Firefox instances

✅ **Architecture**: No hardcoded session limits, dynamic worker spawning, proper isolation
