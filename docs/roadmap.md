# Orcheo Roadmap

This roadmap consolidates Orcheo's milestone sequencing and task backlog in a single place so planning and execution stay aligned.

## v1.0 Roadmap Summary
1. **Milestone 1 – Platform Foundation**: Lock in LangGraph architecture, scaffold repos, and ship baseline developer tooling.
2. **Milestone 2 – Backend Orchestration & Triggers**: Deliver the dual-mode execution backend, workflow APIs, and reliable trigger layer.
3. **Milestone 3 – Credential Vault & Security**: Launch the encrypted credential vault, validation flows, and security hardening.
4. **Milestone 4 – Visual Designer Experience**: Build the React Flow canvas, workflow operations, and live execution monitoring.
5. **Milestone 5 – Node Ecosystem & Integrations**: Provide launch-ready trigger, AI, data, storage, and utility nodes with docs/tests.
6. **Milestone 6 – Observability, Testing & Launch Prep**: Instrument runtime visibility, finalize metrics, and prep the beta rollout.

## Milestone Details
### Milestone 1 – Platform Foundation
- [x] Finalize LangGraph-centric architecture decisions, persistence layer, and hosting model supporting both canvas and SDK. See [Milestone 1 Task 1](./milestone1_task1.md) for the detailed outcomes.
  - [x] Capture deployment recipes for local and hosted environments ([deployment guide](./deployment.md)).
  - [ ] Extend configuration to cover vault-managed credential settings.
  - [ ] Wire Postgres persistence checks into CI once infrastructure is ready.
- [ ] Scaffold repositories for FastAPI backend, Python SDK package, and React canvas app, including CI, linting, and coverage automation.
- [ ] Define workflow data models (graphs, versions, runs, credential metadata) with encryption hooks and audit logging.
- [ ] Establish developer tooling: local dev containers, `uv` scripts, seed environment variables, and sample flows covering both user paths.

### Milestone 2 – Backend Orchestration & Triggers
- [ ] Implement Python SDK with typed node authoring, local execution parity, and deployment hooks that sync with the server.
- [ ] Build FastAPI services for workflow CRUD, execution lifecycle, version diffing, and WebSocket streaming telemetry.
- [ ] Deliver trigger layer covering webhook validation (verbs, filtering, rate limits), cron scheduler (timezone aware, overlap guards), manual/batch runs, and retry policies.
- [ ] Add execution engine support for loops, branching, parallelization, run history, and replay/debug APIs.

### Milestone 3 – Credential Vault & Security
- [ ] Ship AES-256 encrypted credential vault with per-workflow scoping, rotation policies, and masked logging.
- [ ] Implement OAuth refresh flows, credential validation/testing, and health checks to block misconfigured automations.
- [ ] Create credential templates and UI/API for secure storage, token issuance, and secret governance alerts.
- [ ] Run security reviews, penetration tests, and threat modeling across vault, triggers, and execution surfaces.

### Milestone 4 – Visual Designer Experience
- [ ] Build React Flow canvas tooling: pan/zoom/minimap, grid snapping, undo/redo, node search/filtering, duplication, styling, and collapsible configuration panels.
- [ ] Implement workflow operations: save/load, JSON import/export, template onboarding, shareable exports, and version diff viewer.
- [ ] Integrate credential management UI, reusable sub-workflows, and publish-time validation.
- [ ] Connect canvas executions to backend WebSocket streams for live status, token metrics, and run replay hooks.

### Milestone 5 – Node Ecosystem & Integrations
- [ ] Deliver trigger nodes (Webhook, Cron, Manual, HTTP Polling) with both UI and SDK parity.
- [ ] Implement AI/LLM nodes (OpenAI, Anthropic, Custom Agent, Text Processing) with prompt management and latency guardrails.
- [ ] Build Data & Logic nodes (HTTP Request, JSON Processing, Data Transform, If/Else, Switch, Merge, Set Variable) plus Storage/Communication nodes (MongoDB, PostgreSQL, SQLite, Email, Slack, Telegram, Discord).
- [ ] Add utility nodes (Python/JavaScript execution sandbox, Delay, Debug, Sub-workflow orchestration) with tests, docs, and templates.

### Milestone 6 – Observability, Testing & Launch Prep
- [ ] Instrument execution viewer with per-step prompts/responses, token metrics, artifact downloads, and monitoring dashboards.
- [ ] Establish success metrics tracking (uv installs, GitHub stars, quickstart completion rate, failure backlog) and analytics pipelines.
- [ ] Produce onboarding docs, templates, SDK examples, closed-beta playbook, and feedback/A-B testing loops for AI node recommendations.
- [ ] Run end-to-end reliability tests, load tests on React Flow canvas, finalize beta rollout plan, and prepare Phase 1/Phase 2 regional launch gates.

## Post v1.0 Outlook
- [ ] **v1.1 Advanced Features:** Team workspaces, advanced debugging, workflow marketplace.
- [ ] **v1.2 Enterprise:** SSO, audit logging, advanced monitoring, on-prem deployment.
- [ ] **v2.0 AI-Enhanced:** AI-assisted workflow creation, smart node recommendations, auto error resolution, natural language queries.

---

_Last updated: 2025-09-28_
