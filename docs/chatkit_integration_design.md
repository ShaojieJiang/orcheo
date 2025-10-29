# ChatKit Integration Design

## 1. Summary
- **Purpose**: Define the plan for connecting OpenAI ChatKit to Orcheo so conversations trigger backend workflows with persisted chat state.
- **Scope**: Frontend wiring in `examples/chatkit-orcheo.html`, a new ChatKit webhook endpoint inside the Orcheo FastAPI app, orchestration of ChatKit actions into Orcheo workflows via LangGraph, and SQLite-backed storage for conversation artifacts.
- **Status**: Draft for implementation; no code changes committed yet.

## 2. Objectives & Success Criteria
| Objective | Success Criteria |
| --- | --- |
| ChatKit actions call Orcheo | Actions initiated in the widget result in HTTP requests to an Orcheo endpoint with workflow context, returning structured responses that ChatKit renders. |
| Workflow selection | The HTML example lets operators choose an Orcheo workflow (pre-registered or demo) before starting the session; selection persists for the session. |
| Backend orchestration | The new endpoint validates payloads, resolves the selected workflow, and invokes a LangGraph-powered execution stub. |
| Data persistence | Chat messages, threads, and file metadata persist to SQLite with migration + cleanup utilities. |
| Extensibility | Design supports swapping the scripted LangGraph stub with real orchestrations without altering ChatKit contract. |

## 3. Functional Requirements
1. **ChatKit example wiring**
   - Embed ChatKit per OpenAI guidance with custom `actions`, `theme`, and `onSubmit` handlers.
   - Provide a workflow dropdown (populated from a static list or fetched via `/api/workflows`) and disable the chat input until a workflow is selected.
   - Forward ChatKit action payloads to `/api/chatkit/sessions/{session_id}/events` with headers for session + workflow.
2. **Backend endpoint**
   - Implement `POST /api/chatkit/sessions/{session_id}/events` in FastAPI.
   - Validate ChatKit signature (placeholder config), enforce workflow selection, persist inbound payloads, and dispatch to LangGraph.
   - Return ChatKit-compatible responses (`{ "content": [...], "status": "completed" }`).
3. **LangGraph stub workflow**
   - Create `examples/langgraph/chatkit_demo.py` (name TBD) that builds a vanilla LangGraph similar to `examples/vanilla_langgraph.py`.
   - Provide scripted deterministic nodes (e.g., greeting, workflow summary, fallback) to emulate responses until real workflows exist.
   - Expose helper to run graph synchronously from backend.
4. **SQLite storage**
   - Add SQLite DB (e.g., `data/chatkit.sqlite3`) with tables: `sessions`, `threads`, `messages`, `files`.
   - Provide data access layer with migrations, connection pooling, and TTL/archival utilities.
   - Ensure backend endpoint reads/writes via DAL before invoking LangGraph.

## 4. Non-Functional Requirements
- **Security**: Support signature verification, workflow access checks, and configurable rate limits.
- **Observability**: Log ChatKit events, track workflow execution metadata, and emit metrics (count per action, failure rates).
- **Reliability**: Handle retries/idempotency with `event_id` tracking, ensure database transactions wrap each request.
- **Maintainability**: Encapsulate ChatKit logic in dedicated module `orcheo.chatkit` with tests and documentation.

## 5. Architectural Overview
### 5.1 Component Diagram
```
ChatKit Widget (examples/chatkit-orcheo.html)
  └── fetch() -> Orcheo FastAPI (/api/chatkit/...)
          ├── ChatKitService (validation + persistence)
          ├── ChatStore (SQLite DAL)
          └── LangGraphRunner (executes chat workflow)
LangGraph Graph (examples/langgraph/chatkit_demo.py)
  └── scripted nodes -> response payloads
```

### 5.2 Request Flow
1. User selects workflow in the HTML dropdown; widget stores `workflow_id` in `sessionStorage`.
2. ChatKit action fires `onSubmit` → `fetch('/api/chatkit/...', { body: { action, messages, files } })` with headers for `X-Orcheo-Workflow-ID` and `X-ChatKit-Session`.
3. FastAPI endpoint:
   - Authenticates (future), validates JSON schema, logs event.
   - Upserts session/thread, persists messages/files to SQLite.
   - Calls `LangGraphRunner.run(workflow_id, payload)`.
4. `LangGraphRunner` loads configured LangGraph (scripted) or uses Orcheo workflow registry.
5. Response mapped to ChatKit format and returned to widget for rendering.

### 5.3 Module Placement
- `src/orcheo/chatkit/router.py`: FastAPI router + dependency wiring.
- `src/orcheo/chatkit/service.py`: Business logic (validation, persistence, orchestration).
- `src/orcheo/chatkit/store.py`: SQLite DAL using `sqlalchemy` or `sqlite3` with async wrappers.
- `examples/chatkit-orcheo.html`: Frontend integration + UX tweaks.
- `examples/langgraph/chatkit_demo.py`: LangGraph stub for ChatKit.
- `tests/chatkit/`: Unit/integration tests for DAL, service, endpoint, and HTML snapshot if needed.

## 6. Data Model
| Table | Columns | Notes |
| --- | --- | --- |
| `sessions` | `id (PK)`, `workflow_id`, `created_at`, `updated_at`, `status` | Tracks ChatKit sessions and associated workflow. |
| `threads` | `id (PK)`, `session_id (FK)`, `chatkit_thread_id`, `created_at`, `updated_at` | Allows multi-thread or parallel conversations. |
| `messages` | `id (PK)`, `thread_id (FK)`, `direction (enum:user,assistant,system)`, `content (JSON)`, `metadata (JSON)`, `event_id`, `created_at` | Persists content + deduplicates via `event_id`. |
| `files` | `id (PK)`, `message_id (FK)`, `file_name`, `mime_type`, `url`, `size_bytes`, `created_at` | Metadata only; storage delegated to existing blob service when available. |

- Implement migrations using Orcheo's existing tooling (Alembic? If none, add simple SQL bootstrap executed at startup).
- Provide `ChatStore` methods: `create_session`, `update_session_workflow`, `add_message`, `attach_files`, `get_thread_history`, `mark_event_processed`.

## 7. LangGraph Demo Workflow
- Node graph: `InputNode` → `WorkflowSummaryNode` → `ClosingNode`.
- Each node returns scripted text referencing the chosen workflow and any user attachments.
- Provide `def build_chatkit_demo_graph(): ...` returning `Graph` plus `run_graph(messages: list[Message]) -> list[Message]` helper.
- Document how to replace with real Orcheo workflows (load by workflow_id, use orchestrator service).

## 8. Implementation Plan
1. **Scaffold backend module**
   - Add router/service/store skeletons, configure FastAPI include.
   - Create SQLite DB initialization (config-driven path, ensure directories exist).
2. **Implement DAL**
   - Define schema migrations, connection pooling, CRUD helpers, tests.
3. **Service logic**
   - Validate ChatKit payload (use Pydantic models), orchestrate persistence + LangGraph call, map responses.
4. **LangGraph stub**
   - Build sample graph + runner, ensure importable by service.
   - Provide CLI/test harness (optional) for manual verification.
5. **Frontend wiring**
   - Update HTML example with workflow selector, event handling, error states, theming.
6. **Documentation + tests**
   - Add README section for ChatKit usage, update docs to link design.
   - Create unit/integration tests; add manual test checklist.

## 9. Testing Strategy
- **Unit tests**: DAL operations (insert/select), service response mapping, LangGraph stub outputs.
- **Integration tests**: FastAPI client posting ChatKit events verifying persistence + stub response.
- **Frontend smoke**: Playwright or manual instructions to verify workflow selection gating and API calls.
- **Resilience tests**: Replaying same `event_id` to ensure idempotent behavior.

## 10. Risks & Mitigations
| Risk | Impact | Mitigation |
| --- | --- | --- |
| SQLite contention under load | High | Use WAL mode, connection pooling per request, consider upgrade path to Postgres. |
| ChatKit API changes | Medium | Encapsulate payload models, version endpoints, monitor OpenAI changelog. |
| Workflow registry mismatch | Medium | Provide stub registry mapping + config; fail fast with descriptive errors. |
| File storage scaling | Medium | Limit attachments, store metadata only, integrate with Orcheo blob service later. |

## 11. Open Questions
1. Which auth mechanism (API keys vs session cookies) should gate ChatKit endpoint?
2. Should the workflow dropdown fetch dynamic options or rely on static JSON in the example?
3. Where should ChatKit theme tokens live for reuse across apps?

## 12. References
- [OpenAI ChatKit Guide](https://platform.openai.com/docs/guides/chatkit)
- [ChatKit Themes](https://platform.openai.com/docs/guides/chatkit-themes)
- [ChatKit Actions](https://platform.openai.com/docs/guides/chatkit-actions)
- [Custom ChatKit Endpoints](https://platform.openai.com/docs/guides/custom-chatkit)
- `examples/vanilla_langgraph.py`
