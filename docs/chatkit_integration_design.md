# ChatKit Integration Design

## Overview
This document outlines the plan for integrating OpenAI ChatKit with Orcheo so ChatKit sessions can drive Orcheo workflows through a backend handoff. The integration adds a ChatKit-enabled demo experience, a backend endpoint for ChatKit webhooks, SQLite-backed storage for conversation artifacts, and a reference LangGraph workflow that will eventually power the runtime.

## Goals
- Connect the ChatKit widget in `examples/chatkit-orcheo.html` to Orcheo so chat actions hit a custom endpoint.
- Allow users to select an Orcheo workflow (initially a scripted LangGraph graph) that handles the conversation session.
- Implement a backend endpoint under the Orcheo FastAPI app that conforms to ChatKit’s server API contract.
- Persist chat threads, files, and workflow selections to SQLite for durability and future analytics.
- Provide a vanilla LangGraph graph with scripted outputs that demonstrates the end-to-end integration and is ready for backend upload.

## Non-Goals
- Shipping a production-ready workflow runtime or multi-tenant authentication.
- Implementing real Orcheo workflow execution; the first iteration uses a scripted LangGraph graph stub.
- Replacing existing persistence layers outside of chat/thread/file storage.

## References
- [ChatKit integration guide](https://platform.openai.com/docs/guides/chatkit)
- [ChatKit themes](https://platform.openai.com/docs/guides/chatkit-themes)
- [ChatKit actions](https://platform.openai.com/docs/guides/chatkit-actions)
- [Custom ChatKit server](https://platform.openai.com/docs/guides/custom-chatkit)
- Internal reference: `examples/vanilla_langgraph.py`

## Architecture
### Components
1. **Frontend demo (`examples/chatkit-orcheo.html`)**
   - Embeds the ChatKit JavaScript SDK and theme assets.
   - Adds a workflow selector populated via `/api/workflows` (mock or static JSON until backend listing exists).
   - Binds ChatKit actions (send message, upload file, start/end conversation) to Orcheo’s ChatKit endpoint.
   - Persists the selected workflow identifier in session storage and sends it with each ChatKit request.

2. **Backend endpoints (reuse existing FastAPI routes)**
   - `POST /api/chatkit/session` already issues a client secret. Extend it to surface workflow-aware metadata (display name, theme hints) the widget can render without additional calls.
   - `POST /api/chatkit/workflows/{workflow_id}/trigger` already dispatches workflow runs. Add a ChatKit adapter that translates ChatKit action payloads into the repository-friendly payload before delegating to the existing handler.
   - Share signature/secret validation utilities and storage helpers between the endpoints.

3. **LangGraph workflow stub**
   - Located at `examples/chatkit_langgraph.py` (new file).
   - Uses the same structure as `examples/vanilla_langgraph.py` but hardcodes deterministic responses for key conversation branches (greeting, workflow status, fallback).
   - Exposes a helper `run_chatkit_workflow(session_state, user_message)` to simulate execution.

4. **SQLite persistence layer**
   - Extend the existing repository pattern (`orcheo_backend/app/repository_sqlite.py`) with ChatKit-specific data access objects instead of opening bespoke connections.
   - Tables:
     - `chat_sessions(id TEXT PRIMARY KEY, workflow_id TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)`
     - `chat_messages(id TEXT PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, created_at TIMESTAMP)`
     - `chat_files(id TEXT PRIMARY KEY, session_id TEXT, filename TEXT, media_type TEXT, path TEXT, created_at TIMESTAMP)`
   - Reuse the shared SQLite engine/session lifecycle so the implementation can swap to PostgreSQL when `RepositoryBackend` changes.

### Data Flow
1. User opens the demo page and selects an Orcheo workflow.
2. ChatKit widget initializes with the selected workflow token and obtains session metadata from Orcheo.
3. When the user sends a message or uploads a file, ChatKit posts an action payload to `/api/chatkit/workflows/{workflow_id}/trigger` with the current session metadata.
4. The backend adapter logs the request, persists the new message/file, and calls the LangGraph stub before delegating to the repository to create a workflow run.
5. The LangGraph stub returns scripted assistant responses and optional actions (e.g., follow-up questions).
6. Backend persists assistant messages, packages the response per ChatKit schema, and returns it to the widget.
7. Widget renders the response and continues the conversation loop until ended.

## Backend API Contract
- **Session issuance (`POST /api/chatkit/session`):**
  - **Request:** Reuse `ChatKitSessionRequest` with optional `workflow_id`.
  - **Response:** Extend `ChatKitSessionResponse` to optionally include workflow display metadata so the frontend can render contextual hints without additional lookups.
  - **Headers:** Continue supporting Bearer auth via `CHATKIT_CLIENT_SECRET` (global or workflow-scoped) while keeping it optional for the demo.

- **Workflow trigger (`POST /api/chatkit/workflows/{workflow_id}/trigger`):**
  - **Request:** Accept `ChatKitWorkflowTriggerRequest` but allow an embedded `chatkit_payload` block that mirrors ChatKit action bodies (messages, files, tool invocations). The adapter will normalize this into the existing repository payload.
  - **Response:** Return the existing `WorkflowRun` plus a derived ChatKit message envelope so the frontend can update the transcript immediately.
  - **Headers:** Support `Authorization: Bearer <chatkit_client_secret>` and introduce optional signature validation via `X-ChatKit-Signature` guarded behind a feature flag.

- **Error Handling:** Reuse `_raise_not_found`, `_raise_conflict`, and FastAPI HTTPException helpers while wrapping adapter-level errors in ChatKit-compliant error payloads.

## Frontend Requirements (`examples/chatkit-orcheo.html`)
- Load ChatKit SDK and theme assets from CDN.
- Add a workflow selector `<select id="workflow-picker">` with placeholder options until dynamic fetch is ready.
- Initialize ChatKit by first calling `/api/chatkit/session` to obtain a client secret, then wiring ChatKit actions so they `fetch` `/api/chatkit/workflows/{workflow_id}/trigger` with the current session metadata.
- Bind selector change events to reset ChatKit session (new session ID, clears transcripts).
- Display basic status indicators (workflow name, connection state) for manual testing.

## SQLite Storage Plan
- Create a new SQLite database file under `data/chatkit.db` (configurable through `CHATKIT_DB_PATH` on `AppSettings`).
- Provide migration bootstrap script to create tables if missing (executed on startup) and wire it into the repository initialization lifecycle.
- Use parameterized queries and ensure indices on `session_id` for message/file tables by following the repository helper conventions.
- Implement helper methods:
  - `get_or_create_session(session_id, workflow_id)`
  - `append_message(session_id, role, content)`
  - `list_messages(session_id)`
  - `store_file(session_id, upload_metadata)`

## LangGraph Stub Design
- Based on `examples/vanilla_langgraph.py` structure with `StateGraph` and node handlers.
- Graph nodes:
  - `ingest_user_message`: adds the user turn to state, performs simple intent detection (keyword match) to pick scripted branch.
  - `branch_router`: routes to `greeting`, `status_report`, or `fallback` nodes.
  - `greeting`: returns canned welcome plus workflow-specific hints.
  - `status_report`: simulates checking workflow progress and returns placeholder metrics.
  - `fallback`: echoes that the question will be handled later.
- Output should align with ChatKit message schema (text plus optional buttons for follow-up actions).
- Provide CLI entry point for manual testing: `python examples/chatkit_langgraph.py --simulate` prints a sample transcript.

## Security & Configuration
- Extend `_DEFAULTS` and `AppSettings` in `src/orcheo/config.py` with:
  - `CHATKIT_CLIENT_SECRET`: optional string used for Bearer auth (global default, with workflow-specific overrides).
  - `CHATKIT_DB_PATH`: filesystem path to the SQLite file (defaults to `data/chatkit.db`).
  - `CHATKIT_SIGNATURE_VERIFICATION`: boolean flag controlling whether `X-ChatKit-Signature` is enforced (defaults to `True`).
- Ensure sensitive configs continue to flow from environment variables via the existing settings loader.
- Document how to rotate secrets and configure CORS for the ChatKit demo.

## Testing Strategy
- **Unit tests:**
  - Storage layer CRUD using temporary SQLite database.
  - LangGraph stub path selection logic.
- **Integration tests:**
  - FastAPI TestClient covering `/api/chatkit/session` and `/api/chatkit/workflows/{workflow_id}/trigger` with sample ChatKit payloads.
  - Frontend smoke test using Playwright (future stretch goal).
- **Test scaffolding:** Leverage existing backend testing patterns in `tests/backend/` (e.g., `test_app_init.py`) for fixtures and HTTP helpers.
- **Manual QA:**
  - Run FastAPI dev server, open `examples/chatkit-orcheo.html`, verify message loop and workflow selection.

## Rollout Plan
1. Implement storage layer and LangGraph stub behind feature flag.
2. Add backend endpoint with logging and structured responses.
3. Wire frontend demo and manual QA.
4. Harden security (signature validation, auth checks).
5. Document usage in README and docs.

## Open Questions
- Should workflows be listed dynamically from Orcheo API or hardcoded? (Initial plan: static list with TODO.)
- What retention policy should we apply to stored transcripts and files? (Default: manual cleanup until policy defined.)
- When scaling beyond SQLite, should ChatKit storage share the primary repository backend (e.g., PostgreSQL)? (The DAO pattern above enables swapping once Milestone 4 storage work lands.)

## Task Breakdown
1. Storage & configuration scaffolding.
2. LangGraph stub implementation and packaging.
3. Backend endpoint and routing integration.
4. Frontend demo wiring and manual test plan.
5. Follow-up hardening (auth, cleanup jobs).

