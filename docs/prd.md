# Product Requirements Document

**Product** : **AIC Flow – Backend API & SDK for Workflow Automation**
**Version** : 0.2
**Author** : Shaojie Jiang, ChatGPT & Kiro
**Date** : 21 July 2025
**Reviewers** : Core Engineering & Design teams

| Rev | Date         | Author(s)                    | Notes                           |
| --- | ------------ | ---------------------------- | ------------------------------- |
| 0.1 | 1 May 2025   | Shaojie Jiang                | Initial skeleton                |
| 0.2 | 21 Jul 2025  | Shaojie Jiang, ChatGPT, Kiro| Backend-first approach pivot    |

---

## 1 · Overview

### 1.1 Problem Statement

Developers and technical teams struggle to build robust, scalable workflow automation systems that can seamlessly integrate AI agents, data sources, and third-party services.
Existing solutions are either **too low-level** (requiring extensive infrastructure code—e.g., raw LangGraph) or **too rigid** (limited extensibility and AI capabilities—e.g., traditional workflow engines). There's a gap for a **developer-first platform** that provides both power and productivity.

### 1.2 Goal

Deliver a **powerful backend API and SDK** that enables developers to programmatically design, test, and run complex automations—including AI-centric tasks—with a code-first approach, while laying the foundation for future low-code interfaces.

- **API-first architecture** with comprehensive REST endpoints and WebSocket streaming
- **Code-first depth** via **LangGraph**, first-class **Python** SDK support
- **Extensible node system** with proven patterns for data ops, AI agents, and long-running jobs
- **Developer-friendly** with clear documentation, examples, and testing tools

### 1.3 Scope (v1)

- **REST API** for workflow management (CRUD, execution, monitoring)
- **WebSocket streaming** for real-time workflow execution updates
- **5 Essential node types**: Python Code, AI Agent, HTTP Request, Webhook, Cron, If/Else
- **Workflow validation** with schema and dependency checking
- **Error handling** with graceful failures, retries, and clear error reporting
- **Basic security** with API key authentication and input sanitization
- **Developer SDK** with Python client library and examples

### 1.4 Out-of-Scope (v1)

- **Frontend UI** (drag-and-drop canvas, visual workflow editor)
- **Advanced node types**: Database queries, file operations, notifications, data transforms
- **Complex control flow**: Loops (for-each, while), parallel execution
- **Enterprise features**: RBAC, OAuth, multi-tenancy, credential vault
- **Scalability features**: Celery workers, Redis caching, load balancing
- **Advanced features**: Template marketplace, plugin system, Git versioning
- JavaScript code node or JS runtime
- AI-assisted workflow generation / node suggestion
- Mobile apps (view or authoring)
- HIPAA / FedRAMP compliance

---

## 2 · Assumptions & Constraints

- **Backend-first approach**: MVP focuses on API and SDK before UI development
- **Python-centric**: Custom nodes require Python development skills
- **API-driven architecture**: FastAPI backend with comprehensive REST endpoints
- **LangGraph foundation**: Execution engine relies on LangGraph + async processing
- **Developer audience**: Primary users are developers, DevOps engineers, and technical teams

---

## 3 · User Personas & Key Use Cases

| Persona                          | Representative Story                                                            |
| -------------------------------- | ------------------------------------------------------------------------------- |
| **Olivia** – DevOps Engineer     | "I use the Python SDK to build ETL pipelines that run on our infrastructure." |
| **Diego** – Data Scientist       | "I chain AI nodes via API calls to auto-classify and process research data."   |
| **Bao** – Backend Developer      | "I extend the node registry with custom nodes that wrap our internal APIs."    |
| **Ming** – ML Engineer           | "I build evaluation loops using the workflow API for complex AI pipelines."    |
| **Arun** – Platform Engineer     | "I deploy AIC Flow as a service and create reusable workflow templates."       |
| **Sarah** – Integration Specialist| "I use REST endpoints to integrate workflows with our existing systems."      |
| **Alex** – Automation Developer  | "I programmatically create and manage workflows using the Python client."      |

---

## 4 · Functional Requirements

### 4.1 Workflow Editor

- **Workflow CRUD**: Create, read, update, delete workflows via REST endpoints
- **Execution API**: Start, stop, monitor workflow executions with real-time status
- **Node Management**: Register, discover, and configure node types programmatically
- **Python SDK**: High-level client library for workflow creation and management
- **Validation**: Server-side workflow validation (type checking, dependency resolution)
- **Streaming**: WebSocket endpoints for real-time execution updates and logs

### 4.2 Fundamental Node Types

- **Python Code**: Execute arbitrary Python code with state access ✅ *implemented*
- **AI Agent**: LangGraph-based agent with tool support ✅ *implemented*
- **HTTP Request**: Combined GET/POST requests with authentication support
- **Webhook**: Receive HTTP requests to trigger workflow execution
- **Cron**: Schedule workflows using cron expressions
- **If/Else**: Basic conditional branching based on state values

*Note: Additional node types (DB queries, file operations, loops) deferred to v1.1+*

### 4.3 Workflow Management

- **Schema validation**: Ensure workflow JSON structure is valid and well-formed
- **Dependency checking**: Detect circular references and missing node connections
- **Type checking**: Validate node input/output type compatibility
- **Graceful failure handling**: Isolated node failures don't crash entire workflow
- **Retry mechanisms**: Configurable exponential backoff for transient failures
- **Error reporting**: Detailed error messages with context and debugging information

### 4.4 Execution Engine

- **API key authentication**: Simple token-based access control for all endpoints
- **Input sanitization**: Prevent code injection in Python nodes and user inputs
- **Rate limiting**: Basic request throttling to prevent abuse and DoS attacks
- **Secure execution**: Sandboxed Python code execution with resource limits

### 4.5 Integrations & Plugins

- **LangGraph-based execution**: Async workflow processing with state management
- **SQLite persistence**: Workflow definitions, execution history, and checkpoints
- **WebSocket streaming**: Real-time execution updates and logs
- **Basic monitoring**: Execution status, duration, and error tracking

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
| Adoption     | Active developers    | ≥ 500         |
|              | API calls            | ≥ 100 000 / mo|
|              | Workflow executions  | ≥ 10 000 / mo |
| Technical    | Test coverage        | > 80 %        |
|              | API response time    | < 200 ms      |
|              | SDK adoption         | ≥ 200 installs/mo |
| Commercial   | Enterprise inquiries | ≥ 10 / mo     |
| Satisfaction | NPS                  | > 40          |

---

## 8 · Dependencies

| Layer         | Key Tech                                              | Purpose                |
| ------------- | ----------------------------------------------------- | ---------------------- |
| Backend       | FastAPI, Pydantic, LangGraph, SQLite                  | Core API & engine      |
| SDK           | Python 3.12+, asyncio, httpx, websockets             | Client library         |
| DevOps        | Docker, Kubernetes, Helm                              | Packaging & deployment |
| Observability | OpenTelemetry, Prometheus                             | Tracing & metrics      |
| Auth          | API Keys, JWT (OAuth 2 in v2)                        | API authentication     |

---

## 9 · Milestones & Timeline

| Phase       | Dates          | Deliverables                                                           | Exit Criteria                             |
| ----------- | -------------- | ---------------------------------------------------------------------- | ----------------------------------------- |
| **MVP**     | May – Jun 2025 | REST API; 6 essential nodes; validation; error handling; security; SDK | Demo: create & run workflow via API ≤ 10 min |
| **Beta**    | Jul – Sep 2025 | Extended node library; persistence; monitoring; developer docs         | 50 developer users; comprehensive examples    |
| **GA 1.0**  | Oct – Dec 2025 | Production-ready API; plugin system; performance optimization          | API uptime ≥ 99.9%; load testing passed      |
| **Post-GA** | 2026+          | Frontend UI; visual editor; credential vault; enterprise features      | Roadmap refresh Q1 2026                       |

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
