# ChatKit Integration Design

## Overview
This document proposes the design for integrating OpenAI ChatKit into Orcheo so that end users can exercise Orcheo workflows through a ChatKit-powered chat experience. The implementation intentionally focuses on scaffolding: wiring the frontend sample, defining backend contract surfaces, capturing workflow orchestration, and specifying persistence. No production code changes are included yet; this plan will guide subsequent delivery work.

## Goals & Non-Goals
### Goals
- Enable the `examples/chatkit-orcheo.html` demo to drive conversations against Orcheo via a ChatKit widget.
- Expose a FastAPI endpoint inside Orcheo that conforms to ChatKit's server expectations and dispatches requests to a selected workflow.
- Prepare a vanilla LangGraph workflow script with deterministic (scripted) outputs that can be published to Orcheo for the integration.
- Specify a SQLite-backed persistence layer for chat files, threads, and workflow session state.

### Non-Goals
- Building a production-grade UX; the scope is limited to the example HTML and backend scaffolding.
- Implementing streaming token relay or advanced ChatKit features (themes, custom actions beyond workflow selection).
- Shipping full workflow runtime logic—the LangGraph graph will return stubbed responses for now.

## Reference Documentation
- [ChatKit Overview](https://platform.openai.com/docs/guides/chatkit)
- [ChatKit Themes](https://platform.openai.com/docs/guides/chatkit-themes)
- [ChatKit Actions](https://platform.openai.com/docs/guides/chatkit-actions)
- [Custom ChatKit Backends](https://platform.openai.com/docs/guides/custom-chatkit)

## Architecture Summary
```
+------------------------+        +---------------------------+        +------------------------+
| chatkit-orcheo.html    |        | Orcheo FastAPI Backend   |        | LangGraph Workflow     |
| - ChatKit Widget       |  --->  | - /api/chatkit endpoint  |  --->  | - Vanilla scripted run |
| - Workflow selector    | <---   | - SQLite persistence     | <---   | - Session state events |
+------------------------+        +---------------------------+        +------------------------+
```
1. The example HTML embeds ChatKit, configures actions (submit, upload), and surfaces an Orcheo workflow dropdown.
2. When the user starts a session, the widget includes the selected workflow ID in conversation metadata.
3. ChatKit requests hit the new FastAPI endpoint. The backend stores/retrieves thread artifacts in SQLite, resolves the workflow, and relays prompts to the LangGraph runner.
4. The prepared LangGraph graph produces scripted responses, emulating workflow behavior until real logic is implemented.

## Frontend (examples/chatkit-orcheo.html)
1. **ChatKit Initialization**
   - Use `ChatKit.init` with our custom endpoint URL (e.g., `/api/chatkit`).
   - Provide theme overrides minimal: align with Orcheo palette but keep defaults for simplicity.
2. **Workflow Selection Component**
   - Add a `<select>` populated by `GET /api/workflows?source=chatkit-demo` or a static list for now.
   - On selection, store workflow ID in `sessionStorage` and pass it to ChatKit's context via `metadata`.
3. **Custom Actions Hook**
   - Implement a ChatKit action `select_workflow` invoked before session creation; ensure actions update the widget state.
   - Provide UI feedback when no workflow is selected; disable send button until set.
4. **File Upload Handling**
   - Enable ChatKit's file attachments; rely on backend to persist metadata in SQLite.

## Backend Endpoint Design
- **Route**: `POST /api/chatkit/{thread_id}/events`
  - Follows ChatKit webhook pattern for message events and tool calls.
- **Payload Handling**
  - Validate signature/headers (future work).
  - Persist inbound event (message, file, action) into SQLite tables: `chat_threads`, `chat_messages`, `chat_files`.
  - Extract `workflow_id` from event metadata; default to fallback stub if missing.
- **Processing Flow**
  1. Load or create chat thread record.
  2. If event contains files, store file metadata and blob path (filesystem storage under `data/chatkit/`).
  3. Invoke LangGraph execution helper with user message and thread state.
  4. Capture workflow response, persist as assistant message, and respond to ChatKit with structured payload.
- **Response Schema**
  - Return `200 OK` with `messages` array conforming to ChatKit's `events` response contract, including message IDs and statuses.

## LangGraph Workflow (vanilla example)
- Create `examples/langgraph_chatkit_demo.py` (name TBD) following `examples/vanilla_langgraph.py` patterns.
- Structure
  - Nodes: `Start`, `ScriptedResponder`, `End`.
  - The responder node returns canned responses based on simple keyword matching (e.g., "status", "deploy"), else uses default message.
  - Provide metadata fields to surface workflow name and supported actions.
- Execution
  - Provide a helper `run_chatkit_demo(message: str, context: dict) -> dict` returning message text and optional follow-up actions.
  - Include instructions for uploading the graph into Orcheo backend using existing CLI/API scaffolding.

## SQLite Persistence
- **Schema**
  - `chat_threads (id TEXT PRIMARY KEY, workflow_id TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)`
  - `chat_messages (id TEXT PRIMARY KEY, thread_id TEXT, role TEXT, content TEXT, created_at TIMESTAMP)`
  - `chat_files (id TEXT PRIMARY KEY, thread_id TEXT, filename TEXT, mime_type TEXT, storage_path TEXT, created_at TIMESTAMP)`
- **Lifecycle Hooks**
  - Create tables on startup via Alembic-like migration or manual bootstrap function invoked during FastAPI startup.
  - Use connection pooling via `sqlmodel` or `sqlite3` with thread-safe access (FastAPI dependency injection).
- **Retention & Cleanup**
  - Provide background task to prune stale threads (e.g., older than 30 days) and delete associated files.

## Security & Compliance Considerations
- Enforce max attachment size (align with ChatKit defaults) and sanitize file names before storage.
- Plan for future authentication (API keys per session) and request signature verification (per ChatKit docs).
- Ensure logs omit message content unless debug mode enabled.

## Testing Strategy
- Unit tests for SQLite repository functions (CRUD operations).
- FastAPI route tests using `TestClient` to verify ChatKit event ingestion and response formation.
- Frontend smoke test: open HTML file, ensure workflow dropdown populates and session metadata includes the selected ID.
- LangGraph script tests verifying deterministic responses for sample inputs.

## Rollout Plan
1. Implement backend endpoint and persistence enabled by default.
2. Add LangGraph demo script and register workflow in local Orcheo instance.
3. Update example HTML and provide README snippet on how to run the demo.
4. Conduct end-to-end manual test: start FastAPI, open HTML file, run sample conversation.
5. Iterate on telemetry and error handling before promoting beyond demo status.

## Open Questions
- Should workflow selection reflect authenticated user context or stay anonymous?
- Do we need multi-tenant storage isolation in SQLite, or is a single database sufficient for the demo?
- How will we migrate stored threads/files if we move to Postgres in production?
