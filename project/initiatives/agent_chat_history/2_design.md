# Design Document

## For Agent Chat History via LangGraph Store

- **Version:** 0.1
- **Author:** Codex
- **Owner:** Shaojie Jiang
- **Date:** 2026-02-26
- **Status:** Draft

---

## Overview

This design adds a dedicated LangGraph store backend to Orcheo runtime and wires it into graph compilation alongside the existing checkpointer. The store supports SQLite and Postgres, mirroring current persistence backend options used in backend execution paths.

On top of that, `AgentNode` gains an opt-in mode to consume chat history from graph store. When enabled, the node resolves a keyed conversation identity, reads only the latest window required for inference (`max_messages`), and appends new user/assistant turns to persisted full history. This is intended for bot backends where each callback may not include full prior context.

## Components

- **Config Layer (`orcheo.config`)**
  - Adds graph store backend and path fields (plus validation) parallel to checkpoint backend.
  - Ensures Postgres DSN requirements are enforced when graph store backend is `postgres`.

- **Persistence Factory (`src/orcheo/persistence.py`)**
  - Adds `create_graph_store(settings)` async context manager.
  - Uses LangGraph `AsyncSqliteStore` or `AsyncPostgresStore`.
  - Calls `store.setup()` before use.

- **Backend Execution Wiring (`apps/backend/...`)**
  - Extends compile call sites to `graph.compile(checkpointer=..., store=...)`.
  - Applies to workflow execution, triggers, worker tasks, and ChatKit workflow executor.

- **AgentNode (`src/orcheo/nodes/ai.py`)**
  - Adds opt-in fields controlling graph-store chat history behavior and keying.
  - Reads only a recent tail window before run, merges with current messages, trims to `max_messages` for inference, then appends newly observed turns to full history.

## Request Flows

### Flow 1: Compile graph with checkpointer + store

1. Backend loads runtime settings.
2. Backend opens checkpointer context (`create_checkpointer(settings)`).
3. Backend opens graph store context (`create_graph_store(settings)`).
4. Backend compiles with both: `graph.compile(checkpointer=checkpointer, store=store)`.
5. Compiled graph execution proceeds unchanged for nodes not using store.

### Flow 2: AgentNode run with graph-store history enabled

1. `AgentNode.run(...)` receives state and runtime config.
2. Node resolves message candidates from state/input and gathers key candidates from config and parsed payload fields (literal values or Orcheo templates like `{{results.some_node.some_field}}`).
3. Node resolves namespace/key using precedence (explicit key override, channel-derived stable key, then `thread_id` fallback).
4. Node loads conversation metadata and fetches only the latest history tail required for inference.
5. Node normalizes and merges `history_tail + current_thread_messages`.
6. Node trims to latest `max_messages` and invokes agent.
7. Node appends newly observed user/assistant messages to full history and updates metadata (best effort with retry on version conflict).

### Flow 3: AgentNode run with history disabled or unavailable

1. Toggle is `False`, or no conversation key can be resolved, or store unavailable.
2. Node executes current in-memory message path only.
3. No graph store read/write performed.

## API Contracts

### Runtime settings (proposed)

```env
ORCHEO_GRAPH_STORE_BACKEND=sqlite|postgres
ORCHEO_GRAPH_STORE_SQLITE_PATH=~/.orcheo/graph_store.sqlite
# Uses ORCHEO_POSTGRES_DSN and shared pool settings when backend=postgres
```

### Internal persistence API

```python
@asynccontextmanager
async def create_graph_store(settings: Dynaconf) -> AsyncIterator[Any]:
    ...
```

### AgentNode fields (proposed)

```python
use_graph_chat_history: bool = False
history_namespace: list[str] = ["agent_chat_history"]
# Supports literal values (for example "shared-room") or Orcheo templates.
history_key_template: str = "{{conversation_key}}"
history_key_candidates: list[str] = [
    "{{results.resolve_history_key.session_key}}",
    "{{configurable.history_key}}",
    "{{inputs.history_key}}",
    "telegram:{{results.telegram_events_parser.chat_id}}",
    "wecom_cs:{{results.wecom_cs_sync.open_kf_id}}:{{results.wecom_cs_sync.external_userid}}",
    "wecom_aibot:{{results.wecom_ai_bot_events_parser.chat_type}}:{{results.wecom_ai_bot_events_parser.user}}",
    "wecom_dm:{{results.wecom_events_parser.user}}",
    "{{thread_id}}",
]
history_meta_key_suffix: str = "__meta__"
history_chunk_size: int = 200
history_value_field: str = "content"
```

## Data Models / Schemas

### Graph store metadata item

```json
{
  "conversation_key": "telegram:123456789",
  "last_seq": 4231,
  "chunk_size": 200,
  "latest_chunk_key": "chunk:000021",
  "updated_at": "2026-02-26T20:30:00Z",
  "version": 17
}
```

### Graph store chunk item (append-only history segments)

```json
{
  "conversation_key": "telegram:123456789",
  "chunk_key": "chunk:000021",
  "start_seq": 4201,
  "end_seq": 4231,
  "messages": [
    {"seq": 4228, "role": "user", "content": "Hi"},
    {"seq": 4229, "role": "assistant", "content": "Hello"},
    {"seq": 4230, "role": "user", "content": "Need help"},
    {"seq": 4231, "role": "assistant", "content": "Sure"}
  ],
  "updated_at": "2026-02-26T20:30:00Z"
}
```

### Read/write behavior

- **Tail read for inference**
  - Read metadata by conversation key.
  - Fetch latest chunk(s) backward until collecting at least `max_messages`.
  - Return only newest `max_messages` in chronological order for prompt assembly.
- **Append for persistence**
  - Assign new monotonically increasing `seq` values from metadata `last_seq`.
  - Append only newly observed user and assistant turns to the latest chunk (or create next chunk if full).
  - Update metadata (`last_seq`, `latest_chunk_key`, `updated_at`, `version`) with optimistic concurrency and retry.

### Key resolution

- Namespace: tuple from `history_namespace` (for example `("agent_chat_history",)`)
- Conversation key: first non-empty key resolved from `history_key_candidates`
- Candidate/template syntax:
  - Literal string is allowed (for example `support-room-1`)
  - Orcheo template syntax `{{...}}` is allowed (for example `telegram:{{results.telegram_events_parser.chat_id}}`)
  - Templates may reference runtime state such as `inputs`, `results`, `configurable`, and `thread_id`
- Key: resolved from `history_key_template` (literal or template) with `conversation_key` available in scope

## Security Considerations

- Chat history may contain sensitive content; storing only required fields (`role`, `content`) reduces exposure.
- Keep store usage explicit (`use_graph_chat_history=False` by default).
- Ensure DSN and credentials stay in env/vault and are never logged.
- Add warning-level logs on store failures without dumping message bodies.

## Performance Considerations

- Inference path is bounded by `max_messages`: metadata read + latest chunk reads only (not full transcript scan).
- Persistence path appends only deltas; it does not rewrite the full history blob on each turn.
- Full history can grow unbounded for analytics/audit use cases without slowing inference path.
- Use optimistic concurrency for metadata/chunk updates to avoid lost writes under concurrent callbacks.
- For Postgres backend, reuse pooled connections via store factory config.

## Testing Strategy

- **Unit tests**
  - `create_graph_store` for SQLite and Postgres paths, setup call, and invalid backend handling.
  - Config validation/default tests for graph store env vars.
  - `AgentNode` history logic: toggle on/off, key resolution, tail read to `max_messages`, append-only writes, chunk rollover, reset command interaction.

- **Integration tests**
  - Backend compile paths include `store` argument in addition to checkpointer.
  - Repeated callbacks with the same resolved conversation key recover recent context while full history keeps growing append-only.
  - Concurrent callbacks on the same conversation key do not lose appended turns (retry/version path).

- **Manual QA checklist**
  - Simulate WeCom/Telegram callbacks with stable payload IDs (same `chat_id` / same `open_kf_id + external_userid`).
  - Verify context continuity across separate runs.
  - Verify latest `max_messages` retrieval latency remains stable after very long sessions.
  - Verify full transcript remains complete and ordered by `seq`.
  - Verify disabling toggle restores old behavior.

## Rollout Plan

1. Phase 1 (Dev/staging — SQLite): Implement store factory/config and compile wiring; validate with SQLite backend in dev/staging.
2. Phase 2 (Staging — Postgres): Implement `AgentNode` toggle + history behavior; validate DSN/pool setup and end-to-end chat continuity with Postgres backend in staging.
3. Phase 3 (Production opt-in): Enable for selected WeCom/Telegram bot workflows with monitoring.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-02-26 | Codex | Initial draft |
