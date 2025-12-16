# Requirements Document

## METADATA
- **Authors:** Codex
- **Project/Feature Name:** Agentensor-powered AI node optimization for Orcheo
- **Type:** Feature
- **Summary:** Absorb the agentensor project as a first-class package and use its optimizers to tune Orcheo AI nodes via evaluation outputs while persisting best-performing prompts and hyper-parameters for production.
- **Owner (if different than authors):** Shaojie Jiang
- **Date Started:** 2025-12-16

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| Prior Artifacts | https://github.com/ShaojieJiang/agentensor | Shaojie Jiang | Agentensor OSS reference |
| Design Review | docs/agentensor/design.md | Shaojie Jiang | Agentensor integration design |
| Eng Requirement Doc | docs/agentensor/requirements.md | Shaojie Jiang | This document |
| Experiment Plan | docs/agentensor/plan.md | Shaojie Jiang | Execution plan |
| Rollout Docs | docs/agentensor/plan.md | Shaojie Jiang | Launch steps (inline) |

## PROBLEM DEFINITION
### Objectives
Integrate agentensor into Orcheo so AI nodes can be optimized automatically using evaluation feedback, and persist the best parameters for production use.
Provide a repeatable loop where evaluation node outputs become losses for agentensor optimizers, closing the gap between experimentation and live workflows.

### Target users
Workflow authors who build Orcheo graphs with AI nodes and want automated prompt/hyper-parameter tuning.
Evaluation owners who need evaluation signals to drive optimization.
Platform operators who maintain reliable, reproducible AI node behavior in production.

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| Workflow author | Attach an agentensor optimizer to AI nodes | Prompts and hyper-parameters improve without manual trial-and-error | P0 | Optimizer selectable per AI node; runs on-demand or scheduled; status visible |
| Evaluation owner | Feed evaluation node outputs into optimizers as losses | Optimization aligns with our evaluation metrics and guardrails | P0 | Evaluation outputs available in optimizer context; failed evaluations fail fast with clear errors |
| Platform operator | Persist and version the best-performing AI node parameters | Production runs default to vetted prompts with rollback options | P0 | Best parameters stored with metadata and checksum; inference uses latest approved version; rollback supported |
| Developer | Install and import agentensor from this repo | There is a single dependency graph and maintenance surface | P1 | agentensor packaged under the Orcheo repo; build/install steps documented and passing CI |

### Context, Problems, Opportunities
Agentensor currently lives as an external repo, creating dependency drift and deployment friction. Orcheo AI nodes lack an automated path to tune prompts and hyper-parameters using real evaluation feedback. This project consolidates agentensor, wires evaluation outputs into optimization loops, and standardizes persistence so optimized configurations flow cleanly into production workflows.

### Product goals and Non-goals
- Goals: First-party agentensor package; optimizer-to-evaluation integration; durable storage and retrieval of best AI node parameters; reproducible optimization runs with audit trails.
- Non-goals: Building new evaluation metrics; changing Orcheo execution semantics beyond optimizer hooks; creating a full UI for optimization (initially CLI/API driven).

## PRODUCT DEFINITION
### Requirements
- P0: Vendor/absorb agentensor into the Orcheo repo with build, test, and packaging parity (uv/pyproject).
- P0: Provide a configuration API to attach agentensor optimizers to Orcheo AI nodes (per-node and per-workflow scopes).
- P0: Route evaluation node outputs into agentensor as loss/metric inputs with schema validation and failure surfacing.
- P0: Persist best-performing AI node parameters (system prompts, temperature, other hyper-parameters) with versioning, approvals, and audit metadata.
- P1: Support scheduled/continuous optimization runs driven by evaluation recency and data volume thresholds.
- P1: Expose optimization artifacts (metrics, parameter diffs) via CLI/API for observability and rollback.
- Out of scope: UI dashboards, auto-creation of new evaluation nodes, or model training beyond prompt/hyper-parameter tuning.

### Designs (if applicable)
Design overview: docs/agentensor/design.md
Copy/doc references: docs/agentensor/plan.md

### Other Teams Impacted
- DevOps: Build and packaging updates for the merged agentensor library.
- Product Ops: Rollout coordination for workflows adopting optimized prompts.
- Security: Review of persisted prompt content and secrets handling.

## TECHNICAL CONSIDERATIONS

### Architecture Overview
- Absorb agentensor code under the Orcheo monorepo and expose it as `orcheo.agentensor`.
- Add optimizer hooks in the Orcheo graph execution so AI nodes can emit optimization events and consume updated parameters.
- Create an evaluation-to-optimizer bridge that transforms evaluation node outputs into loss signals consumable by agentensor.
- Store tuned parameters and metadata in existing Orcheo persistence layers (DB/object storage) with versioning semantics.

### Technical Requirements
- Maintain absolute imports and typing across the merged codebase; align with Orcheo lint/mypy rules.
- Provide deterministic optimizer runs (seeded) and log artifacts for reproducibility.
- Handle partial failures: evaluation errors should halt optimization and emit actionable diagnostics.
- Ensure serialization of optimizer configs and tuned parameters for reuse across environments.
- Keep runtime overhead minimal for production inference (no optimizer dependency on hot path; only persisted parameters are used).

### AI/ML Considerations

#### Data Requirements
- Evaluation node outputs, including scores and structured feedback, must be captured and normalized for optimizer consumption.
- Store optimization traces (loss curves, parameter candidates) for audit and regression analysis.

#### Algorithm selection
- Use agentensor's existing optimizer set (e.g., Bayesian/gradient-free search) with pluggable strategy selection per AI node.
- Default to sample-efficient optimizers for prompt tuning; allow metric-specific objective configuration.

#### Model performance requirements
- P0: Optimized prompts must improve primary evaluation metrics by at least 10% over baseline or maintain parity with reduced variance.
- Guardrail: No degradation on safety/constraint evaluations; enforce fail-closed behavior on regression.

## MARKET DEFINITION
Internal platform feature; external TAM not applicable. No external market exclusions anticipated.

### Total Addressable Market
Internal Orcheo workflows and AI nodes across product teams; external users not in scope for this release.

### Launch Exceptions
None planned; all internal environments are eligible once feature flags are enabled.

| Market | Status | Considerations & Summary |
|--------|--------|--------------------------|
| Internal | Will launch | Feature-flagged rollout to Orcheo-managed workflows |

## LAUNCH/ROLLOUT PLAN

### Success metrics
| KPIs | Target & Rationale |
|------|--------------------|
| Primary: % AI nodes using optimizer-backed parameters | 50% of AI nodes in pilot workflows within 2 sprints |
| Secondary: Evaluation metric lift after optimization | ≥10% improvement on primary eval metric vs. baseline |
| Guardrail: Safety/constraint regressions | 0 regressions; all guardrail evals pass before promotion |

### Rollout Strategy
- Stage 1: Enable agentensor packaging and optimizer hooks behind a feature flag in dev/staging.
- Stage 2: Pilot with 2–3 workflows with existing evaluation coverage; require sign-off on persisted parameters.
- Stage 3: Broader enablement and documentation for workflow authors; default new AI nodes to accept optimizer configs.

### Experiment Plan
- A/B compare optimized vs. baseline prompts on a holdout evaluation set per workflow.
- Track win rate and variance; rollback if guardrail metrics fail or improvement <5%.

### Estimated Launch Phases

| Phase | Target | Description |
|-------|--------|-------------|
| **Phase 1** | Dev/staging workflows | Agentensor package absorbed; optimizer hooks available behind flag |
| **Phase 2** | Pilot workflows | Evaluation-driven optimization runs with persisted best parameters |
| **Phase 3** | All internal workflows | Default availability; documentation and observability in place |

## HYPOTHESIS & RISKS
Hypothesis: Using agentensor optimizers with evaluation-driven losses will improve AI node evaluation metrics by at least 10% while keeping safety guardrails intact.
Risks: Overfitting to evaluation sets, storage of sensitive prompt content, runtime regressions if optimized parameters are malformed, and maintenance overhead from merging repos.
Risk Mitigation: Use holdout evals and guardrails, redact sensitive data before persistence, validate parameter schemas pre-promotion, and add CI checks for merged agentensor modules.

## APPENDIX
None at this time.
