# Connect a Coding Agent to Orcheo Canvas

Use Claude Code, Cursor, or any CLI-capable coding agent to read and modify
your Orcheo workflows directly from the terminal. The agent stays in sync with
the workflow you have open in Canvas — no copy-pasting required.

## Prerequisites

- **Orcheo CLI** (`orcheo`) installed and updated to the latest version.
- An Orcheo account with API access.

## Quick Start

### 1. Authenticate

```bash
orcheo auth login
```

This opens your browser for OAuth login and stores credentials locally.
Alternatively set the `ORCHEO_SERVICE_TOKEN` environment variable.

### 2. Start the browser context bridge

```bash
orcheo browser-aware
```

This starts a lightweight HTTP server on `localhost:3333` that receives context
from your Canvas browser tabs. Keep it running while you work.

Use `--port` to change the port:

```bash
orcheo browser-aware --port 4444
```

### 3. Open Canvas

Navigate to any workflow in Orcheo Canvas. The browser tab automatically relays
which page and workflow you're viewing to the local server.

### 4. Use your agent

Your coding agent can now run CLI commands to interact with the active workflow:

```bash
# See what you have open in Canvas
orcheo context

# View workflow details
orcheo workflow show <workflow-id>

# Download the workflow script
orcheo workflow download <workflow-id>

# Download the script plus stored runnable config defaults
orcheo workflow download <workflow-id> --config-out workflow.config.json

# Upload an updated script
orcheo workflow upload --id <workflow-id> updated_script.py

# List all workflows
orcheo workflow list
```

## Connect Claude Code to Orcheo Canvas

1. Start the browser context bridge: `orcheo browser-aware`
2. Open a workflow in Canvas.
3. In your terminal, ask Claude Code: *"What workflow am I looking at?"*
4. Claude Code runs `orcheo context` to read the active workflow, then
   `orcheo workflow show <id>` or `orcheo workflow download <id>` to fetch the
   script.
5. Ask Claude Code to make changes — it will edit the script and run
   `orcheo workflow upload --id <id> <file>` to push the update.
6. Refresh Canvas to see the updated workflow graph.

## Connect Cursor to Orcheo Canvas

1. Start the browser context bridge: `orcheo browser-aware`
2. Open a workflow in Canvas.
3. In Cursor's terminal, run `orcheo context` to see the active workflow.
4. Use `orcheo workflow download <id>` to get the script, edit it in Cursor,
   then `orcheo workflow upload --id <id> <file>` to push changes.

## Multi-tab Support

If you have multiple Canvas tabs open, `orcheo context` returns the most
recently focused tab's context. Use `orcheo context sessions` to see all
active tabs:

```bash
orcheo context sessions
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `orcheo context` says "Could not connect" | Make sure `orcheo browser-aware` is running in another terminal. |
| `orcheo context` says "No active Canvas session" | Open Orcheo Canvas in your browser. The context relay only works when a Canvas tab is open. |
| Context is stale | Check that the Canvas tab is not minimized or suspended. The heartbeat pauses when the tab is hidden. |
| Authentication errors on workflow commands | Run `orcheo auth login` to refresh your credentials. |
