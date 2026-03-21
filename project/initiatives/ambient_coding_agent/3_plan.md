# Project Plan

## For Ambient Coding Agent — Browser Context MCP

- **Version:** 0.1
- **Author:** ShaojieJiang
- **Date:** 2026-03-21
- **Status:** Draft

---

## Overview

Deliver the Browser Context MCP feature in three phases: backend context store first (enabling CLI and MCP testing without any frontend changes), then Canvas integration for a complete end-to-end relay, then Canvas reload push and onboarding polish for GA.

**Related Documents:**
- Requirements: `project/initiatives/ambient_coding_agent/1_requirements.md`
- Design: `project/initiatives/ambient_coding_agent/2_design.md`

---

## Milestones

### Milestone 1: Backend Context Store + CLI Alpha

**Description:** Ship the backend context relay endpoints and the initial `orcheo browser` and `orcheo mcp` CLI commands. Developers can connect Claude Code or Codex via MCP and test all workflow tools. Canvas integration is not yet required — developers can call `POST /api/browser-context` manually to seed context during alpha testing.

#### Task Checklist

- [ ] Task 1.1: Implement `BrowserContextStore` — in-memory store keyed by `(user_id, session_id)` with 60-second TTL eviction, focus-priority resolution, and pin/unpin support
  - Dependencies: None
- [ ] Task 1.2: Implement `POST /api/browser-context` endpoint — upsert session entry, reset TTL, enforce rate limit (60 req/min/user)
  - Dependencies: Task 1.1
- [ ] Task 1.3: Implement `GET /api/browser-context` endpoint — return active context (focus-priority), include `staleness_seconds` and `total_sessions`
  - Dependencies: Task 1.1
- [ ] Task 1.4: Implement `GET /api/browser-context/sessions` endpoint — return all active sessions for the authenticated user
  - Dependencies: Task 1.1
- [ ] Task 1.5: Implement `POST /api/browser-context/pin` and `DELETE /api/browser-context/pin` endpoints
  - Dependencies: Task 1.1
- [ ] Task 1.6: Register all browser context routes in `factory.py` under authenticated router
  - Dependencies: Tasks 1.2–1.5
- [ ] Task 1.7: Write unit tests for `BrowserContextStore` (TTL, focus-priority, pin logic) and integration tests for all five endpoints
  - Dependencies: Tasks 1.2–1.5
- [ ] Task 1.8: Implement `orcheo browser context` CLI command — calls `GET /api/browser-context`, renders human-readable and `--json` output, shows staleness warning
  - Dependencies: Task 1.3
- [ ] Task 1.9: Implement `orcheo browser context --watch` — polls every 2 seconds, diffs and reprints on change
  - Dependencies: Task 1.8
- [ ] Task 1.10: Implement `orcheo browser context --session <id>` — fetches and displays a specific session from `GET /api/browser-context/sessions`
  - Dependencies: Task 1.4
- [ ] Task 1.11: Implement `orcheo browser sessions` — lists all active sessions with ID, page, focused state, workflow name, last-seen time
  - Dependencies: Task 1.4
- [ ] Task 1.12: Implement `orcheo browser pin <session-id>` and `orcheo browser unpin`
  - Dependencies: Task 1.5
- [ ] Task 1.13: Implement MCP tool definitions in `packages/sdk/orcheo_sdk/cli/mcp/tools.py` — all eight tools (`orcheo_get_context`, `orcheo_list_workflows`, `orcheo_get_workflow_script`, `orcheo_update_workflow_script`, `orcheo_create_workflow`, `orcheo_delete_workflow`, `orcheo_get_workflow_config`, `orcheo_update_workflow_config`)
  - Dependencies: Tasks 1.3, and existing workflow/credential API client in SDK
- [ ] Task 1.14: Implement `orcheo mcp serve` command — starts FastMCP server with HTTP (default `localhost:3333`) and `--stdio` transport; `--port` and `--session` flags
  - Dependencies: Task 1.13
- [ ] Task 1.15: Implement `orcheo mcp config` — resolves active profile and API token, prints ready-to-paste `.mcp.json` snippet with usage note to treat as secret
  - Dependencies: Task 1.14
- [ ] Task 1.16: Implement `orcheo mcp config --format claude-desktop` and `--format cursor` output variants
  - Dependencies: Task 1.15
- [ ] Task 1.17: Write unit tests for all eight MCP tools (correct REST calls, error handling) and smoke test for `orcheo mcp serve --stdio`
  - Dependencies: Task 1.13

---

### Milestone 2: Canvas Integration — End-to-End Context Relay

**Description:** Enable automatic context relay from Canvas browser tabs to the backend. After this milestone the full UX is live: open a workflow in Canvas, run `orcheo mcp serve`, and Claude Code sees the active workflow without any manual steps.

#### Task Checklist

- [ ] Task 2.1: Create `BrowserContextProvider` React component — generates stable `sessionId` from `sessionStorage` on mount, exposes `setPageContext()` via React context
  - Dependencies: Milestone 1
- [ ] Task 2.2: Implement context relay in `BrowserContextProvider` — posts context on `setPageContext()` call; attaches `visibilitychange`, `focus`, and `blur` event listeners; starts/stops 10-second heartbeat based on visibility; calls `authFetch`
  - Dependencies: Task 2.1
- [ ] Task 2.3: Mount `BrowserContextProvider` in `App.tsx` wrapping all authenticated routes
  - Dependencies: Task 2.2
- [ ] Task 2.4: Call `setPageContext({ page: 'gallery', ... })` in `WorkflowGallery` on workflow list load and update
  - Dependencies: Task 2.3
- [ ] Task 2.5: Call `setPageContext({ page: 'canvas', workflowId, workflowName, scriptSource })` in `WorkflowCanvas` on workflow load; update `scriptSource` when a new version is ingested
  - Dependencies: Task 2.3
- [ ] Task 2.6: Write unit tests for `BrowserContextProvider` — fires POST on route change, heartbeat start/stop on visibility change, focus flag accuracy
  - Dependencies: Task 2.2
- [ ] Task 2.7: Add "Connect your agent" section to Canvas Settings page — shows `orcheo mcp config` snippet with syntax highlighting, "Copy" button, and "Generate API token" button (reuses existing service token flow)
  - Dependencies: Task 2.3
- [ ] Task 2.8: Add active session indicator to the Settings "Connect your agent" section — polls `GET /api/browser-context/sessions` every 10 seconds and displays session count and last-seen time
  - Dependencies: Tasks 2.3, 2.7
- [ ] Task 2.9: End-to-end manual QA: open Canvas gallery → `orcheo browser context` shows gallery; navigate to workflow → context updates within 2 seconds; open two tabs → `orcheo browser sessions` shows both
  - Dependencies: Tasks 2.4, 2.5

---

### Milestone 3: Canvas Reload Push + GA Polish

**Description:** Close the write loop by pushing a reload event to Canvas when an agent mutates a workflow. Finalize documentation and onboarding guide for general availability.

#### Task Checklist

- [ ] Task 3.1: Implement backend SSE push endpoint `GET /api/browser-context/events` — streams `workflow_updated` events for the authenticated user; keyed per `workflow_id`
  - Dependencies: None (parallel with Milestone 2)
- [ ] Task 3.2: Emit `workflow_updated` SSE event from `orcheo_update_workflow_script` and `orcheo_create_workflow` MCP tools (via a shared notify hook on the ingest endpoint)
  - Dependencies: Task 3.1, Milestone 1
- [ ] Task 3.3: Implement SSE subscription in Canvas — `WorkflowCanvas` subscribes to `GET /api/browser-context/events`; on `workflow_updated` for the current workflow fires `WORKFLOW_STORAGE_EVENT` to trigger reload
  - Dependencies: Task 3.1
- [ ] Task 3.4: Implement SSE subscription in `WorkflowGallery` — on `workflow_updated` (any workflow ID) fires `WORKFLOW_STORAGE_EVENT` to refresh the gallery list
  - Dependencies: Task 3.1
- [ ] Task 3.5: Write integration tests — `orcheo_update_workflow_script` triggers SSE event; Canvas (mocked) receives event and fires reload
  - Dependencies: Tasks 3.2, 3.3
- [ ] Task 3.6: Write and publish onboarding documentation — "Connect Claude Code to Orcheo Canvas" and "Connect Cursor to Orcheo Canvas" guides; include `orcheo mcp config` one-liner setup
  - Dependencies: Milestones 1, 2
- [ ] Task 3.7: Run `make lint`, `make test`, `make canvas-lint`, `make canvas-test` — all green with zero errors
  - Dependencies: All previous tasks

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-03-21 | ShaojieJiang | Initial draft |

---

## Rollback / Contingency

- Context relay (`BrowserContextProvider`) can be disabled via feature flag without affecting any other Canvas functionality.
- If the context store causes unexpected backend load, the heartbeat interval can be increased server-side by adjusting the TTL without a client release.
- MCP server is CLI-side only; no rollback needed on the backend for Milestone 1 items beyond disabling the new routes in `factory.py`.
