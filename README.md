# Orcheo

[![CI](https://github.com/ShaojieJiang/orcheo/actions/workflows/ci.yml/badge.svg?event=push)](https://github.com/ShaojieJiang/orcheo/actions/workflows/ci.yml?query=branch%3Amain)
[![Coverage](https://coverage-badge.samuelcolvin.workers.dev/ShaojieJiang/orcheo.svg)](https://coverage-badge.samuelcolvin.workers.dev/redirect/ShaojieJiang/orcheo)
[![PyPI - Core](https://img.shields.io/pypi/v/orcheo.svg?label=core)](https://pypi.org/project/orcheo/)
[![PyPI - Backend](https://img.shields.io/pypi/v/orcheo-backend.svg?label=backend)](https://pypi.org/project/orcheo-backend/)
[![PyPI - SDK](https://img.shields.io/pypi/v/orcheo-sdk.svg?label=sdk)](https://pypi.org/project/orcheo-sdk/)

Orcheo is a tool for creating and running workflows.

## Repository layout

- `src/orcheo/` – core orchestration engine and FastAPI implementation
- `apps/backend/` – deployment wrapper exposing the FastAPI ASGI app
- `packages/sdk/` – lightweight Python SDK for composing workflow requests
- `apps/canvas/` – React + Vite scaffold for the visual workflow designer

## Quick start

The project ships with everything needed to spin up the FastAPI runtime on
SQLite for local development.

1. **Install dependencies**

   ```bash
   uv sync --all-groups
   ```

2. **Seed environment variables**

   ```bash
   uv run orcheo-seed-env
   ```

   Pass `-- --force` to overwrite an existing `.env` file.

3. **Run the API server**

   ```bash
   uv run orcheo-dev-server
   ```

4. **Verify the setup**

   ```bash
   uv run orcheo-test
   ```

Opening the repository inside VS Code automatically offers to start the included
dev container with uv and Node.js preinstalled. The new quickstart flows in
`examples/quickstart/` demonstrate the visual designer and SDK user journeys,
and `examples/ingest_langgraph.py` shows how to push a Python LangGraph script
directly to the backend importer, execute it, and stream live updates.

See [`docs/deployment.md`](docs/deployment.md) for Docker Compose and managed
PostgreSQL deployment recipes.

## Releasing packages

Follow [`docs/releasing.md`](docs/releasing.md) for the step-by-step guide to
version, tag, and publish the `orcheo`, `orcheo-backend`, and `orcheo-sdk`
packages independently via the automated CI workflows.
