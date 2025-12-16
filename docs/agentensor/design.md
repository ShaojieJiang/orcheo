# Design Document

## For Agentensor-powered optimization for Orcheo

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-16
- **Status:** Draft

---

## Overview

We are merging the agentensor optimization library into the Orcheo repository and exposing it as `orcheo.agentensor`. The goal is to let Orcheo AI nodes delegate prompt and hyper-parameter tuning to agentensor optimizers while consuming losses derived from Orcheo evaluation nodes. Best-performing parameters are persisted and promoted to production inference by default, with rollback support and auditability.

This design defines the integration points between Orcheo's workflow execution engine, evaluation nodes, the optimizer loop, and the parameter store. It focuses on keeping optimization off the hot inference path, ensuring reproducibility, and making evaluation outputs the single source of truth for optimization signals.

## Components

- **Orcheo Workflow Orchestrator (Python/Orcheo)**
  - Runs workflow graphs, including AI and evaluation nodes.
  - Emits evaluation outputs and exposes hooks for optimizer triggers.
- **Agentensor Optimizer Library (Python/orcheo.agentensor)**
  - Provides optimization strategies (e.g., Bayesian and gradient-free search).
  - Accepts objectives from evaluation outputs and returns candidate parameters.
- **Evaluation-to-Optimizer Bridge (Python/Orcheo)**
  - Normalizes evaluation node outputs into loss/metric schemas agentensor can consume.
  - Handles validation, error surfacing, and batching of evaluation results.
- **Parameter Store (DB/Object Storage + Metadata)**
  - Persists tuned parameters, version tags, approval status, and checksums.
  - Serves parameters to inference-time AI nodes and supports rollback.
- **Observability & Control Plane (FastAPI/CLI)**
  - API and CLI endpoints to start optimization runs, inspect artifacts, and promote parameters.
  - Integrates with feature flags for staged rollout.

## Request Flows

### Flow 1: Optimization Run

1. User or scheduler triggers `POST /api/workflows/{workflow_id}/optimize` with target AI nodes and optimizer settings.
2. Orcheo runs the workflow; AI nodes generate outputs; evaluation nodes compute metrics.
3. The bridge converts evaluation outputs into optimizer objectives and feeds them into agentensor.
4. Agentensor proposes new parameter candidates; Orcheo reruns affected nodes/evaluations as needed.
5. Optimization stops when convergence/limit criteria are met; the best parameters and artifacts are persisted.
6. User reviews and optionally promotes the parameters to production.

### Flow 2: Production Inference with Persisted Parameters

1. Workflow execution starts in production.
2. AI nodes fetch the latest approved parameter version from the parameter store.
3. Inference runs with cached parameters; no optimizer logic is executed on the hot path.
4. Outputs are logged; optional shadow evaluations can be run for drift detection.

### Flow 3: Rollback or Promotion

1. Operator requests promotion or rollback via CLI/API.
2. Control plane updates the parameter version pointer for the targeted AI nodes.
3. Subsequent workflow executions pick up the new/rolled-back parameters automatically.

## API Contracts

```
POST /api/workflows/{workflow_id}/optimize
Headers:
  Authorization: Bearer <token>
Body:
  node_ids: string[]
  optimizer: string
  objective: { metric: string, direction: "maximize" | "minimize" }
  limits: { iterations: int, time_seconds: int }

Response:
  202 Accepted -> { run_id, status: "running" }
  4xx/5xx -> validation or execution errors
```

```
GET /api/workflows/{workflow_id}/parameters/{node_id}
Response:
  200 OK -> { version, parameters: {...}, metadata: {...} }
```

```
POST /api/workflows/{workflow_id}/parameters/{node_id}/promote
Body:
  version: string
  reason: string
Response:
  200 OK -> { status: "promoted", active_version: version }
```

CLI equivalents mirror these endpoints via `uv run orcheo optimize ...` commands.

## Data Models / Schemas

| Field | Type | Description |
|-------|------|-------------|
| run_id | string | Unique optimizer run identifier |
| workflow_id | string | Target workflow |
| node_id | string | Target AI node |
| optimizer | string | Agentensor optimizer name |
| objective | object | Metric name and direction |
| parameters | object | Prompt and hyper-parameters for the AI node |
| metrics | object | Evaluation metrics captured per candidate |
| version | string | Version tag for persisted parameters |
| status | string | Run status (running, completed, failed) |

Example payload persisted for a tuned parameter set:

```json
{
  "version": "v3",
  "node_id": "ai-node-123",
  "parameters": {
    "system_prompt": "Concise assistant with chain-of-thought hidden.",
    "temperature": 0.3,
    "top_p": 0.9
  },
  "metrics": {
    "primary": 0.87,
    "guardrail_safety": 1.0
  },
  "metadata": {
    "optimizer": "bayesian",
    "run_id": "run-456",
    "created_at": "2025-12-16T00:00:00Z",
    "checksum": "abc123"
  }
}
```

## Security Considerations

- Enforce workflow- and node-level authorization on optimization and promotion endpoints.
- Store prompts and parameters in encrypted storage; redact secrets from logs.
- Validate optimizer payloads and evaluation outputs to prevent injection or malformed configs.
- Rate-limit optimization triggers and enforce per-user quotas.

## Performance Considerations

- Optimization runs are async/background; production inference remains fast by caching approved parameters.
- Batch evaluation outputs to reduce optimizer overhead; cap iterations and runtime per run.
- Cache parameter fetches in the orchestrator to avoid repeated storage hits.

## Testing Strategy

- **Unit tests:** Optimizer bridge transformations, parameter persistence logic, schema validation.
- **Integration tests:** End-to-end optimization flow with mock evaluation outputs; promotion/rollback behavior.
- **Manual QA checklist:** Trigger optimization on staging workflow, verify metrics improve, promote and rollback parameters, confirm production inference uses promoted version.

## Rollout Plan

1. Phase 1: Internal/flag-gated deployment of merged agentensor package and optimizer hooks in dev/staging.
2. Phase 2: Limited pilot with workflows that have existing evaluation coverage; collect metrics and tune defaults.
3. Phase 3: General availability with documentation, observability dashboards, and rollback tooling.

Feature flags and migration steps:
- Add feature flag `agentensor.optimization.enabled` per environment.
- Migration script to import existing agentensor code and align dependencies.
- Backfill baseline parameter versions before enabling promotion.

## Open Issues

- [ ] Finalize optimizer default selection per AI node type.
- [ ] Define retention policy for optimization artifacts and metrics.
- [ ] Confirm storage backend and encryption approach for persisted prompts.
- [ ] Align CLI ergonomics with API contracts for promotion/rollback.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-16 | Codex | Initial draft |
