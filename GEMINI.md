# Orcheo Context for Gemini

## Project Overview
Orcheo is a workflow orchestration platform built on LangGraph, featuring a node-based architecture. It allows users to create, manage, and execute complex workflows combining AI nodes, task nodes, and external integrations.

The project is a monorepo structure containing:
-   **Core Engine & Backend**: Python-based (FastAPI, LangGraph).
-   **SDK**: Python SDK for interacting with the Orcheo API.
-   **Canvas**: A visual workflow designer (React, Vite).

## Architecture & Tech Stack

### Backend (`src/orcheo`, `apps/backend`)
-   **Framework**: FastAPI + Uvicorn
-   **Orchestration**: LangGraph + LangChain
-   **Database**: SQLite (default/dev), PostgreSQL (production support)
-   **Dependency Management**: `uv`
-   **Testing**: `pytest`
-   **Linting/Formatting**: `ruff`, `mypy`

### Frontend / Canvas (`apps/canvas`)
-   **Framework**: React 19 + Vite
-   **UI Library**: Radix UI, Tailwind CSS
-   **Graphing**: @xyflow/react (React Flow)
-   **Testing**: Vitest
-   **Linting/Formatting**: ESLint, Prettier

## Development Workflow

### Prerequisite
-   **Python**: 3.12+
-   **Node.js**: Latest LTS recommended
-   **Package Manager**: `uv` (Python), `npm` (Node.js)

### Key Commands (Makefile)
The `Makefile` is the primary entry point for development tasks.

| Task | Command | Description |
| :--- | :--- | :--- |
| **Backend** | | |
| Start Server | `make dev-server` | Starts FastAPI backend with hot-reload on port 8000. |
| Test | `make test` | Runs Python tests with coverage (`pytest`). |
| Lint | `make lint` | Runs `ruff check`, `mypy`, and `ruff format --check`. |
| Format | `make format` | Auto-formats Python code using `ruff`. |
| Docs | `make doc` | Serves MkDocs documentation on port 8080. |
| **Frontend** | | |
| Test | `make canvas-test` | Runs Frontend tests (`vitest`). |
| Lint | `make canvas-lint` | Runs `eslint`. |
| Format | `make canvas-format` | Auto-formats Frontend code using `prettier`. |

### CLI Commands
The project also exposes CLI commands via `pyproject.toml` scripts (available when environment is active):
-   `orcheo-dev-server`: Equivalent to `make dev-server`.
-   `orcheo-seed-env`: Sets up development environment variables.

## Directory Structure

-   `apps/`
    -   `backend/`: Deployment wrapper for the FastAPI application.
    -   `canvas/`: Source code for the React visual editor.
-   `packages/`
    -   `sdk/`: Python SDK implementation.
-   `src/`
    -   `orcheo/`: Core package logic, nodes, graph engine, and API routes.
-   `tests/`: Python test suite (mirrors `src/` structure).
-   `docs/`: Project documentation (Markdown).
-   `examples/`: Example scripts and Jupyter notebooks.
-   `Makefile`: Automation for common dev tasks.
-   `pyproject.toml`: Python configuration and dependencies.
-   `uv.lock`: Locked Python dependencies.

## Coding Conventions

### Python
-   **Style**: Follows Google Docstring convention.
-   **Typing**: Strict type hints are enforced (`mypy`).
-   **Async**: Extensive use of `async/await` patterns.
-   **Imports**: Absolute imports only (no relative imports).

### TypeScript/React
-   **Style**: Functional components with Hooks.
-   **Styling**: Tailwind CSS for styling, avoiding raw CSS where possible.
-   **State**: Local state + React Context for global needs.

## Critical Instructions for AI Agent
1.  **Verify First**: Before changing code, always run the relevant lint/test command to establish a baseline.
2.  **Adhere to Style**: Use `make format` and `make canvas-format` to ensure changes match the project style.
3.  **Test Updates**: When modifying logic, ensure existing tests pass and add new tests for new functionality; run the smallest relevant pytest target for your change (e.g., `uv run pytest tests/nodes/test_foo.py`) and document which test command you ran, ensuring it passes with all tests green before completion; for Canvas work run `make canvas-format`, `make canvas-lint`, and the smallest relevant Canvas test target (prefer targeted npm/vitest commands), document which Canvas test command you ran, ensure it passes with all tests green, and run all three Canvas commands after ANY TypeScript/JavaScript code modification.
4.  **Dependency Awareness**: Do not assume global packages. Use `uv run` or `npm run` context.
