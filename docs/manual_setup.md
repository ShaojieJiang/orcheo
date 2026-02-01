# Manual Setup Guide

This guide covers manual installation and configuration of Orcheo for users who prefer direct control over their setup.

## Prerequisites

- **Docker**: Required for running Redis and other services via Docker Compose
- **Python 3.12+**: Required for the backend
- **uv**: Recommended for dependency management

## Docker Compose (Full Stack)

For a complete containerized setup with PostgreSQL, Redis, Celery workers, and Canvas, use the bundled Docker Compose configuration.

### Quick Start

1. **Download the compose files** from [agent-skills/orcheo/assets](https://github.com/ShaojieJiang/agent-skills/tree/main/orcheo/assets):
   ```bash
   curl -fsSLO https://raw.githubusercontent.com/ShaojieJiang/agent-skills/main/orcheo/assets/docker-compose.yml
   curl -fsSLO https://raw.githubusercontent.com/ShaojieJiang/agent-skills/main/orcheo/assets/Dockerfile.orcheo
   curl -fsSL https://raw.githubusercontent.com/ShaojieJiang/agent-skills/main/orcheo/assets/.env.example -o .env
   ```

2. **(Optional) Configure required secrets** in `.env`:

    !!! tip "Quick start"
        For local testing, you can skip this step entirely. The placeholder values in `.env.example` will work out of the box. Just be aware that if you later change `ORCHEO_VAULT_ENCRYPTION_KEY`, any previously stored credentials will become unreadable.

    ```bash
    # Generate a secure encryption key (64 hex characters)
    python -c "import secrets; print(secrets.token_hex(32))"

    # Edit .env with your values:
    ORCHEO_POSTGRES_PASSWORD=your-secure-password
    ORCHEO_VAULT_ENCRYPTION_KEY=your-64-hex-char-key
    VITE_ORCHEO_CHATKIT_DOMAIN_KEY=your-chatkit-key
    ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN=your-bootstrap-token
    ```

3. **Start all services**:
   ```bash
   docker compose up -d
   docker compose ps
   ```

4. **Verify services are running**:
    - Backend API: http://localhost:8000
    - Canvas UI: http://localhost:5173

5. **Install the CLI**:
   ```bash
   uv tool add orcheo-sdk
   ```


### Managing Services

```bash
# View logs
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f celery-beat
docker compose logs -f canvas

# Stop all services
docker compose down

# Rebuild after changes
docker compose build
docker compose up -d
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
