# System Architecture

## Overview

This is an **AI Agent API** built with FastAPI that provides a Claude-powered computer-use agent with streaming capabilities. The system enables users to interact with an AI agent that can execute computer tasks through a RESTful API with WebSocket streaming support.

## High-Level Architecture

```
┌─────────────────┐
│   API Client    │
└────────┬────────┘
         │
         │ HTTP/WebSocket
         │
┌────────▼────────┐
│   FastAPI App   │
│  (main.py)      │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼──┐  ┌──▼──────┐
│ REST │  │WebSocket│
│Routes│  │ Stream  │
└───┬──┘  └──┬──────┘
    │        │
    │    ┌───▼───────┐
    │    │  Events   │
    │    │ Publisher │
    │    └───────────┘
    │
┌───▼──────────────┐
│ Session Manager  │
└───┬──────────────┘
    │
┌───▼──────────────┐
│  Agent Service   │
│  (Core Logic)    │
└───┬──────────────┘
    │
┌───┴───┬──────┬───┐
│       │      │   │
│  LLM  │Tools │DB │
│Client │Exec  │   │
│       │      │   │
└───────┴──────┴───┘
```

## Directory Structure

```
app/
├── main.py                         # FastAPI entrypoint
│
├── api/
│   ├── routes/
│   │   ├── sessions.py            # create/list sessions
│   │   └── agent.py               # send user message
│   │
│   └── websocket/
│       └── stream.py              # WebSocket streaming endpoint
│
├── services/
│   ├── agent/
│   │   ├── agent_service.py       # 🔥 core logic (LLM + tools loop)
│   │   ├── agent_runner.py        # background task runner (asyncio)
│   │   └── message_manager.py     # message formatting + history
│   │
│   ├── session/
│   │   └── session_manager.py     # session lifecycle management
│   │
│   └── tools/
│       ├── executor.py            # wraps ToolCollection
│       ├── bash.py                # refactored (stateless)
│       ├── computer.py            # refactored
│       └── edit.py                # refactored
│
├── core/
│   ├── llm/
│   │   └── client.py              # Anthropic wrapper
│   │
│   ├── tools/
│   │   ├── base.py                # ✅ reused
│   │   ├── collection.py          # ✅ reused
│   │   └── groups.py              # ✅ reused
│   │
│   ├── execution/
│   │   └── run.py                 # ✅ reused
│   │
│   └── events/
│       └── publisher.py           # event emitter (WebSocket bridge)
│
├── schemas/
│   ├── agent.py                   # request/response models
│   ├── session.py                 # session models
│   └── event.py                   # 🔥 streaming event schema
│
├── db/
│   ├── models.py                  # SQLAlchemy models
│   ├── repository.py              # DB abstraction layer
│   └── database.py                # DB connection/session
│
├── config/
│   └── settings.py                # env/config management
│
└── utils/
    └── logger.py                  # logging (optional but strong)
```

## Core Components

### 1. API Layer (`app/api/`)

**Purpose:** Handle HTTP and WebSocket connections, route requests to appropriate services.

#### Routes (`app/api/routes/`)
- **sessions.py**: Manages session creation and listing
  - `POST /sessions` - Create new agent session
  - `GET /sessions` - List all sessions
  - `GET /sessions/{id}` - Get session details

- **agent.py**: Handles user messages to the agent
  - `POST /agent/message` - Send message to agent
  - Returns immediate acknowledgment, actual processing happens asynchronously

#### WebSocket (`app/api/websocket/`)
- **stream.py**: Real-time event streaming endpoint
  - `WS /ws/{session_id}` - Connect to session event stream
  - Pushes agent thoughts, tool calls, results, and responses in real-time

### 2. Services Layer (`app/services/`)

**Purpose:** Business logic and orchestration.

#### Agent Service (`app/services/agent/`)

**agent_service.py** - The heart of the system
- Implements the agent reasoning loop
- Coordinates between LLM, tools, and message history
- Flow:
  1. Receive user message
  2. Format conversation history
  3. Call LLM with available tools
  4. Process tool calls (if any)
  5. Execute tools via executor
  6. Feed results back to LLM
  7. Repeat until final response
  8. Emit events at each step

**agent_runner.py** - Background execution
- Runs agent loop asynchronously using asyncio
- Prevents blocking the API
- Manages concurrent agent sessions

**message_manager.py** - Message handling
- Formats messages for Anthropic API
- Maintains conversation history
- Handles system prompts and context

#### Session Service (`app/services/session/`)

**session_manager.py**
- Creates and manages agent sessions
- Tracks session state (active, completed, errored)
- Provides session lifecycle hooks
- Stores sessions in database

#### Tools Service (`app/services/tools/`)

**executor.py**
- Wraps `ToolCollection` from core
- Executes tool calls from LLM responses
- Handles tool errors and validation
- Returns structured results

**Tool Implementations** (bash.py, computer.py, edit.py)
- Refactored to be stateless
- Each tool is a standalone function/class
- Takes parameters, returns results
- No shared state between calls

### 3. Core Layer (`app/core/`)

**Purpose:** Reusable, framework-agnostic business logic.

#### LLM (`app/core/llm/`)

**client.py**
- Wrapper around Anthropic SDK
- Handles API authentication
- Formats requests/responses
- Implements retries and error handling
- Supports streaming responses

#### Tools (`app/core/tools/`)

**base.py**
- Base tool interface/abstract class
- Defines tool contract (name, description, schema, execute)

**collection.py**
- Registry of available tools
- Manages tool discovery and execution
- Validates tool inputs

**groups.py**
- Organizes tools into logical groups
- Allows enabling/disabling tool sets
- Example groups: bash, computer, editing

#### Execution (`app/core/execution/`)

**run.py**
- Manages tool execution environment
- Handles subprocess management for bash tools
- Implements timeouts and resource limits
- Captures stdout/stderr

#### Events (`app/core/events/`)

**publisher.py**
- Event emitter pattern
- Bridges agent events to WebSocket clients
- Event types:
  - `agent.thinking` - LLM reasoning
  - `tool.called` - Tool invocation
  - `tool.result` - Tool output
  - `agent.response` - Final answer
  - `agent.error` - Error occurred

### 4. Data Layer (`app/db/`)

**models.py**
- SQLAlchemy ORM models
- Tables:
  - `Session` - Agent sessions
  - `Message` - Conversation history
  - `ToolCall` - Tool execution log (optional)

**repository.py**
- Data access abstraction
- CRUD operations
- Query helpers
- Hides SQLAlchemy details from services

**database.py**
- Database connection management
- Session factory
- Migration support (Alembic)

### 5. Schemas (`app/schemas/`)

Pydantic models for request/response validation.

**agent.py**
- `MessageRequest` - User message input
- `MessageResponse` - Agent response
- `ToolCallSchema` - Tool execution details

**session.py**
- `SessionCreate` - Session creation params
- `SessionResponse` - Session details
- `SessionList` - List of sessions

**event.py**
- `StreamEvent` - WebSocket event structure
- `EventType` - Event type enum
- `EventPayload` - Event data

### 6. Configuration (`app/config/`)

**settings.py**
- Environment variable management
- Configuration classes
- Secrets handling (API keys)
- Database URLs
- CORS settings

### 7. Utilities (`app/utils/`)

**logger.py**
- Centralized logging configuration
- Structured logging (JSON format)
- Log levels per module
- Request ID tracking

## Data Flow

### 1. Session Creation
```
Client → POST /sessions → SessionManager → DB → SessionResponse
```

### 2. Message Processing (Async)
```
Client → POST /agent/message → AgentRunner (background)
                                    ↓
                              AgentService
                                    ↓
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
              MessageManager    LLMClient    ToolExecutor
                    ↓               ↓               ↓
              [Format history] [Call Claude] [Run tools]
                    └───────────────┬───────────────┘
                                    ↓
                              EventPublisher → WebSocket
```

### 3. Real-time Streaming
```
Client ←→ WS /ws/{session_id} ←→ EventPublisher ←← AgentService
         (bidirectional)              (events)      (processing)
```

## Design Patterns & Principles

### 1. **Separation of Concerns**
- API layer: routing and validation
- Service layer: business logic
- Core layer: reusable components
- Data layer: persistence

### 2. **Dependency Injection**
- Services receive dependencies via constructors
- Easier testing and mocking
- FastAPI's `Depends()` for route dependencies

### 3. **Event-Driven Architecture**
- Agent emits events during execution
- WebSocket clients subscribe to events
- Decouples processing from communication

### 4. **Repository Pattern**
- Database operations abstracted behind repository
- Swappable data sources
- Simplified testing

### 5. **Stateless Tools**
- Tools don't maintain state between calls
- Easier to parallelize and scale
- More predictable behavior

### 6. **Async/Await**
- Non-blocking I/O throughout
- Background task processing
- Better resource utilization

## Technology Stack

- **Framework**: FastAPI
- **LLM**: Anthropic Claude (via SDK)
- **Database**: SQLAlchemy (SQLite/PostgreSQL)
- **WebSocket**: FastAPI WebSocket
- **Validation**: Pydantic
- **Async**: asyncio
- **Tools**: Computer use APIs (bash, screen, keyboard, mouse)

## Scalability Considerations

### Current State
- Single-server deployment
- SQLite for development
- In-memory event bus

### Future Improvements
- **Horizontal Scaling**: Stateless design allows multiple API instances
- **Message Queue**: Replace in-memory events with Redis/RabbitMQ
- **Database**: PostgreSQL with connection pooling
- **Caching**: Redis for session data
- **Load Balancing**: Nginx/ALB for distributing requests
- **WebSocket**: Sticky sessions or Redis pub/sub for multi-instance

## Security Considerations

1. **API Authentication**: JWT or API keys for client authentication
2. **Tool Sandboxing**: Limit file system access, network calls
3. **Rate Limiting**: Prevent abuse of expensive LLM calls
4. **Input Validation**: Strict schema validation on all inputs
5. **Secrets Management**: Environment variables, never hardcoded
6. **SQL Injection**: SQLAlchemy ORM protects against this
7. **CORS**: Configured for allowed origins only

## Error Handling

- **API Errors**: HTTP status codes with error messages
- **Tool Errors**: Captured and returned to LLM for recovery
- **LLM Errors**: Retry logic with exponential backoff
- **WebSocket Errors**: Error events sent to client
- **Database Errors**: Transaction rollback, error logging

## Monitoring & Observability

1. **Logging**: Structured logs with request IDs
2. **Metrics**: Tool execution times, LLM token usage
3. **Tracing**: Request flow through components (future: OpenTelemetry)
4. **Health Checks**: `/health` endpoint for monitoring
5. **Error Tracking**: Sentry or similar (optional)

## Development Workflow

1. **Local Development**: SQLite, hot-reload with uvicorn
2. **Testing**: pytest with fixtures, mock LLM calls
3. **Migrations**: Alembic for database schema changes
4. **Linting**: ruff/black for code formatting
5. **Type Checking**: mypy for static analysis

## Deployment

- **Container**: Docker image with Python 3.11+
- **Environment**: Environment variables for config
- **Database**: PostgreSQL in production
- **Reverse Proxy**: Nginx for HTTPS termination
- **Process Manager**: Gunicorn with uvicorn workers

## Extension Points

1. **New Tools**: Implement `BaseTool`, add to `ToolCollection`
2. **Custom LLM**: Implement LLM client interface
3. **Event Handlers**: Subscribe to `EventPublisher`
4. **Authentication**: Add middleware in `main.py`
5. **Storage**: Swap repository implementation

---

**Last Updated**: 2026-03-20
