# ChatKit Integration Design

## Overview
This document outlines how to integrate OpenAI's ChatKit widget with the Orcheo platform so chat interactions can execute Orcheo workflows through a dedicated backend endpoint. The initial release focuses on a prototype experience that exercises the full end-to-end flow without yet connecting to production data sources.

## Goals & Non-Goals
### Goals
- Enable the `examples/chatkit-orcheo.html` demo to communicate with an Orcheo-hosted ChatKit endpoint.
- Let operators choose an Orcheo workflow to power each chat session.
- Forward ChatKit requests to the selected workflow via a LangGraph-driven orchestration layer.
- Persist chat files and threads in SQLite to simplify local development while we evaluate long-term storage options.
- Provide a clear milestone plan so this integration becomes the next actionable Milestone 5 task.

### Non-Goals
- Shipping a production-ready ChatKit experience (e.g., authentication, rate limiting, billing) — those land in later milestones.
- Implementing the full backend or modifying existing workflows; this document only guides the future implementation work.
- Delivering a customizable front-end beyond the demo HTML file.

## High-Level Architecture
1. **ChatKit Web Demo** (`examples/chatkit-orcheo.html`)
   - Adds a workflow selector UI next to the ChatKit widget.
   - Initializes the ChatKit client with Orcheo theme overrides and custom action handlers.
   - Submits message payloads to `/api/chatkit/sessions/{session_id}/messages` and action payloads to `/api/chatkit/sessions/{session_id}/actions`.

2. **Orcheo Backend API** (`src/orcheo/main.py` future changes)
   - Exposes REST endpoints for session creation, message ingestion, action routing, and status polling.
   - Marshals ChatKit payloads into LangGraph run requests and returns streaming updates compatible with ChatKit expectations.

3. **LangGraph Workflow Adapter** (`examples/chatkit_workflow_graph.py` proposed)
   - Defines a vanilla LangGraph graph using `langgraph.graph.Graph` following `examples/vanilla_langgraph.py` patterns.
   - Provides scripted responses for now, emulating workflow outputs and handing back structured messages/actions to the ChatKit client.

4. **SQLite Persistence Layer** (`src/orcheo/storage/sqlite_chat_store.py` proposed)
   - Stores chat sessions, threads, messages, and file references using SQLite via SQLAlchemy (or Python's `sqlite3` for minimal dependency footprint).
   - Enables offline testing, quick resets, and simple backup semantics during prototyping.

## Detailed Design
### Frontend (ChatKit Demo Page)
- **Workflow Selector UI**: Add a `<select>` element populated from `/api/chatkit/workflows` so the operator can choose an Orcheo workflow. When the fetch fails, surface a non-blocking inline error, keep the selector disabled, and offer a "Retry" control that reuses cached results when available. Fall back to client-side JSON seed for local demos so the prototype stays usable offline.
- **ChatKit Client Initialization**:
  - Use `ChatKit.init({ apiUrl: '/api/chatkit', theme: 'orcheo', actions: [...] })` to point to the new backend.
  - Register action handlers that translate ChatKit action invocations (buttons, forms) into POST requests.
  - Persist the selected workflow ID in `localStorage` and include it in every request header or payload.
- **Event Flow**:
  - On message submit, call `POST /api/chatkit/sessions/{session_id}/messages` with the message, attachments, and `workflow_id`.
  - Listen to Server-Sent Events or WebSocket responses for streaming tokens and update the widget accordingly.
  - Render system/tool messages returned by the backend using ChatKit's `message` API.

### Backend API Contract
| Endpoint | Method | Purpose | Notes |
| --- | --- | --- | --- |
| `/api/chatkit/workflows` | GET | List available workflows for the selector | Reads from Orcheo workflow registry; returns `[{id, name, description}]`. |
| `/api/chatkit/sessions` | POST | Create a new ChatKit session | Accepts optional `workflow_id`. Returns `session_id` and stream URL. |
| `/api/chatkit/sessions/{session_id}/messages` | POST | Submit a new user message | Persists message, triggers LangGraph run, streams output. |
| `/api/chatkit/sessions/{session_id}/actions` | POST | Handle ChatKit action invocations | Forwards payloads to LangGraph nodes as events. |
| `/api/chatkit/sessions/{session_id}` | GET | Fetch session summary/state | Used for reconnection and debugging. |

- Idempotency: message submissions include a client-supplied `message_id` so retried requests are deduplicated. Concurrent message submissions in the same session are serialized by the backend queue to preserve ordering while still returning 409 errors if a conflicting run is in-flight.
- Responses follow JSON API conventions with `data` envelopes, while streaming uses server-sent events (SSE) to align with ChatKit's streaming mode.
- Authentication is deferred; local development uses unsecured endpoints behind localhost.

### Error Handling Strategy
- **Session lifecycle**: creation failures return structured error payloads (`status`, `detail`, `retry_after`). The frontend surfaces inline notices and allows the operator to retry without refreshing.
- **Message submission**: timeouts trigger backend cancellation of the LangGraph run, emit a `run_timeout` SSE event, and prompt the client to offer retry or escalation actions. Unexpected exceptions are wrapped in `run_failed` events with sanitized stack summaries and correlation IDs for logs.
- **ChatKit client resilience**: the frontend listens for dropped SSE connections, displays a reconnect banner, and resends the last acknowledged event ID to resume streaming without duplicating messages.
- **Repository errors**: SQLite write failures raise 500 responses tagged with `storage_error`; the handler retries transient errors (e.g., `database is locked`) twice with exponential backoff before surfacing the failure.
- **File uploads**: invalid MIME types or oversized files are rejected with 413/415 responses that the frontend renders inline. Files are stored only after full validation to avoid orphaned blobs.

### Performance & Scalability Considerations
- **SQLite concurrency**: use a write queue with short-lived transactions to avoid `database locked` errors. Document the path to upgrade to Postgres once concurrency requirements exceed prototype limits.
- **Streaming throughput**: SSE responses flush every 200ms batch to balance responsiveness with CPU usage. The design includes metrics hooks (via UVicorn access logs and custom counters) to measure token latency.
- **Memory footprint**: large responses stream directly from LangGraph without buffering entire payloads in memory. Attachments are spooled to disk using `SpooledTemporaryFile` to avoid holding multi-megabyte uploads in RAM.
- **Future scaling**: call out that the `/api/chatkit` router can be fronted by an ASGI server supporting HTTP/2 (e.g., Hypercorn) and that stateful session data should migrate to Redis/Postgres when moving beyond the prototype.

### Security & Validation
- **Input validation**: Pydantic models enforce payload shapes, size limits, and allowed action types. Invalid fields respond with 422 errors and descriptive messages for the frontend.
- **File hygiene**: configure allowed MIME types/extensions via environment variable (`ORCHEO_CHATKIT_ALLOWED_FILE_TYPES`) and enforce a max size (`ORCHEO_CHATKIT_MAX_UPLOAD_MB`). The upload directory path defaults to `data/chatkit_uploads/` but can be overridden (`ORCHEO_CHATKIT_UPLOAD_DIR`). A periodic cleanup task removes files older than 7 days for abandoned sessions.
- **Secrets management**: ChatKit API keys live in `.env` and are injected into the frontend demo only when explicitly enabled. Production hardening (auth, rate limiting) remains out of scope but is highlighted for the next milestone.
- **Logging**: redact message content from debug logs by default, storing only metadata and correlation IDs.

### Development Setup (Getting Started)
1. Install dependencies: `uv sync --all-groups` (adds `fastapi-sse-starlette` or equivalent SSE helper if not already present).
2. Seed environment: copy `.env.example` to `.env`, set `ORCHEO_CHATKIT_UPLOAD_DIR` (optional), and export the ChatKit API key when using the live widget.
3. Run migrations: execute `uv run python -m orcheo.storage.init_chatkit_db` (a lightweight bootstrap script) to create the SQLite tables.
4. Start backend: `uv run uvicorn orcheo.main:app --reload`.
5. Launch demo: open `examples/chatkit-orcheo.html` in a static file server (`python -m http.server`) and ensure the workflow selector loads via `/api/chatkit/workflows`.
6. Verify streaming: use browser dev tools to confirm SSE connections remain open and events carry incremental tokens.

### LangGraph Workflow Adapter
- Create a new example graph (`examples/chatkit_workflow_graph.py`) that demonstrates:
- State shape: `{"messages": list, "workflow_id": str, "metadata": dict, "message_id": str}` to track deduplication and ordering.
  - Nodes: `UserInput` (ingest), `Router` (branch on workflow ID), `ScriptedResponse` (returns templated replies), `ActionGenerator` (injects ChatKit actions for follow-up choices).
- Execution: triggered per message, returning ChatKit-compatible JSON with `role`, `content`, `message_id`, and optional `actions` describing buttons/forms. The adapter validates that loaded workflows declare ChatKit compatibility metadata; incompatible graphs short-circuit with a descriptive error surfaced to the frontend.
- Include docstrings referencing ChatKit docs for future contributors, and align naming with `examples/vanilla_langgraph.py` to ease onboarding.
- Provide instructions for uploading the graph to the Orcheo backend (e.g., via CLI or admin UI) in the final implementation phase, and add a version field so future revisions can be coordinated with ChatKit expectations.

### SQLite Chat Store
- Schema Outline:
  - `chat_sessions(id, workflow_id, created_at, updated_at)`
  - `chat_threads(id, session_id, title, created_at)` (optional grouping if we reuse sessions).
- `chat_messages(id, thread_id, role, content, payload, created_at)`
- `chat_files(id, message_id, filename, mime_type, path, size_bytes)`
- Use migration-friendly patterns (e.g., SQLAlchemy ORM or Alembic migrations) even if initial prototype seeds the schema programmatically.
- Provide repository functions for:
  - `create_session(workflow_id)`
  - `append_message(thread_id, role, content, payload)`
  - `list_messages(thread_id)`
  - `store_file(metadata)` and `get_file(message_id)`
- Ensure all file blobs live on disk (under a configurable path defaulting to `data/chatkit_uploads/`) with SQLite storing metadata only. Introduce a background janitor task (async job on startup) that deletes orphaned files when sessions are purged to prevent storage leaks.
- Document how to swap the repository to Postgres in future milestones once concurrency requirements increase.

## Implementation Plan
1. **Backend Preparation**
   - Scaffold `/api/chatkit` router, Pydantic models for request/response bodies, and SSE streaming utilities.
   - Implement SQLite repository and wire into dependency injection / service layer.
   - Build LangGraph runner wrapper that accepts workflow ID, loads the uploaded graph, and executes it per message.

2. **Frontend Updates**
   - Extend `examples/chatkit-orcheo.html` with workflow dropdown, ChatKit theme/action hooks, and fetch helpers.
   - Document local setup steps (start backend, run HTML file, configure workflow ID).

3. **Testing & Validation**
   - **Unit tests**: cover repository functions (including failure retries), API routes (422 validation, 409 concurrency, 500 storage errors), and SSE event ordering using mocked LangGraph responses.
   - **Integration tests**: simulate a full ChatKit session by creating a session, posting messages with attachments, verifying streamed tokens, and asserting idempotency when resending a `message_id`.
   - **Contract tests**: fixture-based tests that mock ChatKit webhooks to ensure payload compatibility across SDK versions.
   - **Manual QA checklist**: verify workflow selector fallback, SSE reconnect banner, file upload validation errors, and cleanup scripts.

4. **Operational Follow-Up**
   - Evaluate persistence performance; plan migration to managed database if needed.
   - Harden authentication and rate limiting in subsequent milestones.

## Open Questions
- Should we reuse existing workflow registry endpoints or introduce a ChatKit-specific subset for now?
- Do we want to use WebSockets instead of SSE for streaming? (Depends on ChatKit's preferred transport.)
- How will file uploads be authenticated/virus scanned before production rollout?

## References
- [ChatKit overview](https://platform.openai.com/docs/guides/chatkit)
- [ChatKit theming](https://platform.openai.com/docs/guides/chatkit-themes)
- [ChatKit actions](https://platform.openai.com/docs/guides/chatkit-actions)
- [Custom ChatKit integrations](https://platform.openai.com/docs/guides/custom-chatkit)
