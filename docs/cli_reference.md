# CLI Reference

Orcheo ships with a LangGraph-friendly CLI for node discovery, workflow inspection, credential management, and reference code generation.

## Getting Started

After installing the SDK, the CLI is available immediately:

```bash
orcheo --help
```

Check which version you have installed:

```bash
orcheo --version
```

## Global Options

| Flag | Environment Variable | Description |
|------|---------------------|-------------|
| `--version` | — | Show the installed CLI version and exit. |
| `--human` | `ORCHEO_HUMAN=1` | Use human-friendly Rich output (colored tables, panels). Without this flag, the CLI defaults to **machine-readable output** (JSON, Markdown tables) suitable for scripting and piping. |
| `--profile <name>` | `ORCHEO_PROFILE` | Select a named profile from `cli.toml`. |
| `--api-url <url>` | `ORCHEO_API_URL` | Override the backend API URL. |
| `--service-token <token>` | `ORCHEO_SERVICE_TOKEN` | Override the service token. |
| `--offline` | — | Fall back to cached data when network calls fail. |
| `--cache-ttl <hours>` | — | Cache TTL in hours for offline data (default: 24). |
| `--no-update-check` | `ORCHEO_DISABLE_UPDATE_CHECK=1` | Skip startup update reminders for the current invocation. |

## Output Modes

By default the CLI produces **machine-readable output**: lists render as Markdown tables, detail views render as JSON, and errors are returned as JSON objects. This makes the CLI suitable for use in scripts, CI pipelines, and tool integrations.

To get human-friendly output with Rich formatting (colored tables, syntax highlighting, status panels), pass `--human` or set the `ORCHEO_HUMAN` environment variable to a truthy value (`1`, `true`, `yes`, `on`):

```bash
# Machine-readable (default)
orcheo workflow list

# Human-friendly
orcheo --human workflow list

# Or via environment variable
export ORCHEO_HUMAN=1
orcheo workflow list
```

## Shell Auto-Completion

Enable fast shell auto-completion for commands and options:

```bash
orcheo --install-completion
```

This installs completion for your current shell (bash, zsh, fish, or PowerShell). After installation, restart your shell or source your shell configuration file.

## Available Commands

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
| `orcheo workflow run <workflow> [--inputs <json> \| --inputs-file <path>] [--config <json> \| --config-file <path>] [--verbose] [--stream/--no-stream]` | Trigger a workflow execution. Streaming is enabled by default. |
| `orcheo workflow evaluate <workflow> [--inputs <json> \| --inputs-file <path>] [--config <json> \| --config-file <path>] [--evaluation <json> \| --evaluation-file <path>] [--verbose] [--stream/--no-stream]` | Trigger a workflow evaluation run (requires streaming mode). |
| `orcheo workflow upload <file> [--name <name>] [--config <json> \| --config-file <path>]` | Upload a workflow from Python or JSON file. |
| `orcheo workflow download <workflow> [-o <file>] [--version <num>]` | Download workflow definition as Python or JSON. Use `--version` to download a specific version. |
| `orcheo workflow delete <workflow> [--force]` | Delete a workflow with confirmation safeguards. |
| `orcheo workflow schedule <workflow>` | Activate cron scheduling based on the workflow's cron trigger (no-op if none). |
| `orcheo workflow unschedule <workflow>` | Remove cron scheduling for the workflow. |
| `orcheo workflow publish <workflow> [--require-login] [--chatkit-public-base-url <url>]` | Publish a workflow for public ChatKit access, optionally requiring OAuth login and overriding the share-link origin for that run. |
| `orcheo workflow unpublish <workflow>` | Revoke public access and invalidate existing share links. |
| `orcheo credential list [--workflow-id <id>]` | List credentials with scopes, expiry, and health status. |
| `orcheo credential create <name> --provider <provider> --secret <secret>` | Create a new credential with guided prompts. `--secret` is required. |
| `orcheo credential delete <credential> [--force]` | Revoke a credential with confirmation safeguards. |
| `orcheo auth login [--no-browser] [--port <port>]` | Authenticate via browser-based OAuth flow. |
| `orcheo auth logout` | Clear stored OAuth tokens for the current profile. |
| `orcheo auth status` | Show current authentication status (OAuth or service token). |
| `orcheo token create [--id <id>] [--scope <scope>]` | Create a service token for CLI/API authentication. |
| `orcheo token list` | List all service tokens with their scopes and status. |
| `orcheo token show <token-id>` | Show detailed information for a specific service token. |
| `orcheo token rotate <token-id> [--overlap <seconds>]` | Rotate a service token with grace period overlap. |
| `orcheo token revoke <token-id> [--reason <reason>]` | Immediately invalidate a service token. |
| `orcheo config [--profile <name>] [--api-url <url>] [--service-token <token>] [--env-file <path>]` | Write CLI profile settings to `cli.toml`. Supports OAuth options (see below). |
| `orcheo code template [-o <file>] [--name <name>]` | Generate a minimal Python LangGraph workflow template file. |
| `orcheo code scaffold <workflow>` | Generate Python SDK code snippets to invoke an existing workflow. |
| `orcheo install [--yes] [--mode install\|upgrade] [--auth-mode api-key\|oauth] [--chatkit-domain-key <key>]` | Guided Docker-stack setup/upgrade (asset sync, `.env` updates, optional compose startup). |
| `orcheo install upgrade [--yes] [--auth-mode api-key\|oauth] [--chatkit-domain-key <key>]` | Guided upgrade shortcut command. |

`orcheo install` syncs local stack assets into `~/.orcheo/stack` (or
`ORCHEO_STACK_DIR`). Files are refreshed when upstream content differs.
When startup is enabled (`--start-local-stack`), setup then runs Docker Compose
(Docker must be installed). Setup also prompts for
`VITE_ORCHEO_CHATKIT_DOMAIN_KEY`; you can skip and continue, but ChatKit UI
features stay disabled until the key is set.

## Workflow Commands

### Running Workflows

Pass workflow inputs inline with `--inputs` or from disk via `--inputs-file`. Use `--config` or `--config-file` to provide LangChain runnable configuration for execution (each pair is mutually exclusive).

```bash
# Run with inline inputs
orcheo workflow run my-workflow --inputs '{"query": "hello"}'

# Run with inputs from file
orcheo workflow run my-workflow --inputs-file inputs.json
```

Streaming options:

- `--stream` (default): stream node and trace updates in real time.
- `--no-stream`: disable streaming for `workflow run` and create the run via API response payload.
- `--verbose`: include full payload output for stream updates.

In machine-readable mode (default, without `--human`), `--verbose` emits JSON event lines, including a start event (`workflow.execution.start`) and raw WebSocket updates until terminal status.

### Evaluating Workflows

Use `workflow evaluate` to run Agentensor evaluation mode:

```bash
# Evaluate with inline payload
orcheo workflow evaluate my-workflow \
  --inputs '{"query": "hello"}' \
  --evaluation '{"dataset": {"name": "golden"}}'

# Evaluate with files
orcheo workflow evaluate my-workflow \
  --inputs-file inputs.json \
  --evaluation-file evaluation.json \
  --verbose
```

`workflow evaluate` uses streaming mode and surfaces start events as `workflow.evaluation.start` in machine-readable verbose output.

### Publishing Workflows

Published workflows remain accessible until you run `orcheo workflow unpublish <workflow>` or toggle the `--require-login` flag to gate public chats behind OAuth.

```bash
# Publish a workflow for public access
orcheo workflow publish my-workflow

# Publish with login required
orcheo workflow publish my-workflow --require-login

# Revoke public access
orcheo workflow unpublish my-workflow
```

### Workflow Configuration

Upload-time defaults can be stored on a workflow version with `orcheo workflow upload ... --config` or `--config-file`. Stored config is merged with per-run overrides (run config wins). Avoid putting secrets in runnable config; use environment variables or credential vaults instead.

## Offline Mode

Pass `--offline` to reuse cached metadata when disconnected:

```bash
orcheo node list --offline
orcheo workflow show <workflow-id> --offline
```

## Configuration

The CLI reads configuration from (highest precedence first):

1. Command flags: `--api-url`, `--service-token`, `--profile`
2. Environment variables: `ORCHEO_API_URL`, `ORCHEO_SERVICE_TOKEN`
3. Config file: `~/.config/orcheo/cli.toml` (profiles for multiple environments)

### Writing Profiles with `orcheo config`

The `config` command writes profile settings to `cli.toml`, pulling values from flags, an `.env` file, or the current environment:

```bash
# Write a profile from flags
orcheo config --api-url https://api.example.com --service-token sk-...

# Write a named profile
orcheo config --profile staging --api-url https://staging.example.com

# Import settings from a .env file
orcheo config --env-file .env

# Write multiple profiles at once
orcheo config --profile dev --profile staging --env-file .env
```

The `config` command also accepts OAuth settings for browser-based authentication:

| Flag | Environment Variable | Config Key |
|------|---------------------|------------|
| `--auth-issuer` | `ORCHEO_AUTH_ISSUER` | `auth_issuer` |
| `--auth-client-id` | `ORCHEO_AUTH_CLIENT_ID` | `auth_client_id` |
| `--auth-scopes` | `ORCHEO_AUTH_SCOPES` | `auth_scopes` |
| `--auth-audience` | `ORCHEO_AUTH_AUDIENCE` | `auth_audience` |
| `--auth-organization` | `ORCHEO_AUTH_ORGANIZATION` | `auth_organization` |
| `--chatkit-public-base-url` | `ORCHEO_CHATKIT_PUBLIC_BASE_URL` | `chatkit_public_base_url` |

Once written to a profile, these values are used by `orcheo auth login` and other commands without needing environment variables.

See [Environment Variables](environment_variables.md) for the complete configuration reference.
