# Product Requirements Document

**Product** : **AIC Flow – Visual Workflow Automation Platform**
**Version** : 0.1
**Author** : Shaojie Jiang & ChatGPT
**Date** : 2 May 2025
**Reviewers** : Core Engineering & Design teams

| Rev | Date       | Author(s)     | Notes            |
| --- | ---------- | ------------- | ---------------- |
| 0.1 | 1 May 2025 | Shaojie Jiang | Initial skeleton |

---

## 1 · Overview

### 1.1 Problem Statement

Technical _and_ non-technical users struggle to connect heterogeneous data sources, AI agents, and third-party services without writing glue code.
Existing tools are either **code-first** (powerful but costly to build, deploy, and maintain—e.g., LangGraph) or **workflow-first** (easy but not AI-centric—e.g., n8n). None delivers both ease-of-use _and_ developer-grade extensibility.

### 1.2 Goal

Deliver a **drag-and-drop browser-based builder** that lets users design, test, and run complex automations—including AI-centric tasks—in minutes, while remaining fully extensible for developers.

- Low-code UX powered by **React Flow**.
- Code-first depth via **LangGraph**, first-class **Python** (and virtual-env) support.
- Proven patterns for data ops, AI agents, and long-running jobs.

### 1.3 Scope (v1)

- Core workflow editor (canvas, validation, history).
- Fundamental node types (Section 4.2).
- Credential vault.
- Git-style versioning of workflows & configs.

### 1.4 Out-of-Scope (v1)

- Additional node types not listed in § 4.2.
- JavaScript code node or JS runtime.
- AI-assisted workflow generation / node suggestion.
- Mobile apps (view or authoring).
- Enterprise SSO & multi-tenant admin.
- Marketplace with paid plugins.
- HIPAA / FedRAMP compliance.

---

## 2 · Assumptions & Constraints

- Custom nodes require both React/TypeScript (front-end) and Python (back-end) skills.
- Single-page app (React 18 + Vite) communicates with a FastAPI back-end.
- Execution engine relies on LangGraph + Celery workers.

---

## 3 · User Personas & Key Use Cases

| Persona                          | Representative Story                                                            |
| -------------------------------- | ------------------------------------------------------------------------------- |
| **Beth** – Business Analyst      | “I drag-and-drop CRM + email nodes to send weekly performance reports—no code.” |
| **Maya** – Marketing Manager     | “I use pre-built connectors to keep campaign lists in sync.”                    |
| **Olivia** – Ops Engineer        | “I schedule nightly ETL pipelines so BI dashboards are ready by 06:00.”         |
| **Diego** – Data Scientist       | “I chain AI nodes and webhooks to auto-classify inbound tickets.”               |
| **Arun** – Automation Consultant | “I package reusable sub-workflows for clients via the marketplace.”             |
| **Bao** – Backend Dev            | “I write Python SDK nodes that wrap our proprietary APIs.”                      |
| **Ming** – ML Engineer           | “I build evaluation loops for complex AI pipelines.”                            |

---

## 4 · Functional Requirements

### 4.1 Workflow Editor

- Drag-and-drop canvas (pan, zoom, snap-to-grid).
- Live validation (type errors, dangling edges).
- Undo/redo ≥ 20 steps, multi-select, inline search.
- Mini-map; folder-style workflow organisation.
- Sub-workflow collapse/expand.

### 4.2 Fundamental Node Types

- **Sources**: REST GET, DB query, webhook, cron.
- **Sinks**: REST POST, file export, notifications.
- **Processing**: Python block, data transform, agent node.
- **Control-flow**: if/else, for-each, while.
- **Integration**: sub-workflow call, chat handler.
- **Custom**: signed plugin nodes.

### 4.3 Workflow Management

- Save, duplicate, import/export (JSON) with semantic version tags.
- Template gallery (star, download count).
- Test-run mode with breakpoints & variable inspector.
- Run history: logs, metrics, traces.

### 4.4 Execution Engine

- LangGraph runner with parallel + conditional branches.
- At-least-once delivery; retries & compensating flows.
- Live logs via WebSocket; node-level metrics (latency, throughput, error codes).

### 4.5 Integrations & Plugins

- Built-ins: HTTP, Postgres/MySQL, S3, Google Sheets, Slack, OpenAI.
- OAuth 2 credential vault (role-based access).
- Python SDK + publishing pipeline (marketplace read-only in v1).

### 4.6 Community Hub

- Discover, vote, comment on community nodes.
- Contributor leaderboard; moderation workflow.

---

## 5 · Non-Functional Requirements

| Category      | Requirement (v1)                                                     |
| ------------- | -------------------------------------------------------------------- |
| Performance   | Editor p95 interaction ≤ 200 ms; engine ≥ 50 nodes / s per worker.   |
| Scalability   | Horizontal auto-scaling; ≥ 1 000 concurrent executions, queue < 5 s. |
| Availability  | Monthly uptime ≥ 99.9 % (excl. maintenance).                         |
| Security      | OWASP Top 10, AES-256 secrets, SOC 2 roadmap.                        |
| Compliance    | GDPR DPA.                                                            |
| Observability | OpenTelemetry traces; Prometheus / Grafana dashboard.                |
| I18n          | English UI; string catalog ready for locales.                        |

---

## 6 · UX / UI

- **Design language**: Light/Dark, WCAG 2.1 AA palette.
- **Wireframes**: canvas, node inspector, console (Figma link).
- Guided 3-step onboarding + “Create Demo Flow”.
- Full shortcut reference drawer.

---

## 7 · Success Metrics (first 6 months post-GA)

| Pillar       | KPI                  | Target        |
| ------------ | -------------------- | ------------- |
| Community    | GitHub stars         | ≥ 1 000       |
|              | Active contributors  | ≥ 50 / mo     |
| Adoption     | Active workflows     | ≥ 1 000       |
|              | Workflow executions  | ≥ 10 000 / mo |
| Technical    | Test coverage        | > 80 %        |
|              | Avg response time    | < 200 ms      |
| Commercial   | Enterprise inquiries | ≥ 10 / mo     |
| Satisfaction | NPS                  | > 40          |

---

## 8 · Dependencies

| Layer         | Key Tech                                              | Purpose                |
| ------------- | ----------------------------------------------------- | ---------------------- |
| Frontend      | `@xyflow/react`, React 18, Vite                       | Canvas & build tooling |
| Backend       | FastAPI, Pydantic, LangGraph, Celery, Redis, Postgres | Core API & engine      |
| DevOps        | Docker, Kubernetes, Helm                              | Packaging & deployment |
| Observability | OpenTelemetry, Prometheus                             | Tracing & metrics      |
| Auth          | OAuth 2 / Auth0                                       | SSO, credential vault  |

---

## 9 · Milestones & Timeline

| Phase       | Dates          | Deliverables                                                           | Exit Criteria                             |
| ----------- | -------------- | ---------------------------------------------------------------------- | ----------------------------------------- |
| **MVP**     | May – Jun 2025 | Editor core; 6 node types; single-worker engine                        | Demo: build & run sample flow ≤ 15 min    |
| **Beta**    | Jul – Sep 2025 | Versioning, template gallery, marketplace (read-only), 10 integrations | 500 external beta users; error rate < 5 % |
| **GA 1.0**  | Oct – Dec 2025 | HA engine, plugin publish, RBAC                                        | Uptime ≥ 99.9 %; pass pen-test            |
| **Post-GA** | 2026+          | AI-assisted builder, team collaboration, mobile viewer                 | Roadmap refresh Q1 2026                   |

---

## 10 · Risks & Mitigations

| Risk                                   | Likelihood | Impact | Mitigation                                              |
| -------------------------------------- | ---------: | -----: | ------------------------------------------------------- |
| Under-scoped MVP features              |     Medium |   High | Strict scope lock; weekly scope review.                 |
| Performance degradation at scale       |     Medium |   High | Early load tests; autoscaling POC in Beta.              |
| Plugin security vulnerabilities        |        Low |   High | Signed plugins; automated vetting pipeline.             |
| Dependence on LangGraph roadmap        |     Medium | Medium | Abstract engine layer; fallback to native DAG executor. |
| Talent gap in dual-stack (TS + Python) |       High | Medium | Create starter templates & internal training.           |

---

## 11 · Appendices

- **A.** Figma link – wireframes and component library.
- **B.** API spec (OpenAPI 3.1) – see `/docs/openapi`.

---

> **Living Document** – Changes require a table entry above _and_ reviewer sign-off. Use Slack `#prd-aic-flow` for discussions; major decisions captured in document history.
