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

2. **Backend endpoint (`POST /api/chatkit/events`)**
   - Receives ChatKit action payloads.
   - Validates ChatKit signature or shared secret (configuration stub for now).
   - Loads/creates the chat session record (SQLite).
   - Dispatches the request to the scripted LangGraph workflow executor and returns the response in ChatKit format.

3. **LangGraph workflow stub**
   - Located at `examples/chatkit_langgraph.py` (new file).
   - Uses the same structure as `examples/vanilla_langgraph.py` but hardcodes deterministic responses for key conversation branches (greeting, workflow status, fallback).
   - Exposes a helper `run_chatkit_workflow(session_state, user_message)` to simulate execution.

4. **SQLite persistence layer**
   - New module (e.g., `src/orcheo/chatkit/storage.py`) to manage SQLite connections.
   - Tables:
     - `chat_sessions(id TEXT PRIMARY KEY, workflow_id TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)`
     - `chat_messages(id TEXT PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, created_at TIMESTAMP)`
     - `chat_files(id TEXT PRIMARY KEY, session_id TEXT, filename TEXT, media_type TEXT, path TEXT, created_at TIMESTAMP)`
   - Uses `sqlite3` with connection pooling via FastAPI lifespan event or context manager.

### Data Flow
1. User opens the demo page and selects an Orcheo workflow.
2. ChatKit widget initializes with the selected workflow token and obtains session metadata from Orcheo.
3. When the user sends a message or uploads a file, ChatKit sends an action payload to `/api/chatkit/events`.
4. The backend endpoint logs the request, persists the new message/file, and calls the LangGraph stub.
5. The LangGraph stub returns scripted assistant responses and optional actions (e.g., follow-up questions).
6. Backend persists assistant messages, packages the response per ChatKit schema, and returns it to the widget.
7. Widget renders the response and continues the conversation loop until ended.

## Backend API Contract
- **Route:** `POST /api/chatkit/events`
- **Request:** JSON payload from ChatKit containing `session`, `message`, `files`, `action`.
- **Response:** JSON object with `messages`, `actions`, optional `session_update`.
- **Headers:** Support `Authorization: Bearer <chatkit_api_key>` (configurable) and `X-ChatKit-Signature` (future verification hook).
- **Error Handling:** Return `400` for validation errors, `401` for auth failures, `500` for unexpected exceptions with structured error JSON.

## Frontend Requirements (`examples/chatkit-orcheo.html`)
- Load ChatKit SDK and theme assets from CDN.
- Add a workflow selector `<select id="workflow-picker">` with placeholder options until dynamic fetch is ready.
- Initialize ChatKit with `serverUrl` pointing to `/api/chatkit/events` and include selected workflow in `metadata`.
- Bind selector change events to reset ChatKit session (new session ID, clears transcripts).
- Display basic status indicators (workflow name, connection state) for manual testing.

## SQLite Storage Plan
- Create a new SQLite database file under `data/chatkit.db` (configurable path via env var `CHATKIT_DB_URL`).
- Provide migration bootstrap script to create tables if missing (executed on startup).
- Use parameterized queries and ensure indices on `session_id` for message/file tables.
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
- Introduce settings keys in `src/orcheo/config.py` for `CHATKIT_API_KEY`, `CHATKIT_DB_URL`, and toggle for signature verification.
- Ensure sensitive configs come from environment variables.
- Document how to rotate API keys and configure CORS.

## Testing Strategy
- **Unit tests:**
  - Storage layer CRUD using temporary SQLite database.
  - LangGraph stub path selection logic.
- **Integration tests:**
  - FastAPI TestClient hitting `/api/chatkit/events` with sample payloads.
  - Frontend smoke test using Playwright (future stretch goal).
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

## Task Breakdown
1. Storage & configuration scaffolding.
2. LangGraph stub implementation and packaging.
3. Backend endpoint and routing integration.
4. Frontend demo wiring and manual test plan.
5. Follow-up hardening (auth, cleanup jobs).

