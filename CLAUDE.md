# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Testing and Quality
- `make test` - Run tests with coverage reports using pytest
- `make lint` - Run full lint check (ruff, mypy, format check)
- `make format` - Auto-format code with ruff
- `pytest --cov --cov-report term-missing tests/` - Run tests with detailed coverage

### Development Server
- `make dev-server` - Start development server with hot reload on port 8000
- `make doc` - Serve documentation locally on port 8080

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
- **Database**: SQLite checkpoints, PostgreSQL support
- **AI Integration**: OpenAI, various LangChain providers
- **External Services**: Telegram Bot, Slack, MongoDB, RSS feeds

## File Structure
- `src/orcheo/` - Main package
  - `nodes/` - Node implementations and registry
  - `graph/` - State management and graph builder
  - `main.py` - FastAPI application entry
- `tests/` - Test files mirroring src structure
- `examples/` - Usage examples and notebooks
- `docs/` - Documentation and architecture diagrams

## Code Standards
- Google docstring convention
- Type hints required (mypy strict mode)
- Ruff for linting and formatting (line length 88)
- 100% test coverage expected
- No relative imports allowed

**CRITICAL**: After making any code changes:
1. Run `make lint` and ensure it passes with ZERO errors or warnings
2. Run `make test` and ensure all tests pass

## Important Notes
- Uses async/await patterns throughout
- State flows through nodes via decode_variables() method
- WebSocket support for real-time workflow monitoring
- MCP (Model Context Protocol) adapters for tool integration
