# MCP Integration

Orcheo SDK includes an MCP (Model Context Protocol) server that allows AI assistants like Claude to interact with your workflows directly.

## Overview

The MCP server exposes Orcheo functionality to AI coding agents, enabling them to:

- List and inspect workflows
- Execute workflows and stream results
- Manage credentials and tokens
- Create and upload new workflows

## Claude Desktop

To configure the MCP server in Claude Desktop, add the following to your `claude_desktop_config.json`:

```json
"Orcheo": {
  "command": "/path/to/uvx",
  "args": ["--from", "orcheo-sdk@latest", "orcheo-mcp"],
  "env": {
    "ORCHEO_API_URL": "http://localhost:8000"
  }
}
```

!!! note
    This configuration requires the Orcheo backend to be running. See [Manual Setup Guide](manual_setup.md) for instructions.

## Claude Code

To configure the MCP server in Claude Code:

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

!!! tip
    Replace `/path/to/uvx` with your actual `uvx` binary path (find it with `which uvx`).

## Codex CLI

To configure the MCP server in Codex CLI:

```bash
codex add server Orcheo \
  /path/to/uvx \
  --from orcheo-sdk@latest orcheo-mcp \
  --env ORCHEO_API_URL=http://localhost:8000
```

!!! tip
    Replace `/path/to/uvx` with your actual `uvx` binary path (find it with `which uvx`).

## Authentication

When using the MCP server with authentication enabled, add your service token to the environment:

```json
"Orcheo": {
  "command": "/path/to/uvx",
  "args": ["--from", "orcheo-sdk@latest", "orcheo-mcp"],
  "env": {
    "ORCHEO_API_URL": "http://localhost:8000",
    "ORCHEO_SERVICE_TOKEN": "your-service-token"
  }
}
```

See [Authentication Guide](authentication_guide.md) for details on creating service tokens.
