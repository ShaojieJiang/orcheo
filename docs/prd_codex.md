# Product Requirements Document (Codex)

- **Product**: Orcheo — Visual + API Workflow Automation
- **Version**: 1
- **Author**: Shaojie Jiang, Codex CLI
- **Date**: 2025-08-28
- **Audience**: Shaojie Jiang, Codex CLI

| Rev | Date       | Notes                                   |
| --- | ---------- | --------------------------------------- |
| 1 | 2025-08-28 | Initial PRD aligned to visual automation vision |

---

## 1. Overview

### 1.1 Problem
Teams need to automate data and AI workflows that integrate APIs, LLM agents, and services. Existing options are either too rigid (classic workflow engines) or too low-level (DIY agent graphs). We need a developer-first stack that combines a visual editor with a robust backend runner and strong observability.

### 1.2 Vision
Orcheo is a visual + programmable workflow platform:
- Canvas editor (React + react-flow) for building flows using predefined nodes.
- Backend runner executing flows as LangGraph graphs with real-time streaming.
- Persistent storage for workflows, credentials, API keys, and executions.
- Multiple trigger types (cron, webhooks) with secure, reliable semantics.
- Python SDK for code-first authoring and full API parity.

### 1.3 Goals
- Developer-first: visual editor and Python SDK provide equal capabilities.
- Safe-by-default: credentials, untrusted code, and triggers get strong guardrails.
- Extensible: predictable node model, pluggable tools, clear versioning.
- Observable: streaming events, logs, traces, and reproducible runs.

### 1.4 Non-Goals (v1)
- Drag-and-drop credential vault UI beyond basics (advanced secret management later).
- Complex control flow (loops/parallel/map-reduce). Basic If/Else only in v1.
- Distributed at-least-once queue semantics; single-runner semantics in v1.
- JS runtime for user code nodes (Python-only in v1).

---

### 1.5 Competitive Landscape

- n8n: general-purpose visual automation tool. Orcheo focuses on a Python-first SDK, LangGraph-based execution, AI-native nodes, and deep observability (WS events, checkpoints) for developer workflows.
- Zapier/Make: no/low-code automation platforms. Orcheo targets developer-centric, self-hosted use cases with code-level extensibility and secure Python execution.
- Apache Airflow/Dagster: data/ETL orchestrators. Orcheo emphasizes event-driven automations, real-time streaming, and interactive debugging over batch pipelines.
- Temporal/Cadence: durable execution engines. Orcheo provides a higher-level canvas + SDK experience and simpler onboarding; future integration is possible.
- LangGraph (direct use): graph library for agents. Orcheo adds storage, triggers, credential management, streaming, and a visual editor on top of graph compilation.

---

## 2. Personas & Use Cases

| Persona | Goals |
| ------ | ----- |
| DevOps Engineer | Automate scheduled data/infra jobs and monitor runs. |
| Backend Developer | Orchestrate API calls and internal services using HTTP + credentials. |
| ML/AI Engineer | Build/trace AI agent flows and data labeling/ETL steps. |
| Integration Specialist | Connect systems via webhooks and cron triggers reliably. |

Key use cases:
- API → transform → AI agent → notify
- Inbound webhook → validate/sign → enrich via HTTP → persist
- Nightly cron → fetch → batch process via Python code → index

---

## 3. Scope (v1)

### 3.1 Frontend (Canvas)
- React app using `react-flow` for node/edge editing.
- Node palette, search, drag/drop, connect, delete.
- Node inspector panel: configure inputs, auth, and options.
- Client-side validation: missing connections, type mismatches.
- Save/Load workflows via backend API; version label on save.

### 3.2 Node Library (Initial)
- Triggers: Webhook Trigger, Cron Trigger.
- Control: If/Else (expression or state predicate).
- Actions: HTTP Request, Python Code, AI Agent (LangGraph Agent with tool calls).
- Utils: Set Variable (patch state), Delay (sleep) [optional if trivial].

### 3.3 Backend (Runner + API)
- Translate workflow JSON → LangGraph graph; execute asynchronously.
- REST APIs for workflows, credentials, API keys, triggers, nodes catalog, and executions.
- WebSocket streaming for execution events (node_start, node_end, log, state, error).
- Persistence: workflows, versions, credentials (encrypted), api keys, executions, logs, checkpoints.
- Triggers: secure webhook endpoints; cron scheduler.
- Python SDK for programmatic authoring/management and streaming.

Out of scope v1 but planned:
- DB/File nodes, notifications, parallel branches, loops, retry policies per edge, plugin marketplace.

---

## 4. Architecture

### 4.1 High Level
- Frontend: React + `react-flow` + TypeScript; talks to FastAPI over REST/WS.
- Backend: FastAPI + Pydantic; LangGraph-based runner; SQLite for MVP persistence.
- Workers: In-process async worker for v1; pluggable queue/external workers post-v1.

### 4.2 Data Flow
1) User creates/edits workflow on canvas → saves via API.
2) Execution starts via API/cron/webhook → runner compiles to LangGraph and executes.
3) Runner emits events to persistence and WS streams; credentials injected at node runtime.
4) On completion/failure, execution status and artifacts stored for debugging/tracing.

---

## 5. Domain Model (v1)

- Workflow: { id, name, version, nodes[], edges[], created_at, updated_at, tags[] }
- Node: { id, type, name, inputs{}, outputs{}, config{}, credentials_ref?, ui{} }
- Edge: { id, source_node_id, target_node_id, condition? }
- Execution: { id, workflow_id, workflow_version, status, started_at, completed_at?, error?, stats{}, trigger{} }
- Event: { id, execution_id, ts, type, payload } // streamed + stored (bounded)
- Checkpoint: { id, execution_id, node_id, ts, state_snapshot }
- Credential: { id, name, type, data_encrypted, created_at, updated_at, owner_scope }
- ApiKey: { id, name, prefix, hash, scopes[], created_at, last_used_at }

Notes:
- Credentials encrypted at rest with app-level KMS key; access only by nodes referencing credential id.
- Event retention policy configurable; checkpoints stored at key boundaries (node_end or explicit).

---

## 6. API (Summary)

Authentication: Bearer API key. Idempotency: `Idempotency-Key` supported for mutation endpoints.

### 6.1 Workflows
- POST `/workflows` — create
- GET `/workflows/{id}` — fetch
- PUT `/workflows/{id}` — update
- DELETE `/workflows/{id}` — delete (soft-delete optional)
- GET `/workflows` — list with filters: `q`, `tag`, `page`, `limit`
- POST `/workflows/{id}/versions` — finalize current draft → new version
- GET `/workflows/{id}/versions` — list versions

### 6.2 Executions
- POST `/executions` — start by `workflow_id` or inline `workflow` JSON; optional `input`
- GET `/executions/{id}` — status + summary
- POST `/executions/{id}/cancel` — cancel in-flight
- GET `/executions` — list by `workflow_id`, `status`, `page`, `limit`
- WS `/executions/{id}/stream` — server-sent events over WebSocket

### 6.3 Nodes Catalog
- GET `/nodes` — built-in node types and schemas

### 6.4 Credentials
- POST `/credentials` — create (encrypted), validates schema per `type`
- GET `/credentials/{id}` — fetch metadata (no secrets); `reveal` only with scope policy
- PUT `/credentials/{id}` — rotate/update
- DELETE `/credentials/{id}` — revoke
- GET `/credentials` — list

### 6.5 API Keys
- POST `/api-keys` — create; returns `prefix` + `secret_once`
- GET `/api-keys` — list; show only metadata and `prefix`
- DELETE `/api-keys/{id}` — revoke

### 6.6 Triggers
- POST `/triggers/cron` — create cron schedule bound to workflow/version
- DELETE `/triggers/cron/{id}` — remove cron
- POST `/triggers/webhook` — create webhook endpoint (returns public URL, signing secret)
- DELETE `/triggers/webhook/{id}` — remove webhook
- POST `/<tenant>/hooks/{token}` — inbound webhook invoke (HMAC or token auth)

---

## 7. Node Specifications (v1)

Common behavior
- Inputs/Outputs: Structured JSON values; types documented in catalog schemas.
- Errors: Node error surfaces in execution events; retry policy inherited from workflow default (v1: global retry).
- Timeouts: Per-node timeout with default (e.g., 60s HTTP, 120s AI, 30s Python).
- Logging: Nodes can emit structured logs (captured and streamed).

Nodes
- Webhook Trigger: Validates signature (HMAC SHA-256), captures headers/body, dedup via idempotency key.
- Cron Trigger: Quartz-like cron expr, timezone, misfire policy (skip/queue) configurable per trigger.
- HTTP Request: Method, URL, headers, body, auth (Bearer/API key), retries (5xx/429), max payload size.
- Python Code: Executes restricted code with state access. Limits: CPU, memory, wall time. Allowed imports allowlist. No filesystem/network by default (configurable per workspace).
- AI Agent: LangGraph agent with tools. Config: model, temperature, max tokens, tools list. Budgeting: token/time caps, provider retry matrix. PII redaction in logs.
- If/Else: Boolean expression language against state; validated server-side.
- Set Variable: Patch workflow state with constant or expression.

---

## 8. Execution Semantics

- Determinism: Best-effort; record tool I/O and prompts for replay. External calls are not replayed unless mocked.
- Idempotency: Execution start supports client-supplied idempotency key to prevent duplicates.
- Retries: Global defaults (max_attempts, backoff_jitter) with per-node overrides post-v1.
- Cancellation: Cooperative; runner sends cancel signals and marks final state.
- Concurrency: Per-workflow concurrent runs limit; per-trigger rate limits.
- Checkpointing: After each node completion; state snapshot stored to resume/replay.

---

## 9. Security & Compliance

- Auth: API keys (prefix + hash at rest), scopes per key (workflows:read/write, executions:run, credentials:manage, triggers:manage).
- Rate limiting: Per key and per IP; burst + sustained.
- Credentials: AES-256-GCM at rest; server-only decrypt in runner; strict scoping and audit logs.
- Webhooks: HMAC signatures, timestamp freshness window, replay protection.
- Code execution: Python sandboxes with resource limits; deny network/files by default; feature flags to allow.
- Audit: Record key operations (create/update/delete) for workflows, credentials, and keys.
- Privacy: Redact secrets in logs and streams.

---

## 10. Observability

- Events: `node_start`, `node_end`, `log`, `error`, `state_change` stream via WS and persisted.
- Tracing: OpenTelemetry spans per node and external calls with correlation IDs.
- Metrics: Execution latency, success/failure rates, queue times, trigger latencies.
- Logs: Structured JSON logs with execution_id and node_id.

---

## 11. SDK (Python, v1)

- Client: Auth, pagination, retries, idempotency keys.
- Workflow Builder: Local schema validation, compile to workflow JSON.
- Execution API: Start/cancel, await completion, stream events, capture logs.
- Credentials/API Keys: CRUD utilities with secure input patterns.
- Versioning: Generated from OpenAPI 3.1 spec with hand-written helpers.

---

## 12. Non-Functional Requirements

- Performance: p95 < 200 ms for `GET /workflows/{id}` and `POST /executions` enqueue; stream latency < 1s.
- Throughput: ≥ 25 node execs/sec per worker (HTTP mix), ≥ 5/sec for AI nodes.
- Availability: 99.9% monthly (MVP in single region, excludes maintenance).
- Coverage: ≥ 95% project and 100% diff coverage; type-check clean.
- Security: OWASP Top 10 controls; secrets redaction; dependency scanning.
- Persistence: SQLite MVP; migration path to Postgres; WAL mode enabled.

---

## 13. Milestones

| Phase | Dates | Deliverables | Exit Criteria |
| --- | --- | --- | --- |
| M0 Tech Spike | 1–2 w | Canvas skeleton, node palette; runner POC converting simple flow → LangGraph; WS stream mock | Demo triggers node_start/node_end on toy flow |
| M1 MVP | 3–5 w | Workflows CRUD; Executions; WS streaming; Webhook/Cron triggers; Credentials & API keys; Nodes: Webhook, Cron, HTTP, If/Else, Python, AI Agent | Create, trigger, observe, and debug a flow end-to-end |
| M2 Beta | 4–6 w | Execution viewer, checkpoints, replay; improved HTTP auths; Python sandbox hardening; SDK polish; docs/examples | 50 external users run 200+ executions/day |
| GA 1.0 | 6–8 w | Stability, scalability pass; Postgres option; rate limits; tracing dashboards | 99.9% uptime month; load test passes |

---

## 14. Risks & Mitigations

- Untrusted Code Execution: High impact → sandbox, resource limits, network/files default deny, explicit allowlists.
- LangGraph Drift: Medium → abstract compilation layer, compatibility tests.
- Webhook Abuse/DoS: Medium → HMAC, rate limits, WAF guidance, payload caps.
- State/Schema Evolution: Medium → versioned workflow format, migrations, backward-compat checks.
- Secret Handling Errors: High → encryption, e2e tests, redaction, least-privilege design.

---

## 15. Open Questions

- Expression Language: Adopt JSONata/JMESPath vs. simple Python-safe eval?
- Sandbox Implementation: In-process limits vs. container/Firecracker in v1?
- Multi-Tenancy: Single-tenant deploys first; when to add tenancy boundaries?
- Parallelism: Introduce parallel/merge in v1.1 or later?

---

## 16. Appendix

- OpenAPI 3.1 will be source-of-truth for API + SDK generation.
- Workflow JSON schema will be versioned and validated on save/execute.
- React-flow graph → normalized workflow model → LangGraph compilation boundary documented in code.

> Living document. Updates require reviewer sign-off and revision entry above.
