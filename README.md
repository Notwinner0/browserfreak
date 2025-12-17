# BrowserFreak

🤖 AI-powered browser automation with Anthropic Claude integration.

## Quick Start

### 1. Install
```bash
pip install -r requirements.txt
playwright install
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 3. Run
```bash
# CLI
browserfreak run "Navigate to example.com and click submit"

# FastAPI Server
browserfreak server --host 0.0.0.0 --port 8000

# Streamlit UI (Chat Interface)
streamlit run src/browserfreak/agent_ui.py

The Streamlit UI provides a modern chat-like interface for interacting with BrowserFreak, featuring:
- Conversational chat with message history
- Quick action buttons for common tasks
- Real-time execution status
- Security approval system
- Configurable agent settings
- Chat export functionality

# Python
import asyncio
from browserfreak import run_agent_workflow

result = asyncio.run(run_agent_workflow("your task here"))
```

## Docker

```bash
docker-compose up --build
```

## Features

- **AI Decision Making**: Uses Claude 3.5 Sonnet for intelligent automation
- **Browser Control**: Full Playwright integration for real browser automation
- **Security**: Automatic detection of destructive actions with human approval
- **Fallback Mode**: Works without API key using rule-based decisions
- **Production Ready**: Docker, health checks, logging, and monitoring

## Configuration

Key settings in `.env`:
```env
ANTHROPIC_API_KEY=your-key-here
USE_REAL_BROWSER=false
MAX_ITERATIONS=5
LOG_LEVEL=INFO
```

## CLI Commands

```bash
browserfreak run "task description"          # Execute automation task
browserfreak server [--host HOST] [--port PORT] [--reload]  # Start FastAPI server
browserfreak health                         # Check system health
browserfreak config                         # Show configuration
```

## REST API

The FastAPI server provides REST endpoints for programmatic access:

### Endpoints

- `GET /health` - Health check
- `POST /tasks` - Create and execute a task
- `GET /tasks/{task_id}` - Get task status
- `GET /tasks` - List tasks with filtering
- `DELETE /tasks/{task_id}` - Cancel a task

### API Documentation

When the server is running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Example API Usage

```bash
# Create a task
curl -X POST "http://localhost:8000/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Navigate to example.com and describe what you see",
    "use_real_browser": true,
    "max_iterations": 5
  }'

# Check task status
curl "http://localhost:8000/tasks/{task_id}"
```

## Python API

```python
from browserfreak import run_agent_workflow, create_browser_context

# Run task
result = await run_agent_workflow("click the login button")

# Manual browser control
context = await create_browser_context()
# ... use browser functions
```

## License

MIT
