# Project Plan

## For Agent Training Runtime & AgentensorNode

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-16
- **Status:** In Progress

---

## Overview

Deliver runtime support for `langchain_core.runnables.RunnableConfig` on workflow runs and ship an AgentensorNode that handles evaluation and prompt-optimization training with checkpoints. The plan prioritizes runtime compatibility, reproducible evaluations, and safe training loops. See related documents for full context.

**Related Documents:**
- Requirements: docs/agentensor/requirements.md
- Design: docs/agentensor/design.md

---

## Milestones

### Milestone 0: Agentensor Fork & Packaging

**Description:** Fork upstream agentensor into the monorepo as `packages/agentensor`, align packaging/tooling, and add Orcheo-facing definitions/shims in `src/orcheo/` as needed.

#### Task Checklist

- [x] Task 0.1: Vendor/fork `agentensor` into `packages/agentensor` with compatible `pyproject`/uv metadata mirroring `packages/sdk`
  - Dependencies: Repo access to upstream
- [x] Task 0.2: Wire local package into Orcheo build/test pipeline (lint/typecheck/test)
  - Dependencies: Task 0.1
- [x] Task 0.3: Add minimal Orcheo integration shims/types in `src/orcheo/` (e.g., config refs, node bindings) to work with the forked package
  - Dependencies: Task 0.1
- [x] Task 0.4: Publish/consume uv lockfile updates to ensure downstream tooling uses the fork consistently
  - Dependencies: Task 0.2

---

### Milestone 1: RunnableConfig Ingestion

**Description:** Accept and propagate `RunnableConfig` on workflow runs with validation, merging, and observability in place.

#### Task Checklist

- [x] Task 1.1: Extend run API/SDK schema to accept `RunnableConfig`, with validation and backward compatibility
  - Dependencies: Requirements sign-off
- [x] Task 1.2: Propagate merged config into LangGraph runtime and node execution context (including resolving node -> config prompt references for trainable `TextTensor` prompts); enforce safe limits
  - Dependencies: Task 1.1
- [x] Task 1.3: Register AgentensorNode in `src/orcheo/nodes/registry.py` as a `TaskNode` subclass and validate `{{path.to.value}}` interpolation for prompts
  - Dependencies: Task 1.2
- [x] Task 1.4: Persist run metadata (config, tags, callbacks) and emit observability signals
  - Dependencies: Task 1.2

---

### Milestone 2: AgentensorNode Evaluation Mode

**Description:** Build evaluation-only mode for AgentensorNode with dataset iteration, evaluator execution, and metrics reporting.

#### Task Checklist

- [x] Task 2.1: Implement AgentensorNode evaluation flow with dataset/evaluator wiring
  - Dependencies: Milestone 1
- [x] Task 2.2: Add API/CLI entry to trigger evaluation runs and stream progress via existing workflow router/WebSocket channel
  - Dependencies: Task 2.1
- [x] Task 2.3: Aggregate metrics, persist results, and document evaluator schema
  - Dependencies: Task 2.1

---

### Milestone 3: AgentensorNode Training Mode & Checkpoints

**Description:** Enable prompt optimization loops, checkpointing, and guardrails for training runs.

#### Task Checklist

- [ ] Task 3.1: Integrate optimizer loop for trainable prompts (referenced by nodes via config paths) and runnable-config updates; emit checkpoints
  - Dependencies: Milestone 2
- [ ] Task 3.2: Persist checkpoints and best-performing configs in a dedicated DB table keyed by `workflow_id` with versioned records; expose download/reuse endpoints and ship SQLite/PostgreSQL migrations
  - Dependencies: Task 3.1
- [ ] Task 3.3: Add safeguards (concurrency limits, timeout caps) and end-to-end tests for training mode (including compatibility with existing nodes)
  - Dependencies: Task 3.1
- [ ] Task 3.4: Conduct performance and migration testing (concurrency, rollback/restore) and document operational runbooks
  - Dependencies: Task 3.2

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-16 | Codex | Initial draft |
