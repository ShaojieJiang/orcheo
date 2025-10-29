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
- **Workflow Selector UI**: Add a `<select>` element populated from `/api/chatkit/workflows` so the operator can choose an Orcheo workflow. Fall back to client-side JSON seed for local demos.
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

- Responses follow JSON API conventions with `data` envelopes, while streaming uses server-sent events (SSE) to align with ChatKit's streaming mode.
- Authentication is deferred; local development uses unsecured endpoints behind localhost.

### LangGraph Workflow Adapter
- Create a new example graph (`examples/chatkit_workflow_graph.py`) that demonstrates:
  - State shape: `{"messages": list, "workflow_id": str, "metadata": dict}`.
  - Nodes: `UserInput` (ingest), `Router` (branch on workflow ID), `ScriptedResponse` (returns templated replies), `ActionGenerator` (injects ChatKit actions for follow-up choices).
  - Execution: triggered per message, returning ChatKit-compatible JSON with `role`, `content`, and optional `actions` describing buttons/forms.
- Include docstrings referencing ChatKit docs for future contributors, and align naming with `examples/vanilla_langgraph.py` to ease onboarding.
- Provide instructions for uploading the graph to the Orcheo backend (e.g., via CLI or admin UI) in the final implementation phase.

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
- Ensure all file blobs live on disk (under `data/chatkit_uploads/`) with SQLite storing metadata only.

## Implementation Plan
1. **Backend Preparation**
   - Scaffold `/api/chatkit` router, Pydantic models for request/response bodies, and SSE streaming utilities.
   - Implement SQLite repository and wire into dependency injection / service layer.
   - Build LangGraph runner wrapper that accepts workflow ID, loads the uploaded graph, and executes it per message.

2. **Frontend Updates**
   - Extend `examples/chatkit-orcheo.html` with workflow dropdown, ChatKit theme/action hooks, and fetch helpers.
   - Document local setup steps (start backend, run HTML file, configure workflow ID).

3. **Testing & Validation**
   - Unit tests for repository functions and API routes (FastAPI test client).
   - Integration test simulating ChatKit session: create session, send message, receive scripted response.
   - Manual QA checklist for the HTML demo.

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
