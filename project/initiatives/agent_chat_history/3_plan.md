# Project Plan

## For Agent Chat History via LangGraph Store

- **Version:** 0.1
- **Author:** Codex
- **Owner:** Shaojie Jiang
- **Date:** 2026-02-26
- **Status:** Draft

---

## Overview

Deliver graph-store support (SQLite/Postgres) and `AgentNode` opt-in chat-history behavior for threaded bot backends, while preserving backward compatibility for existing workflows.

**Related Documents:**
- Requirements: `./1_requirements.md`
- Design: `./2_design.md`

---

## Milestones

### Milestone 1: Graph Store Foundation

**Description:** Add store backend configuration and persistence factory, parallel to checkpointer behavior.

#### Task Checklist

- [ ] Task 1.1: Add config types/defaults for graph store backend and sqlite path.
  - Dependencies: None
- [ ] Task 1.2: Add validation rules in `AppSettings` and loader normalization.
  - Dependencies: Task 1.1
- [ ] Task 1.3: Implement `create_graph_store(settings)` in `src/orcheo/persistence.py` for SQLite/Postgres.
  - Dependencies: Task 1.2
- [ ] Task 1.4: Add persistence tests for graph store factory (sqlite/postgres/error paths).
  - Dependencies: Task 1.3

---

### Milestone 2: Backend Compile Wiring

**Description:** Ensure all runtime compilation paths receive both checkpointer and store.

#### Task Checklist

- [ ] Task 2.1: Update workflow execution compile paths to include `store`.
  - Dependencies: Milestone 1
- [ ] Task 2.2: Update trigger/worker/ChatKit executor compile paths to include `store`.
  - Dependencies: Task 2.1
- [ ] Task 2.3: Add/adjust backend unit tests that patch compile calls to assert `store` wiring.
  - Dependencies: Task 2.2

---

### Milestone 3: AgentNode Graph Chat History

**Description:** Add opt-in node behavior to load/merge/trim/persist chat history from graph store.

#### Task Checklist

- [ ] Task 3.1: Add `AgentNode` toggle and keying fields with safe defaults (`use_graph_chat_history=False`) and stable conversation-key precedence (explicit/channel-derived before `thread_id` fallback).
  - Acceptance note: `history_key_template` and `history_key_candidates` accept both literal strings and Orcheo templates (`{{...}}`) including `results.*` references.
  - Dependencies: Milestone 1
- [ ] Task 3.2: Implement store read and message normalization path before agent invoke.
  - Dependencies: Task 3.1
- [ ] Task 3.3: Implement merge + `max_messages` trimming + post-run store update.
  - Dependencies: Task 3.2
- [ ] Task 3.4: Add node tests for enabled/disabled behavior, key resolution, and trim semantics.
  - Acceptance note: include test cases for literal keys and `{{...}}` template keys resolved from previous node results.
  - Dependencies: Task 3.3

---

### Milestone 4: Hardening, Validation, and Reflection

**Description:** Validate behavior in bot-like scenarios and document operational guidance.

#### Task Checklist

- [ ] Task 4.1: Run targeted test suites for config, persistence, backend workflow execution, and AI node message handling.
  - Dependencies: Milestones 2 and 3
- [ ] Task 4.2: SQLite staging verification — validate store factory, compile wiring, and node history behavior with SQLite backend using repeated callbacks with stable conversation IDs (WeCom/Telegram-like payloads).
  - Dependencies: Task 4.1
- [ ] Task 4.3: Postgres staging verification — validate DSN/pool setup and end-to-end chat continuity with Postgres backend using the same callback scenarios.
  - Dependencies: Task 4.2
- [ ] Task 4.4: Document guidance on when to use graph-store chat history and known risks (retention, duplication, key quality).
  - Dependencies: Task 4.3

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-02-26 | Codex | Initial draft |
