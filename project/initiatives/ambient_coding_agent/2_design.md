# Design Document

## For Ambient Coding Agent — Browser Context MCP

- **Version:** 0.1
- **Author:** ShaojieJiang
- **Date:** 2026-03-21
- **Status:** Draft

---

## Overview

This feature exposes Orcheo Canvas context to external AI coding agents (Claude Code, Codex, Cursor, and any MCP-compatible tool) via an MCP server that runs locally on the developer's machine. The MCP server is shipped as part of the Orcheo CLI (`orcheo mcp serve`) and calls the Orcheo REST API directly for workflow operations.

The Canvas browser tab relays its current context (page, active workflow, script source) to a lightweight backend endpoint. The MCP server reads from this endpoint so any connected coding agent always knows what the user is looking at. Agents can then read and update workflows without the user leaving their terminal.

No AI infrastructure is hosted on the Orcheo platform. Users bring their own coding agents and subscriptions. Orcheo provides context and workflow tools, not the model.

## Components

- **Canvas Context Relay (TypeScript, Canvas team)**
  - Sends context updates to the backend on navigation, focus/visibility changes, and a 10-second heartbeat.
  - Generates a stable `sessionId` per tab (stored in `sessionStorage`).
  - Integrated as a side-effect inside a new `BrowserContextProvider` mounted at the app level.

- **Backend Context Store (Python/FastAPI, Backend team)**
  - Two new routers: `browser_context` and (Phase 3) `browser_context_sse`.
  - In-memory store keyed by `(user_id, session_id)` with 60-second TTL.
  - Focus-priority resolution: returns the most recently focused session; falls back to most recently seen.
  - Pinning support: a pinned session bypasses focus-priority.

- **Orcheo CLI — `orcheo browser` commands (Python/Click, SDK team)**
  - Calls `GET /api/browser-context` and `GET /api/browser-context/sessions`.
  - Provides human-readable and `--json` output modes.
  - `--watch` mode polls every 2 seconds and diffs output.

- **Orcheo CLI — `orcheo mcp serve` (Python/FastMCP, SDK team)**
  - Starts an MCP server (HTTP or stdio transport).
  - Implements all MCP tools by calling Orcheo REST API endpoints.
  - Reads browser context via `GET /api/browser-context`.
  - Auth: uses the same `ORCHEO_SERVICE_TOKEN` / `~/.config/orcheo/cli.toml` profile as the rest of the CLI.

- **Canvas Settings — "Connect your agent" UI (TypeScript, Canvas team)**
  - New section in Settings showing MCP config snippet and API token generator.
  - Displays active session count and staleness as a health indicator.

## Request Flows

### Flow 1: Context relay — tab navigation

1. User navigates to `/workflow-canvas/abc` in Canvas.
2. `BrowserContextProvider` detects route change via React Router `useLocation`.
3. Provider calls `POST /api/browser-context` with `{ sessionId, page: 'canvas', workflowId: 'abc', workflowName: 'My Flow', scriptSource: '...', focused: true }`.
4. Backend upserts the session entry; TTL reset to 60 seconds.
5. Tab starts heartbeat (every 10 seconds) while `document.visibilityState === 'visible'`.

### Flow 2: Agent reads current context

1. Developer runs `orcheo mcp serve` locally.
2. Claude Code (configured with `.mcp.json` pointing to localhost) calls MCP tool `orcheo_get_context()`.
3. MCP server calls `GET /api/browser-context` with the developer's bearer token.
4. Backend returns the active session's context: `{ page: 'canvas', workflowId: 'abc', workflowName: 'My Flow', scriptSource: '...', staleness_seconds: 3 }`.
5. Claude Code sees the current workflow and can act on it.

### Flow 3: Agent updates a workflow script

1. Developer asks Claude Code: "Add error handling to the main node."
2. Claude Code calls `orcheo_get_workflow_script('abc')` → receives current script.
3. Claude Code generates an updated script.
4. Claude Code calls `orcheo_update_workflow_script('abc', updated_script)`.
5. MCP server calls `POST /api/workflows/abc/versions/ingest` with the updated script.
6. Backend ingests the new version and (Phase 3) sends an SSE reload event to all Canvas tabs watching workflow `abc`.
7. Canvas receives the event, fires `WORKFLOW_STORAGE_EVENT`, and reloads the workflow graph.
8. Developer sees the updated canvas within seconds.

### Flow 4: Multi-tab disambiguation

1. Developer has two Canvas tabs open: Tab A (gallery, focused 2 minutes ago) and Tab B (workflow X, focused 10 seconds ago).
2. Both tabs are backgrounded; developer switches to terminal.
3. `orcheo browser context` (or Claude Code via MCP) calls `GET /api/browser-context`.
4. Backend returns Tab B's context (most recently focused, within TTL).
5. Developer runs `orcheo browser sessions` — sees both sessions with their pages and last-seen times.
6. Developer runs `orcheo browser pin <tab-a-session-id>` to override.
7. Subsequent `orcheo_get_context()` calls return Tab A's gallery context until unpinned.

### Flow 5: Developer onboarding (`orcheo mcp config`)

1. Developer runs `orcheo mcp config`.
2. CLI resolves active profile, reads API token, and prints:
   ```json
   {
     "mcpServers": {
       "orcheo": {
         "command": "orcheo",
         "args": ["mcp", "serve", "--stdio"],
         "env": { "ORCHEO_SERVICE_TOKEN": "<token>" }
       }
     }
   }
   ```
3. Developer pastes into `~/.claude/claude_desktop_config.json` (or `.mcp.json` for HTTP mode).
4. Agent is connected.

### Flow 6: Stale / no active session

1. Developer has no Canvas tab open.
2. Claude Code calls `orcheo_get_context()`.
3. MCP server calls `GET /api/browser-context` → response: `{ page: null, staleness_seconds: 120, total_sessions: 0 }`.
4. MCP tool returns: `"No active Canvas session found. Open Orcheo Canvas in your browser to provide context."`.
5. Claude Code can still call other tools (`orcheo_list_workflows`, etc.) that don't depend on browser context.

## API Contracts

### Context relay endpoints

```
POST /api/browser-context
Authorization: Bearer <token>
Body:
  session_id:    string   -- stable per-tab identifier (sessionStorage)
  page:          string   -- "gallery" | "canvas" | "other"
  workflow_id:   string | null
  workflow_name: string | null
  script_source: string | null  -- latest Python script, null on gallery/other
  focused:       bool    -- document.hasFocus() at time of post
  timestamp:     string  -- ISO 8601

Response:
  204 No Content
  401 Unauthorized
```

```
GET /api/browser-context
Authorization: Bearer <token>

Response:
  200 OK ->
    {
      "session_id":       string | null,
      "page":             string | null,
      "workflow_id":      string | null,
      "workflow_name":    string | null,
      "script_source":    string | null,
      "focused":          bool,
      "staleness_seconds": int,
      "total_sessions":   int,
      "pinned":           bool
    }
  401 Unauthorized
```

```
GET /api/browser-context/sessions
Authorization: Bearer <token>

Response:
  200 OK ->
    [
      {
        "session_id":       string,
        "page":             string,
        "workflow_id":      string | null,
        "workflow_name":    string | null,
        "focused":          bool,
        "last_seen":        string,   -- ISO 8601
        "staleness_seconds": int,
        "pinned":           bool
      }
    ]
```

```
POST /api/browser-context/pin
Authorization: Bearer <token>
Body:
  session_id: string

Response:
  204 No Content
  404 Session not found or expired
```

```
DELETE /api/browser-context/pin
Authorization: Bearer <token>

Response:
  204 No Content
```

### MCP tools (via `orcheo mcp serve`)

All tools call the existing Orcheo REST API. The MCP server is a thin translation layer.

| Tool | Underlying REST call |
|------|---------------------|
| `orcheo_get_context()` | `GET /api/browser-context` |
| `orcheo_list_workflows()` | `GET /api/workflows` |
| `orcheo_get_workflow_script(workflow_id)` | `GET /api/workflows/{ref}/versions` → latest version `graph.source` |
| `orcheo_update_workflow_script(workflow_id, script)` | `POST /api/workflows/{ref}/versions/ingest` |
| `orcheo_create_workflow(name, script)` | `POST /api/workflows` then `POST /api/workflows/{ref}/versions/ingest` |
| `orcheo_delete_workflow(workflow_id)` | `DELETE /api/workflows/{ref}` |
| `orcheo_get_workflow_config(workflow_id)` | `GET /api/workflows/{ref}/versions` → latest `runnable_config` |
| `orcheo_update_workflow_config(workflow_id, config_patch)` | `PUT /api/workflows/{ref}/versions/{v}/runnable-config` |

## Data Models / Schemas

### BrowserContextEntry (backend in-memory)

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | string | Authenticated user |
| `session_id` | string | Stable per-tab ID from `sessionStorage` |
| `page` | string | `"gallery"` \| `"canvas"` \| `"other"` |
| `workflow_id` | string \| null | Current workflow ID (canvas page only) |
| `workflow_name` | string \| null | Human-readable workflow name |
| `script_source` | string \| null | Latest LangGraph Python script |
| `focused` | bool | Whether tab had focus at last update |
| `last_seen` | datetime | UTC timestamp of last POST |
| `pinned` | bool | Whether this session is pinned by the user |

TTL: entries are evicted 60 seconds after `last_seen`. The store is per-user; entries from different users are isolated.

### Context relay POST body (TypeScript → backend)

```typescript
interface BrowserContextPayload {
  sessionId: string;
  page: 'gallery' | 'canvas' | 'other';
  workflowId: string | null;
  workflowName: string | null;
  scriptSource: string | null;
  focused: boolean;
  timestamp: string; // ISO 8601
}
```

## Security Considerations

- All context relay and MCP endpoints require a valid bearer token (same auth as existing API). Unauthenticated requests return 401.
- `script_source` is stored in memory only; it is never written to a persistent store. It is evicted with the TTL.
- The context store is strictly per-user: `GET /api/browser-context` returns only the authenticated user's sessions.
- `orcheo mcp serve` runs locally on the developer's machine; the MCP socket is bound to `localhost` by default (not `0.0.0.0`). Stdio transport has no network exposure.
- `orcheo mcp config` embeds the user's service token in the printed config snippet. CLI warns the user to treat the snippet as a secret.
- Rate limiting: `POST /api/browser-context` is limited to 60 requests per minute per user (one per second, generous headroom for 10-second heartbeat).

## Performance Considerations

- In-memory context store: O(1) upsert and read; no database queries on the hot path.
- `POST /api/browser-context` body is < 2 KB (script source truncated to 50 KB with a truncation flag if larger); single in-memory write per request.
- Heartbeat interval is 10 seconds per tab; at 1,000 concurrent active users this is ~100 requests/second — well within backend capacity.
- `orcheo mcp serve` makes one HTTP request per tool call; no persistent connections to maintain on the backend.
- Phase 3 SSE push for canvas reload: one SSE connection per open Canvas tab, server sends at most one event per workflow update.

## Testing Strategy

- **Unit tests**
  - `BrowserContextStore`: TTL eviction, focus-priority resolution, pin/unpin logic, multi-session ordering.
  - `BrowserContextProvider` (React): fires POST on route change, `visibilitychange`, and `focus`; stops heartbeat on `visibilitychange=hidden`.
  - Each MCP tool: correct REST endpoint called, correct response schema returned, graceful error on 404/401.
  - `orcheo browser context`: correct output format, `--json` flag, staleness display.

- **Integration tests**
  - POST then GET round-trip returns correct context.
  - TTL eviction: session expires after 60 seconds without heartbeat.
  - Multi-session: two sessions with different focus states; GET returns most recently focused.
  - Pin/unpin: pinned session returned even when a newer focused session exists.
  - `orcheo_update_workflow_script` calls ingest endpoint and returns new version ID.

- **Manual QA checklist**
  - Open Canvas on gallery → `orcheo browser context` shows `page: gallery`.
  - Navigate to a workflow → `orcheo browser context` updates within 2 seconds.
  - Open second Canvas tab → `orcheo browser sessions` shows two sessions.
  - Close one tab → session disappears from `orcheo browser sessions` within 60 seconds.
  - Run `orcheo mcp serve --stdio` → configure in Claude Code → ask "what workflow am I looking at?" → correct answer.
  - Ask Claude Code to update the current workflow → Canvas reloads (Phase 3).
  - Run `orcheo mcp config --format claude-desktop` → paste into config → MCP server connects.

## Rollout Plan

1. **Phase 1** — Backend context store + CLI alpha: ship `POST/GET /api/browser-context` endpoints and `orcheo browser context`, `orcheo mcp serve`. Developers can test the full MCP loop without any Canvas changes by manually calling the context POST endpoint.
2. **Phase 2** — Canvas integration: enable context relay in Canvas (`BrowserContextProvider`). Ship `orcheo browser sessions`, `orcheo browser pin/unpin`, `orcheo mcp config`. Add "Connect your agent" Settings section. End-to-end flow is fully functional.
3. **Phase 3** — Canvas reload push: implement SSE push from backend on workflow mutation; Canvas subscribes and reloads. Ship `orcheo mcp config --format` variants for Cursor and Claude Desktop. Publish onboarding guide.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-03-21 | ShaojieJiang | Initial draft |
