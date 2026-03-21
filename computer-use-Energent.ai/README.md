# AI Agent API

A FastAPI-based AI agent system powered by Claude with computer-use capabilities, featuring real-time WebSocket streaming.

## Features

- 🤖 **Claude Integration**: Powered by Anthropic's Claude for intelligent agent interactions
- 🔌 **Computer Use Tools**: Bash execution, screen viewing, keyboard/mouse control, file editing
- 📡 **WebSocket Streaming**: Real-time event streaming for agent thoughts, tool calls, and responses
- 💾 **Session Management**: Persistent conversation sessions with SQLite/PostgreSQL
- 🏗️ **Clean Architecture**: Separation of concerns with API, Services, Core, and Data layers
- 🔄 **Async/Await**: Non-blocking I/O for better performance
- 🛠️ **Extensible Tools**: Easy to add new tools with the BaseTool interface

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed system architecture documentation.

## Project Structure

```
app/
├── main.py                    # FastAPI application entry point
├── api/                       # API layer (routes, WebSocket)
├── services/                  # Business logic (agent, session, tools)
├── core/                      # Core components (LLM, tools, events)
├── schemas/                   # Pydantic models
├── db/                        # Database models and repository
├── config/                    # Configuration management
└── utils/                     # Utilities (logging, etc.)
```

## Setup

### Prerequisites

- Python 3.11+
- pip or poetry
- Anthropic API key

### Installation

1. Clone the repository:
```bash
cd computer-use-Energent.ai
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

5. Initialize database:
```bash
# Database will be automatically initialized on first run
```

## Running the Application

### Development Mode

```bash
python app/main.py
```

Or with uvicorn:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## API Usage

### 1. Create a Session

```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"name": "My Agent Session"}'
```

Response:
```json
{
  "id": "session-uuid",
  "name": "My Agent Session",
  "status": "active",
  "created_at": "2026-03-20T00:00:00"
}
```

### 2. Connect to WebSocket for Streaming

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/session-uuid');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data.event_type, data.data);
};
```

### 3. Send a Message

```bash
curl -X POST http://localhost:8000/api/agent/message \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-uuid",
    "message": "What files are in the current directory?"
  }'
```

### 4. Watch Real-time Processing

Events will be streamed via WebSocket:
- `agent.thinking` - Agent is processing
- `tool.called` - Tool is being executed
- `tool.result` - Tool execution result
- `agent.response` - Final response
- `agent.error` - Error occurred

## Available Tools

### Bash Tool
Execute shell commands:
```python
{
  "action": "bash",
  "command": "ls -la",
  "timeout": 30
}
```

### Computer Tool
Screen viewing and input control:
```python
{
  "action": "screenshot"  # or mouse_move, left_click, type, key
}
```

### Edit Tool
File editing:
```python
{
  "action": "read",  # or write, append
  "path": "/path/to/file.txt",
  "content": "file content"
}
```

## Development

### Adding a New Tool

1. Create a new tool in `app/services/tools/`:

```python
from app.core.tools.base import BaseTool

class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "Description for the LLM"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "param": {"type": "string"}
            }
        }

    async def execute(self, **kwargs):
        # Implementation
        return {"result": "success"}
```

2. Register it in `app/services/tools/executor.py`:

```python
self.tool_collection.register(MyTool())
```

### Running Tests

```bash
pytest tests/
```

## Configuration

Edit `.env` file:

- `ANTHROPIC_API_KEY`: Your Anthropic API key
- `CLAUDE_MODEL`: Claude model to use (default: claude-3-5-sonnet-20241022)
- `DATABASE_URL`: Database connection string
- `ALLOWED_ORIGINS`: CORS allowed origins
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t ai-agent-api .
docker run -p 8000:8000 --env-file .env ai-agent-api
```

## License

MIT License

## Contributing

Contributions are welcome! Please read the contributing guidelines first.

## Support

For issues and questions, please open an issue on GitHub.
