# Requirements Document

## METADATA
- **Authors:** Codex
- **Project/Feature Name:** Agent Training Runtime & AgentensorNode
- **Type:** Enhancement
- **Summary:** Enable workflow runs to accept `langchain_core.runnables.RunnableConfig` inputs and add an AgentensorNode for evaluation and prompt optimization with checkpointed configs.
- **Owner (if different than authors):** Shaojie Jiang
- **Date Started:** 2025-12-16

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| Prior Artifacts | [agentensor trainer example](https://github.com/ShaojieJiang/agentensor/blob/main/examples/train.py) | Shaojie Jiang | Agentensor trainer example |
| Design Review | `./design.md` | Shaojie Jiang | Agent training design |
| Eng Requirement Doc | `./requirements.md` | Shaojie Jiang | Agent training PRD |
| Experiment Plan | `./plan.md` | Shaojie Jiang | Agent training plan |

## PROBLEM DEFINITION
### Objectives
Enable Orcheo workflows to ingest per-run `RunnableConfig` so authors can control runtime parameters without code changes. Introduce an AgentensorNode that evaluates workflows and optionally optimizes agent prompts, returning evaluation scores and checkpointed configs.

### Target users
Workflow authors, agent builders, and evaluation engineers who need reproducible runs, controllable runtime behavior, and integrated agent evaluation/training.

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| Workflow author | Pass run-specific `RunnableConfig` into workflow run requests | I can tune tracing, concurrency, and metadata without redeploying code | P0 | Runtime accepts validated `RunnableConfig`, applies it to the run context, and preserves defaults when fields are omitted |
| Evaluation engineer | Execute AgentensorNode in evaluation mode against curated datasets and evaluators | I can benchmark agent workflows and share metrics | P0 | Node runs evaluation-only, returns per-evaluator scores and aggregated metrics, and streams progress |
| Agent builder | Run AgentensorNode in training mode to optimize prompts and checkpoint configs | I can iteratively improve agent performance and reuse optimized settings | P0 | Training produces an optimized `RunnableConfig`, emits evaluation at checkpoints, and persists/downloads the best config |

### Context, Problems, Opportunities
Current workflows cannot accept `RunnableConfig` at runtime, forcing code edits for changes to tracing, concurrency, tags, and metadata. Agent evaluation is manual and disconnected from workflow execution, and prompt optimization relies on ad hoc scripts (e.g., the example trainer in `https://github.com/ShaojieJiang/agentensor/blob/main/examples/train.py`). By formalizing runtime config ingestion and shipping a first-class AgentensorNode, we reduce friction for experimenters, improve reproducibility, and enable automated prompt tuning aligned with LangGraph execution.

### Product goals and Non-goals
Goals: support runtime `RunnableConfig` across API/SDK runs; deliver an AgentensorNode with evaluation-only and training modes; provide checkpointed optimized configs with reproducible metrics. Non-goals: building a new UI for training, adding new model providers, or redesigning dataset/evaluator authoring.

## PRODUCT DEFINITION
### Requirements
- **P0: RunnableConfig ingestion**
  - Accept `RunnableConfig` payloads on workflow run requests (API and SDK), validate against LangChain schema, and merge with workflow defaults.
  - Propagate config to all nodes, preserving tracing callbacks, tags, and per-node overrides where applicable.
  - Persist run metadata (config, version, evaluator set) for reproducibility and audit.
- **P0: AgentensorNode - Evaluation mode**
  - Inputs: compiled workflow, `RunnableConfig`, evaluation dataset reference, evaluator functions (LLM-based or deterministic).
  - Behavior: run workflow against dataset, collect per-case metrics, aggregate summary, and return evaluation-only outputs.
  - Support streaming/periodic progress updates and error surfacing per case.
- **P0: AgentensorNode - Training mode**
  - Behavior: optimize prompts defined in `RunnableConfig` (trainable prompts declared as `TextTensor` entries, referenced by agent nodes via config paths, and resolved via Orcheo's `{{path.to.value}}` interpolation) using gradient-free/optimizer loop inspired by `https://github.com/ShaojieJiang/agentensor/blob/main/examples/train.py`.
  - Emit checkpointed optimized configs and corresponding evaluation metrics at configured intervals.
  - Return the best-performing config plus final evaluation summary; allow opt-out for certain nodes/prompts.
- **P1: Tooling and ergonomics**
  - CLI helper to trigger training/evaluation runs with config/dataset references.
  - Documentation and examples covering config schemas, evaluator hooks, and checkpoint handling.

### Designs (if applicable)
See `./design.md` for architecture, flows, and API contracts.

## TECHNICAL CONSIDERATIONS
### Architecture Overview
Workflow runtime (FastAPI/WebSocket + LangGraph) accepts `RunnableConfig` and passes it to compiled graphs. AgentensorNode orchestrates dataset iteration, evaluator execution, and optimizer loops, persisting checkpoints and metrics via existing storage/metadata services.

### Technical Requirements
- JSON-serializable `RunnableConfig` schema compatible with LangChain; reject unsafe callbacks or unserializable fields.
- Trainable prompts must be defined in the config as `TextTensor` objects and referenced by agent nodes via config paths at runtime for evaluation/training.
- Fork upstream `agentensor` into `packages/agentensor`, align with existing `packages/sdk` tooling (uv metadata, Ruff/mypy hooks), and add minimal integration shims in `src/orcheo/` where needed (e.g., config refs, node bindings).
- Backward compatibility for runs without `RunnableConfig` (default behavior unchanged).
- Configurable concurrency and timeout controls to protect shared infrastructure during training.
- Deterministic seeding and dataset versioning for reproducible evaluations.
- Checkpoint storage in a dedicated DB table keyed by `workflow_id` with versioned config records; references stored in run metadata for later reuse/download with migrations for both SQLite (local) and PostgreSQL (prod).
- AgentensorNode registered in the existing node registry (`src/orcheo/nodes/registry.py`) as a `TaskNode` subclass, inheriting state handling and `decode_variables()` behavior so `TextTensor` prompts resolve through the existing `_decode_value()` interpolation logic.
- API additions (trainer/evaluator mode) extend the existing workflow router/WS streaming pattern rather than a new top-level endpoint; authentication/authorization must match current workflow run policies.

### AI/ML Considerations
#### Data Requirements
Evaluation datasets with inputs/expected behaviors and evaluator functions; support text and multimodal tensors where applicable. Store dataset versions and metadata (domains, languages, evaluation rubric).

#### Algorithm selection
Initial optimizer mirrors `agentensor` example: prompt tensor optimization with gradient-free/LLM-judged feedback. Allow pluggable evaluators to score outputs and guide prompt updates.

#### Model performance requirements
Target ≥10% improvement over baseline evaluator score on training set and no worse than -2% on holdout. Ensure latency increase per run stays within operational limits.

### Testing Expectations
- Compatibility testing with existing node types to ensure `RunnableConfig` propagation and prompt interpolation continue to work.
- Performance tests for concurrent training/evaluation runs with bounded concurrency.
- Migration tests covering SQLite/PostgreSQL schema upgrades for checkpoint storage.

## MARKET DEFINITION
Internal feature; no external TAM or launch exceptions required.

## LAUNCH/ROLLOUT PLAN
### Success metrics
| KPIs | Target & Rationale |
|------|--------------------|
| Primary: Valid runs with `RunnableConfig` applied | ≥99% success rate across staged rollouts |
| Secondary: Evaluation throughput | Run 95% of evaluation cases within SLA and surface per-case errors |
| Guardrail: Post-training regression | Holdout evaluator score does not degrade by more than 2% vs. baseline |

### Rollout Strategy
Feature-flag `RunnableConfig` ingestion and AgentensorNode per workflow; start with internal workflows, then allow opt-in for pilot partners before enabling by default.

### Experiment Plan (if applicable)
Offline evaluation using curated datasets; compare baseline vs. optimized configs with holdout split; log evaluator metrics and latency deltas.

### Estimated Launch Phases (if applicable)
| Phase | Target | Description |
|-------|--------|-------------|
| **Phase 1** | Dev/staging workflows | Enable config ingestion and evaluation mode behind flags; validate schema and observability |
| **Phase 2** | Internal pilot workflows | Enable training mode with limited datasets; collect performance metrics and adjust safeguards |
| **Phase 3** | Broad internal availability | Allow opt-in for all workflows; finalize docs and CLI helpers |

## HYPOTHESIS & RISKS
Adding `RunnableConfig` ingestion and an AgentensorNode will shorten iteration cycles and increase evaluator scores without destabilizing runs. Risks include config injection of unsupported callbacks, training runs overloading shared resources, and optimizer regressions on holdout data. Mitigation: strict schema validation, rate/concurrency limits, checkpoint-based rollbacks, and holdout evaluation before promoting optimized configs.

## APPENDIX
Additional examples and dataset templates will be added alongside implementation.
