# Getting Started

> Complete setup guide — from zero to a running, multi-session Computer Use Agent.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone & Configure](#2-clone--configure)
3. [Environment Variables](#3-environment-variables)
4. [Build & Run (Docker — Recommended)](#4-build--run-docker--recommended)
5. [Database Setup](#5-database-setup)
6. [Run Commands Reference](#6-run-commands-reference)
7. [Verify Installation](#7-verify-installation)
8. [Common Issues & Troubleshooting](#8-common-issues--troubleshooting)

---

## 1. Prerequisites

### Required

| Dependency | Minimum Version | Verify Command | Notes |
|---|---|---|---|
| **Docker** | 20.10+ | `docker --version` | Container runtime |
| **Docker Compose** | 2.0+ (v2 plugin) | `docker compose version` | Multi-container orchestration |
| **API Key** | — | — | Either Anthropic or Google Gemini (at least one) |

### Optional (for local development without Docker)

| Dependency | Minimum Version | Verify Command | Notes |
|---|---|---|---|
| **Python** | 3.11.x (≤3.12) | `python3 --version` | ⚠️ Python 3.13+ is **not supported** |
| **Rust/Cargo** | Latest stable | `cargo --version` | Required by some pip dependencies |
| **Xvfb** | System | `which Xvfb` | Virtual display (Linux only) |
| **x11vnc** | System | `which x11vnc` | VNC server (Linux only) |
| **xdotool** | System | `which xdotool` | Input simulation (Linux only) |
| **ImageMagick** | System | `convert --version` | Screenshot processing |
| **Firefox ESR** | System | `firefox-esr --version` | Browser for agent tasks |

> **Note:** Local development without Docker is only possible on Linux due to X11 display dependencies. macOS and Windows users should use Docker.

---

## 2. Clone & Configure

```bash
# Clone the repository
git clone https://github.com/<your-org>/Energent.ai-Challenge-Claude-Computer-Use-.git
cd Energent.ai-Challenge-Claude-Computer-Use-/computer-use-demo

# Copy the environment template
cp .env.example .env
```

### Project Layout After Clone

```
computer-use-demo/
├── .env.example          ← Template (copy to .env)
├── .env                  ← Your local config (git-ignored)
├── Dockerfile            ← Multi-stage Docker build
├── docker-compose.yml    ← Container orchestration
├── build.sh              ← Docker build helper script
├── setup.sh              ← Local dev setup script
├── computer_use_demo/    ← Python backend source
├── frontend/             ← Web UI (HTML/JS/CSS)
├── image/                ← Container entrypoint & desktop scripts
├── tests/                ← Test suite
└── docs/                 ← Documentation (you are here)
```

---

## 3. Environment Variables

Edit the `.env` file with your configuration:

```bash
# ──────────────────────────────────────────────────
# Required: At least ONE API key must be set
# ──────────────────────────────────────────────────

# Option A: Anthropic Claude (recommended)
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxx

# Option B: Google Gemini (alternative)
# GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxx

# ──────────────────────────────────────────────────
# Optional: Model & API Configuration
# ──────────────────────────────────────────────────

# Override the default Claude model (default: claude-sonnet-4-5-20250929)
# ANTHROPIC_MODEL=claude-haiku-4-5-20251001

# Custom API endpoint (e.g., for Azure-hosted Anthropic proxy)
# ANTHROPIC_BASE_URL=https://your-proxy.example.com

# ──────────────────────────────────────────────────
# Optional: Display Configuration
# ──────────────────────────────────────────────────

# Virtual display resolution (default: 1024x768)
WIDTH=1024
HEIGHT=768

# ──────────────────────────────────────────────────
# Optional: Database Configuration
# ──────────────────────────────────────────────────

# SQLite database path inside the container (default: /data/sessions.db)
# DB_PATH=/data/sessions.db

# Connection pool sizing (default: min=2, max=10)
# DB_POOL_MIN_SIZE=2
# DB_POOL_MAX_SIZE=10

# ──────────────────────────────────────────────────
# Optional: Application Configuration
# ──────────────────────────────────────────────────

# Enable debug mode (default: false)
# DEBUG=true

# Logging level (default: INFO)
# LOG_LEVEL=DEBUG
```

### Complete Environment Variable Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes* | — | Anthropic Claude API key |
| `GEMINI_API_KEY` | Yes* | — | Google Gemini API key (alternative) |
| `ANTHROPIC_BASE_URL` | No | `https://api.anthropic.com` | Custom API endpoint |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-5-20250929` | Model identifier |
| `WIDTH` | No | `1024` | Virtual display width (px) |
| `HEIGHT` | No | `768` | Virtual display height (px) |
| `DB_PATH` | No | `/data/sessions.db` | SQLite database file path |
| `DB_POOL_MIN_SIZE` | No | `2` | Minimum DB connection pool size |
| `DB_POOL_MAX_SIZE` | No | `10` | Maximum DB connection pool size |
| `DB_POOL_ACQUIRE_TIMEOUT` | No | `30.0` | Seconds to wait for a DB connection |
| `LOG_LEVEL` | No | `INFO` | Python logging level |
| `DEBUG` | No | `false` | Enable FastAPI debug mode |

> \* At least one API key is required. The system auto-detects the provider: keys starting with `AIza` are treated as Gemini keys, all others as Anthropic keys.

---

## 4. Build & Run (Docker — Recommended)

### Option A: Using Docker Compose (Recommended)

```bash
# Build and start (foreground — see logs in terminal)
docker compose up --build

# Or run in detached mode
docker compose up --build -d

# View logs when running detached
docker compose logs -f
```

### Option B: Using the Build Helper Script

The `build.sh` script handles common Docker issues automatically:

```bash
chmod +x build.sh
./build.sh
```

The script will:
1. Verify Docker is running
2. Pre-pull the base image (`ubuntu:22.04`)
3. Optionally clear the Docker build cache
4. Build the image with `docker-compose build --no-cache`
5. Create a `.env` template if one doesn't exist

### Option C: Manual Docker Build

```bash
# Build the image directly
docker build -t computer-use-agent .

# Run the container
docker run -d \
  --name computer-use \
  -p 8000:8000 \
  -p 6080:6080 \
  -p 5910-5999:5910-5999 \
  -v session-data:/data \
  --env-file .env \
  --security-opt seccomp=unconfined \
  --security-opt apparmor=unconfined \
  --cpus 4.0 \
  --memory 4g \
  computer-use-agent
```

### Port Mapping

| Host Port | Container Port | Service |
|---|---|---|
| `8000` | `8000` | FastAPI backend + frontend UI |
| `6080` | `6080` | Default noVNC display (display `:1`) |
| `5910–5999` | `5910–5999` | Dynamic WebSocket VNC ports for concurrent sessions |

### What Happens on Startup

1. **`entrypoint.sh`** executes as PID 1:
   - Starts `Xvfb` for default display `:1`
   - Starts `tint2` (taskbar) and `mutter` (window manager)
   - Starts `x11vnc` for VNC access to default display
   - Starts `noVNC` proxy on port `6080`
   - Creates `/data` directory for SQLite
   - Launches `uvicorn` serving FastAPI on port `8000`
2. **FastAPI `lifespan` startup**:
   - Initializes database schema (`sessions` + `messages` tables)
   - Creates connection pool (`min=2` connections)
3. Outputs: _"✨ Computer Use API is ready!"_

---

## 5. Database Setup

> **No manual database setup is required.** The system automatically creates and initializes the SQLite database on first startup.

### Automatic Setup

On startup, the FastAPI lifespan handler calls `db.init_db()` which:

1. Creates the SQLite file at `DB_PATH` (default: `/data/sessions.db`)
2. Enables WAL journal mode for concurrent read/write
3. Creates the `sessions` table
4. Creates the `messages` table with foreign key to sessions
5. Creates the index `idx_messages_session_id` on `(session_id, created_at)`

### Data Persistence

The `docker-compose.yml` mounts a named Docker volume:

```yaml
volumes:
  - session-data:/data
```

This means:
- **Data survives container restarts** (the volume persists)
- **Data survives image rebuilds** (volumes are independent of images)
- To **reset the database**, remove the volume: `docker volume rm computer-use-demo_session-data`

### Manual Database Inspection

```bash
# Shell into the running container
docker compose exec computer-use bash

# Open the database with SQLite CLI
sqlite3 /data/sessions.db

# Example queries
.tables                                    -- List tables
SELECT * FROM sessions;                     -- View all sessions
SELECT COUNT(*) FROM messages;              -- Count messages
SELECT * FROM messages WHERE session_id = 'abc123' ORDER BY created_at;

# Exit
.quit
```

---

## 6. Run Commands Reference

### Docker Operations

```bash
# Start the stack
docker compose up --build

# Start in background
docker compose up --build -d

# Stop the stack
docker compose down

# Stop and remove volumes (resets database)
docker compose down -v

# View logs
docker compose logs -f

# Shell into the container
docker compose exec computer-use bash

# Rebuild without cache (clean build)
docker compose build --no-cache
```

### Accessing the Application

| URL | Description |
|---|---|
| `http://localhost:8000` | Main frontend UI |
| `http://localhost:8000/docs` | Swagger API documentation |
| `http://localhost:8000/health` | Health check with DB pool stats |
| `http://localhost:8000/test` | Concurrent sessions test page |
| `http://localhost:6080` | Default noVNC display (display `:1`) |

### Quick Smoke Test

```bash
# 1. Health check
curl http://localhost:8000/health | python3 -m json.tool

# 2. Create a session
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Session"}' | python3 -m json.tool

# 3. List sessions
curl http://localhost:8000/api/sessions | python3 -m json.tool

# 4. Send a message (replace SESSION_ID)
curl -X POST http://localhost:8000/api/sessions/SESSION_ID/messages \
  -H "Content-Type: application/json" \
  -d '{"text": "Take a screenshot of the desktop"}'

# 5. Watch SSE stream (replace SESSION_ID)
curl -N http://localhost:8000/api/sessions/SESSION_ID/stream
```

---

## 7. Verify Installation

### Step 1: Check Health

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

Expected response:
```json
{
    "status": "healthy",
    "active_sessions": 0,
    "database": {
        "pool_size": 2,
        "available": 2,
        "in_use": 0,
        "max_size": 10,
        "total_acquired": 1,
        "health_checks": 1
    }
}
```

### Step 2: Open the Frontend

Navigate to `http://localhost:8000` in your browser. You should see:
- **Left sidebar**: Session list (empty on first run)
- **Center panel**: VNC viewer placeholder
- **Right panel**: Chat interface

### Step 3: Create a Session and Run a Task

1. Click **"New Task"** in the UI
2. A VNC viewer should appear showing a Linux desktop
3. Type a task: _"Open Firefox and search for 'hello world'"_
4. Watch the agent stream its actions in real-time

### Step 4: Test Concurrent Sessions

1. Open two browser tabs to `http://localhost:8000`
2. Create a new session in each tab
3. Give them both tasks simultaneously
4. Verify both VNC viewers show independent Firefox instances

---

## 8. Common Issues & Troubleshooting

### Docker Build Fails

| Symptom | Cause | Fix |
|---|---|---|
| `unable to pull ubuntu:22.04` | Docker network/DNS issue | Run `docker pull docker.io/library/ubuntu:22.04` manually, or set Docker DNS to `8.8.8.8` |
| Build hangs on `apt-get` | Slow network or mirror | Add `--build-arg HTTP_PROXY=...` if behind a proxy |
| `No space left on device` | Docker disk full | Run `docker system prune -a` |

### Container Starts but API Fails

| Symptom | Cause | Fix |
|---|---|---|
| `ANTHROPIC_API_KEY not set` | Missing `.env` or key not set | Verify `.env` file exists and contains a valid key |
| `curl: connection refused` on port 8000 | Uvicorn not started yet | Wait 15–30 seconds for full startup; check `docker compose logs` |
| Health returns `null` database | DB init failed | Check container logs: `docker compose logs \| grep -i error` |

### Agent Doesn't Work

| Symptom | Cause | Fix |
|---|---|---|
| SSE stream shows `API Error: 401` | Invalid API key | Verify your `ANTHROPIC_API_KEY` is correct and active |
| SSE stream shows `API Error: 429` | Rate limited | Reduce concurrent sessions or upgrade API plan |
| Agent seems stuck | LLM timeout or Firefox issue | Check container logs; try `POST .../stop` then resend message |
| VNC shows black screen | Display didn't start | Check `docker compose logs \| grep Xvfb` |

### Firefox Issues

| Symptom | Cause | Fix |
|---|---|---|
| "Firefox is already running" error | Shared profile between sessions | The `firefox_wrapper.sh` handles this; ensure it's installed at `/usr/local/bin/firefox` |
| Firefox doesn't open | `DISPLAY` not set correctly | Verify `DISPLAY_NUM` env var is being passed to tools |

### Performance

| Symptom | Cause | Fix |
|---|---|---|
| Slow screenshots | ImageMagick scaling | Resolution scaling only kicks in for resolutions > XGA |
| Container OOM killed | Too many concurrent sessions | Each session uses ~200–400MB. Increase Docker memory limit. |
| DB timeout errors | Connection pool exhausted | Increase `DB_POOL_MAX_SIZE` |
