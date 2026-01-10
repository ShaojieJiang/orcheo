# Orcheo

[![CI](https://github.com/ShaojieJiang/orcheo/actions/workflows/ci.yml/badge.svg?event=push)](https://github.com/ShaojieJiang/orcheo/actions/workflows/ci.yml?query=branch%3Amain)
[![Coverage](https://coverage-badge.samuelcolvin.workers.dev/ShaojieJiang/orcheo.svg)](https://coverage-badge.samuelcolvin.workers.dev/redirect/ShaojieJiang/orcheo)
[![PyPI - Core](https://img.shields.io/pypi/v/orcheo.svg?logo=python&label=core)](https://pypi.org/project/orcheo/)
[![PyPI - Backend](https://img.shields.io/pypi/v/orcheo-backend.svg?logo=python&label=backend)](https://pypi.org/project/orcheo-backend/)
[![PyPI - SDK](https://img.shields.io/pypi/v/orcheo-sdk.svg?logo=python&label=sdk)](https://pypi.org/project/orcheo-sdk/)
[![PyPI - Agentensor](https://img.shields.io/pypi/v/agentensor.svg?logo=python&label=agentensor)](https://pypi.org/project/agentensor/)
[![npm - Canvas](https://img.shields.io/npm/v/orcheo-canvas.svg?logo=npm&label=canvas)](https://www.npmjs.com/package/orcheo-canvas)

Orcheo is a tool for creating and running workflows.

## For users

### Quick start

The project ships with everything needed to spin up the FastAPI runtime on
SQLite for local development.

1. **Install dependencies**

   For development (from source):
   ```bash
   uv sync --all-groups
   ```

   Or install from PyPI:
   ```bash
   uv add orcheo orcheo-backend orcheo-sdk
   ```

2. **Activate the virtual environment** (optional but recommended)

   ```bash
   source .venv/bin/activate  # On macOS/Linux
   # or
   .venv\Scripts\activate     # On Windows
   ```

   Once activated, you can run commands without the `uv run` prefix.

3. **Run the API server**

   ```bash
   orcheo-dev-server
   ```

   If you enable authentication, configure a bootstrap token first to create your initial service tokens:

   ```bash
   # Generate a secure random token
   python -c "import secrets; print(secrets.token_urlsafe(32))"

   # Configure bootstrap token and authentication
   export ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN="your-secure-random-token"
   export ORCHEO_AUTH_BOOTSTRAP_TOKEN_EXPIRES_AT="2025-05-01T12:00:00Z"  # optional expiry
   export ORCHEO_AUTH_MODE=required

   # Start the server
   orcheo-dev-server
   ```

   **Bootstrap tokens** are special environment-based service tokens for initial setup only:
   - Not stored in the database - read directly from environment
   - Full admin access by default (configurable with `ORCHEO_AUTH_BOOTSTRAP_TOKEN_SCOPES`)
   - Optional expiration via `ORCHEO_AUTH_BOOTSTRAP_TOKEN_EXPIRES_AT`
   - Should be removed after creating persistent tokens

   After the server starts, use the bootstrap token to create persistent service tokens:

   ```bash
   export ORCHEO_SERVICE_TOKEN="your-secure-random-token"  # Use bootstrap token
   orcheo token create --id production-token \
     --scope workflows:read \
     --scope workflows:write \
     --scope workflows:execute
   ```

   Then switch to the new persistent token and remove the bootstrap token:

   ```bash
   export ORCHEO_SERVICE_TOKEN="<new-token-from-previous-command>"
   unset ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN
   ```

4. **Verify the setup**

   ```bash
   orcheo-test
   ```

### CLI

Orcheo ships with a LangGraph-friendly CLI for node discovery, workflow
inspection, credential management, and reference code generation.

### Getting Started

After activating the virtual environment, get started with:

```bash
orcheo --help
```

### Shell Auto-Completion

Enable fast shell auto-completion for commands and options:

```bash
orcheo --install-completion
```

This installs completion for your current shell (bash, zsh, fish, or PowerShell).
After installation, restart your shell or source your shell configuration file.

#### Available Commands

| Command | Description |
|---------|-------------|
| `orcheo node list [--tag <tag>]` | List registered nodes with metadata (name, category, description). Filter by tag. |
| `orcheo node show <node>` | Display detailed node schema, inputs/outputs, and credential requirements. |
| `orcheo edge list [--category <category>]` | List registered edges with metadata (name, category, description). Filter by category. |
| `orcheo edge show <edge>` | Display detailed edge schema and conditional routing configuration. |
| `orcheo agent-tool list [--category <category>]` | List available agent tools with metadata. Filter by category. |
| `orcheo agent-tool show <tool>` | Display detailed tool schema and parameter information. |
| `orcheo workflow list [--include-archived]` | List workflows with owner, last run, and status. |
| `orcheo workflow show <workflow> [--version <num>]` | Print workflow summary, publish status/details, Mermaid graph, and runs. Use `--version` to show a specific version instead of the latest. |
| `orcheo workflow run <workflow> [--inputs <json> \| --inputs-file <path>] [--config <json> \| --config-file <path>]` | Trigger a workflow execution and stream status to the console. |
| `orcheo workflow upload <file> [--name <name>] [--config <json> \| --config-file <path>]` | Upload a workflow from Python or JSON file. |
| `orcheo workflow download <workflow> [-o <file>] [--version <num>]` | Download workflow definition as Python or JSON. Use `--version` to download a specific version. |
| `orcheo workflow delete <workflow> [--force]` | Delete a workflow with confirmation safeguards. |
| `orcheo workflow schedule <workflow>` | Activate cron scheduling based on the workflow's cron trigger (no-op if none). |
| `orcheo workflow unschedule <workflow>` | Remove cron scheduling for the workflow. |
| `orcheo workflow publish <workflow> [--require-login] [--chatkit-public-base-url <url>]` | Publish a workflow for public ChatKit access, optionally requiring OAuth login and overriding the share-link origin for that run. |
| `orcheo workflow unpublish <workflow>` | Revoke public access and invalidate existing share links. |
| `orcheo credential list [--workflow-id <id>]` | List credentials with scopes, expiry, and health status. |
| `orcheo credential create <name> --provider <provider>` | Create a new credential with guided prompts. |
| `orcheo credential delete <credential> [--force]` | Revoke a credential with confirmation safeguards. |
| `orcheo token create [--id <id>] [--scope <scope>]` | Create a service token for CLI/API authentication. |
| `orcheo token list` | List all service tokens with their scopes and status. |
| `orcheo token show <token-id>` | Show detailed information for a specific service token. |
| `orcheo token rotate <token-id> [--overlap <seconds>]` | Rotate a service token with grace period overlap. |
| `orcheo token revoke <token-id> [--reason <reason>]` | Immediately invalidate a service token. |
| `orcheo code template [-o <file>] [--name <name>]` | Generate a minimal Python LangGraph workflow template file. |
| `orcheo code scaffold <workflow>` | Generate Python SDK code snippets to invoke an existing workflow. |

Published workflows remain accessible until you run `orcheo workflow unpublish <workflow>` or toggle the `--require-login` flag to gate public chats behind OAuth.

Pass workflow inputs inline with `--inputs` or from disk via `--inputs-file`. Use `--config` or `--config-file` to provide LangChain runnable configuration for the execution (each pair is mutually exclusive).

Upload-time defaults can be stored on a workflow version with `orcheo workflow upload ... --config` or `--config-file`. Stored config is merged with per-run overrides (run config wins). Avoid putting secrets in runnable config; use environment variables or credential vaults instead.

#### Offline Mode

Pass `--offline` to reuse cached metadata when disconnected:

```bash
orcheo node list --offline
orcheo workflow show <workflow-id> --offline
```

### Authentication

Orcheo supports flexible authentication to protect your workflows and API endpoints.

#### Authentication Modes

Configure via the `ORCHEO_AUTH_MODE` environment variable:

- **disabled**: No authentication (development only)
- **optional**: Validates tokens when provided but not required
- **required**: All requests must include valid credentials (recommended for production)

```bash
export ORCHEO_AUTH_MODE=required
```

#### Service Tokens

Service tokens are ideal for CLI usage, CI/CD pipelines, and automated integrations.

**Create a token:**
```bash
# Basic token
orcheo token create

# Token with scopes and workspace access
orcheo token create --id my-ci-token \
  --scope workflows:read \
  --scope workflows:execute \
  --workspace ws-production
```

**Use with CLI:**
```bash
export ORCHEO_SERVICE_TOKEN="your-token-secret-here"
orcheo workflow list
```

**Use with Python SDK:**
```python
from orcheo_sdk import OrcheoClient

client = OrcheoClient(
    api_url="https://orcheo.example.com",
    token=os.environ["ORCHEO_SERVICE_TOKEN"]
)
```

**Rotate tokens:**
```bash
orcheo token rotate my-ci-token --overlap 300
```

#### JWT Authentication

For production deployments with Identity Providers (Auth0, Okta, Keycloak):

```bash
# Symmetric key (HS256)
export ORCHEO_AUTH_JWT_SECRET="your-secure-secret-key"

# Asymmetric key (RS256) with JWKS
export ORCHEO_AUTH_JWKS_URL="https://your-idp.com/.well-known/jwks.json"
export ORCHEO_AUTH_AUDIENCE="orcheo-production"
export ORCHEO_AUTH_ISSUER="https://your-idp.com/"
```

For detailed configuration, security best practices, and troubleshooting, see [docs/authentication_guide.md](docs/authentication_guide.md).

### MCP (Model Context Protocol)

Orcheo SDK includes an MCP server that allows AI assistants like Claude to interact with your workflows.

#### Claude Desktop
To configure it in Claude Desktop, add the following to your `claude_desktop_config.json`:

```json
"Orcheo": {
  "command": "/path/to/uvx",
  "args": ["--from", "orcheo-sdk@latest", "orcheo-mcp"],
  "env": {
    "ORCHEO_API_URL": "http://localhost:8000"
  }
}
```

**Note:** This configuration requires the Orcheo development backend to be running locally (see [Run the API server](#quick-start)).

#### Claude CLI

To configure the MCP server in Claude CLI:

```bash
claude mcp add-json Orcheo --scope user '{
  "command": "/path/to/uvx",
  "args": [
    "--from",
    "orcheo-sdk@latest",
    "orcheo-mcp"
  ],
  "env": {
    "ORCHEO_API_URL": "http://localhost:8000"
  }
}'
```

**Note:** Replace `/path/to/uvx` with your actual `uvx` binary path (find it with `which uvx`).

#### Codex CLI

To configure the MCP server in Codex CLI:

```bash
codex add server Orcheo \
  /path/to/uvx \
  --from orcheo-sdk@latest orcheo-mcp \
  --env ORCHEO_API_URL=http://localhost:8000
```

**Note:** Replace `/path/to/uvx` with your actual `uvx` binary path (find it with `which uvx`).

### Canvas (Visual Workflow Designer)

Orcheo Canvas is the visual workflow designer for creating and managing workflows through a drag-and-drop interface.

#### Installation

```bash
# Install globally
npm install -g orcheo-canvas

# Or install locally in your project
npm install orcheo-canvas
```

#### Usage

After installation, start the Canvas interface:

```bash
# Start preview server (production mode)
orcheo-canvas

# Start development server
orcheo-canvas dev

# Build for production
orcheo-canvas build

# Preview production build
orcheo-canvas preview
```

The Canvas application will be available at `http://localhost:5173` (dev mode) or the configured preview port (production mode).

For more details, see [apps/canvas/README.md](apps/canvas/README.md).

## For developers

### Repository layout

- `src/orcheo/` – core orchestration engine and FastAPI implementation
- `apps/backend/` – deployment wrapper exposing the FastAPI ASGI app
- `packages/sdk/` – lightweight Python SDK for composing workflow requests
- `apps/canvas/` – React + Vite scaffold for the visual workflow designer

Opening the repository inside VS Code automatically offers to start the included
dev container with uv and Node.js preinstalled. The new quickstart flows in
`examples/quickstart/` demonstrate the visual designer and SDK user journeys,
and `examples/ingest_langgraph.py` shows how to push a Python LangGraph script
directly to the backend importer, execute it, and stream live updates.

See [`docs/deployment.md`](docs/deployment.md) for Docker Compose and managed
PostgreSQL deployment recipes.

### Seed environment variables

To set up your development environment:

```bash
orcheo-seed-env
```

Pass `--force` to overwrite an existing `.env` file.

### Configuration

The CLI reads configuration from:
- Environment variables: `ORCHEO_API_URL`, `ORCHEO_SERVICE_TOKEN`
- Config file: `~/.config/orcheo/cli.toml` (profiles for multiple environments)
- Command flags: `--api-url`, `--service-token`, `--profile`

See [`docs/cli_tool_design.md`](docs/cli_tool_design.md) for detailed design,
roadmap, and future MCP server integration plans.

### Custom nodes and tools

Learn how to extend Orcheo with your own nodes, tool integrations, and workflow helpers in [`docs/custom_nodes_and_tools.md`](docs/custom_nodes_and_tools.md).

### Workflow repository configuration

The FastAPI backend now supports pluggable workflow repositories so local
development can persist state without depending on Postgres. By default the app
uses a SQLite database located at `~/.orcheo/workflows.sqlite`. Adjust the
following environment variables to switch behaviour:

- `ORCHEO_REPOSITORY_BACKEND`: accepts `sqlite` (default) or `inmemory` for
  ephemeral testing.
- `ORCHEO_REPOSITORY_SQLITE_PATH`: override the SQLite file path when using the
  SQLite backend.

Refer to `.env.example` for sample values and to `docs/deployment.md` for
deployment-specific guidance.
