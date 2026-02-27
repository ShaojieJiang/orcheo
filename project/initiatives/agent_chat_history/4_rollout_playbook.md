# Rollout Playbook

- **Version:** 0.2
- **Author:** Codex
- **Owner:** Shaojie Jiang
- **Date:** 2026-02-27

## Scope

Operational rollback and migration guidance for graph-store-backed `AgentNode` chat history.

## Rollback Playbook

### Phase 1: SQLite Staging

Trigger conditions:
- Graph compilation fails after store wiring changes.
- SQLite store setup/read/write errors regress staging stability.

Rollback:
1. Set `ORCHEO_GRAPH_STORE_BACKEND=sqlite` and keep `ORCHEO_GRAPH_STORE_SQLITE_PATH` pointed at a valid absolute path for diagnostics.
2. Disable workflow-level history usage by setting `use_graph_chat_history=false` for affected `AgentNode` definitions.
3. Redeploy backend/worker services.
4. Validate that workflow runs still succeed with checkpointer-only behavior.

### Phase 2: Postgres Staging

Trigger conditions:
- DSN/pool configuration errors.
- Persistent store write conflicts or latency regressions.

Rollback:
1. Switch `ORCHEO_GRAPH_STORE_BACKEND=sqlite` for staging workloads.
2. Keep `use_graph_chat_history=false` on unstable workflows until Postgres configuration is corrected.
3. Redeploy services and rerun callback replay validation.

### Phase 3: Production Opt-In

Trigger conditions:
- Channel-specific key resolution failures.
- Elevated graph-history read/write failures.

Rollback:
1. Disable `use_graph_chat_history` on affected production workflows first (fastest and lowest-risk rollback).
2. If backend-wide issues persist, switch to `ORCHEO_GRAPH_STORE_BACKEND=sqlite` with a known-good path.
3. If required, roll back backend image to previous release and keep the feature toggle disabled.

## Migration Guidance

### Prerequisites

1. Configure graph store:
  - `ORCHEO_GRAPH_STORE_BACKEND=sqlite|postgres`
  - `ORCHEO_GRAPH_STORE_SQLITE_PATH` must be absolute when backend is `sqlite`
  - `ORCHEO_POSTGRES_DSN` required when backend is `postgres`
2. Ensure workflows compile with both checkpointer and store wiring (covered by backend unit tests).

### Node Configuration Migration

1. Enable feature per `AgentNode`:
  - `use_graph_chat_history: true`
2. Keep defaults unless customization is needed:
  - `history_namespace: ["agent_chat_history"]`
  - `history_key_template: "{{conversation_key}}"`
3. Keep default channel-derived `history_key_candidates`; add custom candidates only when workflow-specific keys are required (for example `{{results.resolve_history_key.session_key}}` or `{{config.configurable.history_key}}`).

### Validation Checklist

1. Replay repeated callbacks for the same Telegram/WeCom identities and verify context continuity.
2. Confirm unresolved or invalid keys do not crash runs (node should degrade to in-memory behavior).
3. Verify truncation behavior: inference payload keeps latest `max_messages`, while store history keeps appended turns.
4. Monitor warning logs for:
  - key-resolution failures
  - store read failures
  - store write conflicts/failures

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-02-27 | Codex | Updated migration guidance to remove `thread_id` fallback dependency and align custom key examples with state-based `{{config.*}}` templates |
| 2026-02-27 | Codex | Initial draft |
