# Orcheo

[![CI](https://github.com/ShaojieJiang/orcheo/actions/workflows/ci.yml/badge.svg?event=push)](https://github.com/ShaojieJiang/orcheo/actions/workflows/ci.yml?query=branch%3Amain)
[![Coverage](https://coverage-badge.samuelcolvin.workers.dev/ShaojieJiang/orcheo.svg)](https://coverage-badge.samuelcolvin.workers.dev/redirect/ShaojieJiang/orcheo)
[![PyPI - Core](https://img.shields.io/pypi/v/orcheo.svg?label=core)](https://pypi.org/project/orcheo/)
[![PyPI - Backend](https://img.shields.io/pypi/v/orcheo-backend.svg?label=backend)](https://pypi.org/project/orcheo-backend/)
[![PyPI - SDK](https://img.shields.io/pypi/v/orcheo-sdk.svg?label=sdk)](https://pypi.org/project/orcheo-sdk/)

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
| `orcheo agent-tool list [--category <category>]` | List available agent tools with metadata. Filter by category. |
| `orcheo agent-tool show <tool>` | Display detailed tool schema and parameter information. |
| `orcheo workflow list [--include-archived]` | List workflows with owner, last run, and status. |
| `orcheo workflow show <workflow>` | Print workflow summary, Mermaid graph, and latest runs. |
| `orcheo workflow run <workflow> [--inputs <json>]` | Trigger a workflow execution and stream status to the console. |
| `orcheo workflow upload <file> [--name <name>]` | Upload a workflow from Python or JSON file. |
| `orcheo workflow download <workflow> [-o <file>]` | Download workflow definition as Python or JSON. |
| `orcheo workflow delete <workflow> [--force]` | Delete a workflow with confirmation safeguards. |
| `orcheo credential list [--workflow-id <id>]` | List credentials with scopes, expiry, and health status. |
| `orcheo credential create <name> --provider <provider>` | Create a new credential with guided prompts. |
| `orcheo credential delete <credential> [--force]` | Revoke a credential with confirmation safeguards. |
| `orcheo credential reference <credential>` | Show the `[[cred_name]]` placeholder syntax for use in workflows. |
| `orcheo code scaffold <workflow>` | Generate Python SDK code snippets to invoke the workflow. |

#### Offline Mode

Pass `--offline` to reuse cached metadata when disconnected:

```bash
orcheo node list --offline
orcheo workflow show <workflow-id> --offline
```

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
