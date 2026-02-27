# Requirements Document

## METADATA
- **Authors:** Codex
- **Project/Feature Name:** Agent Chat History via LangGraph Store
- **Type:** Enhancement
- **Summary:** Add a LangGraph store backend (SQLite/Postgres) and let `AgentNode` optionally read/write keyed chat history from that store to improve threaded bot behavior.
- **Owner (if different than authors):** Shaojie Jiang
- **Date Started:** 2026-02-26

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| LangGraph persistence guide | https://docs.langchain.com/oss/python/langgraph/persistence | LangChain | Store + persistence reference |
| Existing checkpointer factory | `src/orcheo/persistence.py` | Orcheo Eng | `create_checkpointer` |
| Agent node implementation | `src/orcheo/nodes/ai.py` | Orcheo Eng | `AgentNode` message handling |
| Backend graph compilation paths | `apps/backend/src/orcheo_backend/app/workflow_execution.py` | Orcheo Eng | Workflow execution compile points |
| Initiative requirements | `./1_requirements.md` | Shaojie Jiang | This document |
| Initiative design | `./2_design.md` | Shaojie Jiang | Technical design |
| Initiative plan | `./3_plan.md` | Shaojie Jiang | Milestones and tasks |

## PROBLEM DEFINITION
### Objectives
Add a first-class graph store backend, matching the checkpointer backend strategy, with SQLite and Postgres support and wiring to all backend graph compilations. Extend `AgentNode` with an opt-in toggle to load keyed chat history from graph store, merge it with current thread messages, and trim to `max_messages`.

### Target users
Workflow authors building threaded bot backends (for example, WeCom CS bots, Telegram bots) and backend operators managing Orcheo runtime persistence.

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| Workflow author | Enable graph-store-backed history in `AgentNode` | My bot can continue conversations across webhook runs for the same chat/session | P0 | When toggle is enabled and a stable conversation key is resolved, node loads prior messages, merges with current thread messages, and limits to `max_messages` |
| Workflow author | Keep this feature optional | Existing workflows stay unchanged | P0 | Default behavior remains unchanged when toggle is disabled |
| Backend operator | Configure graph store with SQLite or Postgres | Persistence behavior matches deployment backend | P0 | Settings validation supports both backends and graph compilation receives a store instance |
| Backend operator | Observe history-store failures without run crashes | I can troubleshoot safely | P1 | Store read/write failures are logged and node falls back to in-memory message assembly |

### Context, Problems, Opportunities
Current backend wiring compiles graphs with checkpointer only. `AgentNode` currently derives messages from state/input and truncates locally, but does not read/write a shared keyed chat history store. For messaging channels with repeated callbacks per chat, this can lose continuity unless external state assembly is done manually. Webhook runs currently bind `thread_id` to per-run execution IDs, so `thread_id` alone is not a stable chat key for WeCom CS/Telegram callbacks. LangGraph store support provides a natural place to persist lightweight conversation context keyed by a stable conversation identity.

### Product goals and Non-goals
Goals:
- Add graph store backend creation with SQLite/Postgres parity to checkpointer handling.
- Pass store into all backend `graph.compile(...)` paths.
- Add configurable, opt-in chat-history loading in `AgentNode`.
- Keep only latest `max_messages` for inference after merge; store full history append-only.

Non-goals:
- Replacing checkpointer state semantics.
- Building long-term memory retrieval/ranking.
- Introducing summarization/compression in this iteration.
- Cross-thread identity resolution.

## PRODUCT DEFINITION
### Requirements
P0:
- Add `create_graph_store(settings)` in persistence utilities, similar lifecycle to `create_checkpointer(settings)`.
- Support `sqlite` and `postgres` graph store backends.
- Add settings for graph store backend/path with environment validation.
  - SQLite path must be absolute (no `~` or relative paths) to avoid shell-dependent expansion behavior.
- Update all backend graph compilation entry points to pass both `checkpointer` and `store`.
- Add `AgentNode` toggle (for example `use_graph_chat_history: bool = False`).
- When toggle is `True`:
  - Resolve a stable conversation key with this precedence:
    - Explicit override from a previous node result, config, or input (for example `{{results.resolve_history_key.session_key}}`, `{{configurable.history_key}}`, or `{{inputs.history_key}}`).
    - Channel-derived key from parsed payload fields:
      - Telegram: `telegram:{{results.telegram_events_parser.chat_id}}`
      - WeCom Customer Service: `wecom_cs:{{results.wecom_cs_sync.open_kf_id}}:{{results.wecom_cs_sync.external_userid}}`
      - WeCom AI bot: `wecom_aibot:{{results.wecom_ai_bot_events_parser.chat_type}}:{{results.wecom_ai_bot_events_parser.user}}`
      - WeCom internal direct message: `wecom_dm:{{results.wecom_events_parser.user}}`
    - Fallback: `{{thread_id}}` for non-webhook/manual flows.
  - Key fields (`history_key_template`, `history_key_candidates`) must support both:
    - Literal values (for example `support-room-1`)
    - Orcheo template strings `{{...}}` (including previous node outputs via `results.*`)
  - Key resolution must be deterministic and validated:
    - Evaluate candidates in declared order after template rendering.
    - Reject empty keys, unresolved templates (for example values still containing `{{`), and keys with invalid characters.
    - Limit key length (for example max 256 chars) to prevent store-key abuse and accidental collisions.
    - If no valid key is resolved, skip store read/write and continue with in-memory-only behavior.
  - Read stored history before agent run (tail window up to `max_messages`).
  - Merge stored history tail with current thread messages for this invocation.
  - Keep latest `max_messages` for inference.
  - Append newly observed user/assistant turns to full history in graph store after run (full history grows append-only; `max_messages` cap applies only to the inference payload).
  - Store-operation failure behavior:
    - Read failure: warn and continue with in-memory-only message assembly.
    - Write/conflict failure after retries: warn and continue execution without persistence for that run.
    - Runtime should not crash due to node-level store read/write failures.
- When toggle is `False`, preserve current behavior.

P1:
- Add configurable keying fields (`history_namespace`, `history_key_template`, `history_key_candidates`, `history_value_field`).
- Add best-effort error handling and structured logs for store operations.
- Define optimistic-concurrency retry policy (retry limit + backoff + conflict outcome).
- Add observability requirements for store latency/errors, key-resolution failures, and truncation events.
- Add migration and user-facing documentation requirements for workflows transitioning from manual session assembly.

Out of scope:
- Automatic redaction and PII classification.
- Semantic retrieval over historic messages.

### Designs (if applicable)
See `./2_design.md`.

### [Optional] Other Teams Impacted
- **Backend Runtime:** configuration and compile wiring updates.
- **Workflow Authors:** optional new node fields and expectations around stable conversation-key inputs.

## TECHNICAL CONSIDERATIONS
### Architecture Overview
Introduce a dedicated graph store factory in `src/orcheo/persistence.py`, add configuration surface in `orcheo.config`, and wire store instances into backend compile paths that already inject checkpointer. `AgentNode` consumes the runtime store via LangGraph context and performs keyed history load/merge/trim/persist around agent invocation.

### Technical Requirements
- Store backend validation and defaults must be deterministic and backward compatible.
- SQLite path validation must reject non-absolute paths and `~`-prefixed paths.
- Postgres mode requires DSN and compatible pool options.
- Store setup/migrations (`store.setup()`) must run during startup/first use similarly to checkpointer setup.
- Agent history merge should normalize stored entries into `BaseMessage` equivalents.
- History retrieval requires a resolved conversation key; if unavailable, skip store logic safely.
- Key resolution must support literal values and Orcheo `{{...}}` templates for both `history_key_template` and `history_key_candidates`.
- Key validation must enforce non-empty, bounded-length, and allowed-character constraints before any store operation.
- Keep message ordering stable (oldest to newest before trimming tail).
- Concurrency control must specify retry limits and bounded backoff behavior; persistent conflicts should degrade to warning + skip write, not run failure.
- Tests must include reproducible fixtures covering literal keys and channel-specific template patterns (Telegram/WeCom).

### AI/ML Considerations (if applicable)
Not applicable.

## MARKET DEFINITION
Internal enhancement for Orcheo runtime and bot workflow authors.

## LAUNCH/ROLLOUT PLAN
### Success metrics
| KPIs | Target & Rationale |
|------|--------------------|
| Graph compile compatibility | 100% backend compile paths continue to execute with store enabled/disabled |
| Agent history continuity | For repeated callbacks with the same conversation key, prior turns are present in payload when toggle is enabled |
| Regression guardrail | No behavior change in existing workflows with toggle disabled |

### Rollout Strategy
- Implement behind opt-in node field (default `False`).
- Validate SQLite first in local/staging, then Postgres staging.
- Enable feature in selected bot workflows before wider use.
- Define phase-specific rollback steps:
  - Phase 1 rollback: disable graph store backend and compile without `store`.
  - Phase 2 rollback: disable `use_graph_chat_history` for affected workflows.
  - Phase 3 rollback: revert workflow-level toggles and keep legacy in-memory behavior.
- Provide migration guidance for existing workflows that currently do manual session management.

### Experiment Plan (if applicable)
No formal A/B test; use staged workflow validation with replayed thread samples.

### Estimated Launch Phases (if applicable)
| Phase | Target | Description |
|-------|--------|-------------|
| **Phase 1** | Dev/staging (SQLite) | Validate store factory, compile wiring, and node history behavior |
| **Phase 2** | Staging (Postgres) | Validate DSN/pool setup and end-to-end chat continuity |
| **Phase 3** | Production opt-in | Enable for selected WeCom/Telegram workflows |

## HYPOTHESIS & RISKS
- **Hypothesis:** Persisting bounded thread history in graph store improves multi-turn response quality for channel bots without forcing external session assembly.
- **Risk:** Duplicate or conflicting memory sources (checkpointer state vs graph store) can cause confusion.
  - **Mitigation:** Keep graph-store history explicitly opt-in and documented as chat history source for `AgentNode` only.
- **Risk:** Storage growth and sensitive data retention.
  - **Mitigation:** Keep bounded window (`max_messages`), add retention/TTL follow-up, and avoid storing unnecessary payload fields.
- **Risk:** Missing/unstable conversation keys lead to fragmented history.
  - **Mitigation:** Prefer explicit/channel-derived keys, keep `thread_id` only as fallback, validate resolved keys (non-empty/format/length), and log key-resolution failures.

## APPENDIX
None.
