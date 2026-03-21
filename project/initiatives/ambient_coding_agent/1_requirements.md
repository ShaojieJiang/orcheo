# Requirements Document

## METADATA
- **Authors:** ShaojieJiang
- **Project/Feature Name:** Ambient Coding Agent — Browser Context MCP
- **Type:** Feature
- **Summary:** Expose Orcheo Canvas context (current page, active workflow, script source) to external coding agents (Claude Code, Codex, Cursor, etc.) via an MCP server, enabling agents to read and modify workflows without leaving the user's own terminal or IDE. No platform-side AI infrastructure required; users bring their own agents and subscriptions.
- **Owner (if different than authors):** ShaojieJiang
- **Date Started:** 2026-03-21

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| Architecture — CLI Tool Design | `project/architecture/cli_tool_design.md` | ShaojieJiang | Orcheo CLI design |
| Prior Initiative — Python-Only Workflow Composition | `project/initiatives/python_only_workflow_composition/1_requirements.md` | ShaojieJiang | Python-only composition requirements |
| Design | `project/initiatives/ambient_coding_agent/2_design.md` | ShaojieJiang | Ambient coding agent design |
| Plan | `project/initiatives/ambient_coding_agent/3_plan.md` | ShaojieJiang | Ambient coding agent plan |

## PROBLEM DEFINITION

### Objectives
Enable developers to use their preferred AI coding agents (Claude Code, Codex, Cursor, etc.) to read and modify Orcheo workflows from their local terminal, with the agent always aware of what the user is looking at in Canvas. Deliver this without building platform-side AI infrastructure, a web terminal, or requiring users to manage API keys.

### Target users
- Developers who use Claude Code, Codex, or Cursor locally and want those agents to act on their Orcheo workflows
- Teams that prefer a code-first workflow authoring experience with an ambient AI assistant
- Platform operators who want to offer an MCP-compatible interface without owning the agent compute

### User Stories

| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| Developer with Claude Code | Run `orcheo mcp serve` and have Claude Code know which workflow I have open in Canvas | Claude Code can read and update my workflow without me copying and pasting scripts | P0 | `orcheo browser context` returns active Canvas page and workflow; Claude Code calling `orcheo_get_context()` via MCP returns the same data |
| Developer | Have the context update automatically when I switch tabs or navigate to a different workflow | I don't have to restart or re-configure my MCP server | P0 | Navigating in Canvas from gallery to a workflow canvas updates the context returned by MCP within 2 seconds |
| Developer | Run `orcheo browser sessions` to see all my open Canvas tabs | I can diagnose which session is being used as the active context source | P1 | Command lists session IDs, pages, focus state, and last-seen timestamps |
| Developer | Pin a specific Canvas session as the authoritative context source | I can work with two Canvas tabs open and control which one feeds my coding agent | P1 | `orcheo browser pin <session-id>` causes MCP to serve that session's context regardless of focus |
| Developer | Paste an MCP config snippet from `orcheo mcp config` into `.mcp.json` | Onboarding takes under two minutes | P0 | Running `orcheo mcp config` prints a ready-to-paste snippet with the user's API token embedded |
| Developer | Ask Claude Code to create a new workflow | The workflow appears in Canvas without manual copy-paste | P0 | Claude Code calls `orcheo_create_workflow`; workflow appears in Canvas gallery within 5 seconds |
| Developer | Ask Claude Code to update the current workflow | The canvas reloads with the updated script | P0 | Claude Code calls `orcheo_update_workflow_script`; Canvas fires a reload event and shows the updated graph |
| Platform operator | Deploy the context relay endpoint without enabling full MCP infrastructure | The context store is a lightweight addition to the existing backend | P1 | `POST /api/browser-context` and `GET /api/browser-context` can be deployed independently; MCP server is CLI-side only |

### Context, Problems, Opportunities

Orcheo workflows are authored as Python LangGraph scripts. The natural place to write and modify these is a code editor or terminal, not a drag-and-drop canvas. Developers who use AI coding agents (Claude Code, Codex, Cursor) today must manually copy the workflow script out of Canvas, paste it into their editor, make changes, and re-upload — a friction-heavy loop.

The opportunity is to make Canvas context available to any MCP-compatible agent via a standardised protocol. The agent runs wherever the developer already works; Orcheo provides context and workflow tools, not the agent itself. This avoids the complexity and cost of platform-side AI infrastructure while delivering the ambient coding agent experience the developer ecosystem expects.

The adjacent space (VS Code Copilot, Claude Code, Cursor) has established that developers want AI assistance that is aware of their current working context. Orcheo's workflow canvas is the equivalent of the "current file" — it should be equally accessible to these agents.

### Product Goals and Non-goals

**Goals:**
- Expose Canvas context (page, workflow ID, workflow name, script source) to external MCP clients via the Orcheo CLI.
- Provide CLI commands for developers to inspect, watch, and manage browser context sessions.
- Enable the full read/write workflow loop: agent reads context → modifies script → Canvas reloads.
- Handle multiple open Canvas tabs gracefully without requiring agent reconfiguration.

**Non-goals:**
- Building or hosting AI agents, models, or inference infrastructure on the Orcheo platform.
- Requiring users to enter AI provider API keys into Orcheo (users authenticate directly with their own agent CLI).
- Providing a web terminal or in-canvas chat UI (future initiative if needed).
- Real-time collaborative editing or multi-user context sharing across different user accounts.

## PRODUCT DEFINITION

### Requirements

**P0: Context relay (Canvas → backend)**
- Canvas posts context on every page navigation and focus/visibility change to `POST /api/browser-context`.
- Payload includes: `sessionId` (stable per tab, `sessionStorage`-backed), `page` (`gallery` | `canvas` | `other`), `workflowId`, `workflowName`, `scriptSource`, `focused` (bool), `timestamp`.
- Heartbeat every 10 seconds while the tab is visible; stops when hidden or closed.
- Context entries expire server-side after 60 seconds without a heartbeat (tab considered closed).

**P0: Context store (backend)**
- `POST /api/browser-context` — upserts a session entry for the authenticated user.
- `GET /api/browser-context` — returns the active context: the most recently focused session, or the most recently seen if none are focused. Includes `session_id`, `page`, `workflow_id`, `workflow_name`, `script_source`, `staleness_seconds`, `total_sessions`.
- `GET /api/browser-context/sessions` — returns all active sessions for the user (for `orcheo browser sessions`).
- `POST /api/browser-context/pin` — pins a session as authoritative; pinned session is served regardless of focus.
- `DELETE /api/browser-context/pin` — removes the pin.
- Auth: all endpoints require the user's bearer token.

**P0: CLI — `orcheo browser` command group**
- `orcheo browser context` — print the current active Canvas context (page, workflow name, script summary).
- `orcheo browser context --json` — machine-readable output.
- `orcheo browser context --watch` — stream context changes in real-time (poll or SSE).
- `orcheo browser context --session <id>` — get context for a specific session.
- `orcheo browser sessions` — list all active sessions with ID, page, focused state, last-seen time.

**P1: CLI — session pinning**
- `orcheo browser pin <session-id>` — pin a session.
- `orcheo browser unpin` — remove pin.

**P0: CLI — `orcheo mcp` command group**
- `orcheo mcp serve` — start MCP server on `localhost:3333` (HTTP, streamable HTTP transport).
- `orcheo mcp serve --port <port>` — custom port.
- `orcheo mcp serve --stdio` — stdio transport for Claude Desktop / Claude Code.
- `orcheo mcp serve --session <id>` — lock MCP server to serve a specific Canvas session's context.
- `orcheo mcp config` — print a ready-to-paste `.mcp.json` snippet with the user's API token.
- `orcheo mcp config --format claude-desktop` — format for `claude_desktop_config.json`.
- `orcheo mcp config --format cursor` — format for Cursor's MCP settings.

**P0: MCP tools exposed by `orcheo mcp serve`**

| Tool | Description |
|------|-------------|
| `orcheo_get_context()` | Return current Canvas page, workflow ID, name, and script source |
| `orcheo_list_workflows()` | List all user workflows (ID, name, created, last modified) |
| `orcheo_get_workflow_script(workflow_id)` | Fetch the latest LangGraph Python script for a workflow |
| `orcheo_update_workflow_script(workflow_id, script)` | Push a new version; triggers Canvas reload event |
| `orcheo_create_workflow(name, script)` | Create a new workflow from a LangGraph Python script |
| `orcheo_delete_workflow(workflow_id)` | Archive a workflow |
| `orcheo_get_workflow_config(workflow_id)` | Fetch runnable config for a workflow version |
| `orcheo_update_workflow_config(workflow_id, config_patch)` | Patch runnable config without creating a new version |

**P0: Canvas Settings — "Connect your agent" UI**
- New section in Canvas Settings showing the MCP config snippet and a "Generate API token" button.
- Shows active session count and last-seen time as a connection health indicator.
- Token generation reuses the existing API token / service token mechanism.

**P1: Canvas reload on workflow mutation**
- When `orcheo_update_workflow_script` or `orcheo_create_workflow` succeeds, the backend sends a lightweight event (SSE or WebSocket push) to all Canvas tabs for that workflow.
- Canvas subscribes and fires `WORKFLOW_STORAGE_EVENT` on receipt to trigger a reload.
- If no Canvas tab is listening, the change is still persisted; the tab picks it up on next focus.

### Designs (if applicable)
See `project/initiatives/ambient_coding_agent/2_design.md`.

### Other Teams Impacted
- **Canvas Frontend:** New context relay (JS), Settings UI section, and optional SSE subscription for reload events.
- **Backend:** Two new lightweight routers (`browser_context`, optional SSE push); no changes to existing workflow or credential routers.
- **CLI/SDK (`packages/sdk`):** New `browser` and `mcp` command groups; MCP server logic lives in CLI package.

## TECHNICAL CONSIDERATIONS

### Architecture Overview

```
Canvas (browser tab)
  └── context relay: POST /api/browser-context on navigation + focus events + heartbeat

Backend (Orcheo server)
  ├── POST /api/browser-context   ← upsert session context
  ├── GET  /api/browser-context   ← return active context (focus-priority)
  └── GET  /api/browser-context/sessions

Local machine (developer)
  orcheo mcp serve
    ├── Exposes MCP server (localhost or stdio)
    ├── orcheo_get_context()  →  GET /api/browser-context
    ├── orcheo_list/create/update/delete workflow tools  →  GET|POST /api/workflows/...
    └── orcheo_get/update_workflow_config tools  →  PUT /api/workflows/{ref}/versions/{v}/runnable-config

Claude Code / Codex / Cursor
  └── .mcp.json points to orcheo mcp serve
```

### Technical Requirements
- Backend context store must be in-memory with TTL support (Redis in production); no new persistent DB schema required.
- MCP server uses the `mcp` Python SDK (`FastMCP`) with streamable HTTP transport and stdio transport support.
- Context relay runs in the browser as a side-effect of page navigation and the `visibilitychange`/`focus` DOM events; no new React components needed, only a small module imported by the `AmbientAgentContext` provider.
- Multi-tab disambiguation is resolved server-side using focus state and last-seen timestamps; clients do not need to coordinate.
- CLI `orcheo mcp serve` requires a valid Orcheo API token (same `ORCHEO_SERVICE_TOKEN` / `orcheo login` flow already defined in `cli_tool_design.md`).
- Canvas Settings token generation extends the existing service token or long-lived API token mechanism; no new auth primitives needed.

## LAUNCH/ROLLOUT PLAN

### Success metrics

| KPIs | Target & Rationale |
|------|--------------------|
| [Primary] MCP server adoption | ≥ 20% of active developer users run `orcheo mcp serve` within 30 days of GA |
| [Secondary] Workflow updates via MCP | ≥ 10% of workflow version pushes originate from MCP tool calls within 60 days |
| [Guardrail] Context staleness | p95 staleness of `GET /api/browser-context` < 5 seconds when a Canvas tab is open |
| [Guardrail] Backend load | Context relay endpoint adds < 2% overhead to backend request volume |

### Rollout Strategy

Three sequential phases: backend context store first (no frontend changes needed), then CLI commands and MCP server, then Canvas UI polish and reload integration. The context relay can be shipped behind a feature flag on the Canvas side to allow gradual rollout.

### Estimated Launch Phases

| Phase | Target | Description |
|-------|--------|-------------|
| **Phase 1** | Internal engineering | Backend context store endpoints; CLI `orcheo browser context` and `orcheo mcp serve` (alpha). No Canvas integration yet — developers can test MCP tools manually. |
| **Phase 2** | Beta users / developer waitlist | Canvas context relay enabled; end-to-end flow works. CLI `orcheo mcp config` and all `orcheo browser` subcommands shipped. Canvas Settings "Connect your agent" section added. |
| **Phase 3** | GA | Canvas reload-on-mutation via SSE push. Full documentation and onboarding guide. `orcheo mcp config --format` for all major agent IDEs. |

## HYPOTHESIS & RISKS

**Hypothesis:** Developers who already use Claude Code or Codex will adopt `orcheo mcp serve` as their primary workflow authoring interface once they can operate on their Canvas context without leaving the terminal. This will increase workflow version push volume and daily active engagement with the platform.

**Risks:**
- Multi-tab context ambiguity may confuse users if the wrong session's context is served. Mitigation: `orcheo browser sessions` provides visibility; `orcheo browser pin` provides explicit control; context response always includes `staleness_seconds` and `total_sessions` so agents can surface a warning.
- Browser tab heartbeat adds a small constant load to the backend. Mitigation: heartbeat is 10-second interval, POST body is < 1 KB, and the endpoint does a single in-memory upsert. Load impact is negligible at current scale.
- MCP protocol is evolving; breaking changes in the `mcp` SDK or transport spec could require updates. Mitigation: pin `mcp` SDK version; monitor MCP specification changelog.
- Users may expect Orcheo to host Claude or another AI model. Mitigation: documentation clearly frames this as "bring your own agent"; the Settings UI copy emphasises user-owned subscriptions.

## APPENDIX
- MCP specification: https://modelcontextprotocol.io
- Existing CLI design: `project/architecture/cli_tool_design.md`
- Existing service token auth: `project/architecture/authentication_design.md`
