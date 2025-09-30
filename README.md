# Orcheo

[![CI](https://github.com/ShaojieJiang/orcheo/actions/workflows/ci.yml/badge.svg?event=push)](https://github.com/ShaojieJiang/orcheo/actions/workflows/ci.yml?query=branch%3Amain)
[![Coverage](https://coverage-badge.samuelcolvin.workers.dev/ShaojieJiang/orcheo.svg)](https://coverage-badge.samuelcolvin.workers.dev/redirect/ShaojieJiang/orcheo)
[![PyPI](https://img.shields.io/pypi/v/orcheo.svg)](https://pypi.python.org/pypi/orcheo)

Orcheo is a tool for creating and running workflows.

## Quick start

The project ships with everything needed to spin up the FastAPI runtime on
SQLite for local development.

1. **Install dependencies**

   ```bash
   uv sync --all-groups
   ```

2. **Configure environment variables**

   ```bash
   cp .env.example .env
   ```

3. **Run the API server**

   ```bash
   make dev-backend
   ```

4. **Verify the setup**

   ```bash
   uv run pytest
   ```

See [`docs/deployment.md`](docs/deployment.md) for Docker Compose and managed
PostgreSQL deployment recipes.
