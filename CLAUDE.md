# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Testing and Quality
- `make test` - Run Python tests with coverage reports using pytest
- `make lint` - Run full lint check (ruff, mypy, format check)
- `make format` - Auto-format code with ruff
- `make canvas-lint` - Run lint check for Canvas (TypeScript/JavaScript)
- `make canvas-format` - Auto-format Canvas code with prettier
- `make canvas-test` - Run Canvas tests
- `pytest --cov --cov-report term-missing tests/` - Run tests with detailed coverage

### Development Server
- `make dev-server` - Start development server with hot reload on port 8000
- `make doc` - Serve documentation locally on port 8080

### Execution Worker (Celery + Redis)
- `make redis` - Start Redis via Docker Compose
- `make worker` - Start Celery worker for background execution
- `make celery-beat` - Start Celery Beat scheduler for cron triggers

### Docker Compose (Full Stack)
- `make docker-up` - Start all services (backend, canvas, redis, worker, celery-beat)
- `make docker-down` - Stop all Docker Compose services
- `make docker-build` - Build Docker images
- `make docker-logs` - Follow logs from all services

### Package Management
- Uses `uv` for dependency management (see uv.lock)
- Python 3.12+ required
- Dependencies defined in pyproject.toml

## Architecture Overview

Orcheo is a workflow orchestration platform built on LangGraph with a node-based architecture:

### Core Components
- **Nodes**: Individual workflow units inheriting from BaseNode, AINode, or TaskNode
- **Graph Builder**: Constructs workflows from JSON configurations using StateGraph
- **State Management**: Centralized state passing between nodes with variable interpolation
- **Node Registry**: Dynamic registration system for node types

### Key Design Patterns
- Backend-first with optional frontend
- Supports both low-code (config) and code-first (Python SDK) approaches
- Simple cross-node protocol for extensibility
- Variable interpolation using `{{path.to.value}}` syntax in node attributes

### Node Types
- **BaseNode**: Abstract base with variable decoding and tool interface
- **AINode**: For AI-powered nodes, wraps results in messages
- **TaskNode**: For utility/integration nodes, outputs structured data
- Built-in nodes: AI, Code, MongoDB, RSS, Slack, Telegram

### Technology Stack
- **Backend**: FastAPI + uvicorn
- **Workflow Engine**: LangGraph + LangChain
- **Task Queue**: Celery + Redis (for background execution)
- **Database**: SQLite checkpoints, PostgreSQL support
- **AI Integration**: OpenAI, various LangChain providers
- **External Services**: Telegram Bot, Slack, MongoDB, RSS feeds

## File Structure
- `src/orcheo/` - Main package
  - `nodes/` - Node implementations and registry
  - `graph/` - State management and graph builder
  - `main.py` - FastAPI application entry
- `apps/backend/` - Backend deployment package
  - `src/orcheo_backend/worker/` - Celery worker and tasks
- `tests/` - Test files mirroring src structure
- `examples/` - Usage examples and notebooks
- `docs/` - Documentation and architecture diagrams
- `deploy/systemd/` - systemd unit files for production deployment

## Code Standards
- Google docstring convention
- Type hints required (mypy strict mode)
- Ruff for linting and formatting (line length 88)
- 100% test coverage expected
- No relative imports allowed

**CRITICAL**: After making any code changes:
1. For Python code changes:
   - `make format` to auto-format the code
   - `make lint` MUST pass with ZERO errors or warnings before completing any task
   - Run the smallest relevant pytest target for your change (e.g., `uv run pytest tests/nodes/test_foo.py`)
   - Document which test command you ran; ensure it passes with all tests green before completion
2. For TypeScript/JavaScript code changes (Canvas):
   - Run `make canvas-format` to auto-format the code
   - Run `make canvas-lint` and ensure it passes with ZERO errors or warnings
   - Run the smallest relevant Canvas test target for your change (prefer targeted npm/vitest commands)
   - Document which Canvas test command you ran; ensure it passes with all tests green before completion

## Important Notes
- Uses async/await patterns throughout
- State flows through nodes via decode_variables() method
- WebSocket support for real-time workflow monitoring
- MCP (Model Context Protocol) adapters for tool integration
