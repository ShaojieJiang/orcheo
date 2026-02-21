# Manual Setup Guide

This guide covers manual installation and configuration of Orcheo for users who prefer direct control over their setup.

## Quick Start

For one-line installation, see the [Quick Start section on the landing page](index.md#quick-start).
If you already have the SDK installed, run `orcheo install` to set up or upgrade the local stack.

## Prerequisites

- **Docker**: Required for running Redis and other services via Docker Compose
- **Python 3.12+**: Required for the backend
- **uv**: Recommended for dependency management

## Docker Compose (Full Stack)

For a complete containerized setup with PostgreSQL, Redis, Celery workers, and Canvas, use the bundled Docker Compose configuration.

### Quick Start

1. **Set up the local stack** using the CLI (this downloads compose files and creates `.env` automatically):
   ```bash
   orcheo install --start-local-stack
   ```

   The CLI syncs stack assets to `~/.orcheo/stack` (override with `ORCHEO_STACK_DIR`).
   On fresh installs, secure values are auto-generated for `ORCHEO_POSTGRES_PASSWORD`,
   `ORCHEO_VAULT_ENCRYPTION_KEY`, and `ORCHEO_CHATKIT_TOKEN_SIGNING_KEY`.

2. **(Optional) Configure secrets** in `~/.orcheo/stack/.env`:

    You only need to edit `.env` if you want custom values or need to configure
    `VITE_ORCHEO_CHATKIT_DOMAIN_KEY` for ChatKit. The setup flow prompts for this
    key and allows skipping; if skipped, ChatKit UI features remain disabled
    until you set it (or rerun `orcheo install --chatkit-domain-key <key>`). Be aware that changing
    `ORCHEO_VAULT_ENCRYPTION_KEY` after storing credentials will make them unreadable.

3. **Verify services are running**:
    - Backend API: http://localhost:8000
    - Canvas UI: http://localhost:5173 (may take 2-3 minutes on first startup while npm installs dependencies)

### Managing Services

```bash
STACK_DIR="${ORCHEO_STACK_DIR:-$HOME/.orcheo/stack}"

# View logs
docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" logs -f backend
docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" logs -f worker
docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" logs -f celery-beat
docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" logs -f canvas

# Stop all services
docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" down

# Rebuild after changes (--no-cache ensures fresh builds with latest PyPI packages)
docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" build --no-cache
docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" up -d
```

### Local Testing Without OAuth

For local development without OAuth, set `ORCHEO_AUTH_MODE=optional` in your `.env` file. This allows unauthenticated access to the API.

## Installation (Manual)

The project ships with everything needed to spin up the FastAPI runtime on SQLite for local development.

### From Source (Development)

```bash
uv sync --all-groups
```

### From PyPI

```bash
uv add orcheo orcheo-backend orcheo-sdk
```

### Activating the Virtual Environment

After installation, activate the virtual environment (optional but recommended):

```bash
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate     # On Windows
```

Once activated, you can run commands without the `uv run` prefix.

## Running the API Server

Start the development server:

```bash
orcheo-dev-server
```

### Verifying the Setup

```bash
orcheo-test
```

### Authentication

Orcheo supports flexible authentication modes configured via `ORCHEO_AUTH_MODE`:

- **disabled**: No authentication (development only)
- **optional**: Validates tokens when provided but not required
- **required**: All requests must include valid credentials (recommended for production)

For detailed authentication setup including bootstrap tokens, service tokens, and OAuth configuration, see the [Authentication Guide](authentication_guide.md).

## Next Steps

- **[CLI Reference](cli_reference.md)** — Command reference for the `orcheo` CLI
- **[Canvas](canvas.md)** — Visual workflow designer setup
- **[MCP Integration](mcp_integration.md)** — Connect AI assistants to Orcheo
- **[Authentication Guide](authentication_guide.md)** — Detailed authentication configuration
- **[Developer Guide](developer_guide.md)** — Contributing to Orcheo

## Upgrade Recovery Notes

If setup/upgrade is interrupted:

1. Re-run `orcheo install` (idempotent reconciliation is the default path).
2. If local stack services are inconsistent, run:
   `STACK_DIR="${ORCHEO_STACK_DIR:-$HOME/.orcheo/stack}"` then
   `docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" down`
   and
   `docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" up -d`.
3. If local files were customized and you want a clean baseline, delete
   `~/.orcheo/stack` and re-run `orcheo install`.
