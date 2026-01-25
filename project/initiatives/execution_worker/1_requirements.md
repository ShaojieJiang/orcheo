# Requirements Document

## METADATA
- **Authors:** Codex
- **Project/Feature Name:** Execution Worker (Celery + Redis)
- **Type:** Enhancement
- **Summary:** Add a production-grade execution worker to process pending workflow runs
  asynchronously, using Celery with Redis as the broker and systemd for deployment.
- **Owner (if different than authors):** Shaojie Jiang
- **Date Started:** 2025-12-22

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| Prior Artifacts | N/A | N/A | N/A |
| Design Review | N/A | N/A | N/A |
| Design File/Deck | N/A | N/A | N/A |
| Eng Requirement Doc | N/A | N/A | N/A |
| Marketing Requirement Doc (if applicable) | N/A | N/A | N/A |
| Experiment Plan (if applicable) | N/A | N/A | N/A |
| Rollout Docs (if applicable) | N/A | N/A | N/A |

## PROBLEM DEFINITION
### Objectives
Introduce an execution worker that transitions pending runs to completion without
requiring an interactive WebSocket client. Keep webhook latency low while
ensuring runs progress to succeeded/failed in the database.

### Target users
Operators running Orcheo in production who need webhook and cron runs to execute
automatically.

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| Operator | run workflow executions asynchronously | webhooks return fast and runs still complete | P0 | Pending runs are picked up and executed by a worker |
| Operator | see updated run status in CLI | I can confirm execution outcomes | P0 | `orcheo workflow show` reflects running/succeeded/failed |
| Operator | deploy with systemd | I can manage uptime consistently | P1 | systemd unit examples are provided |

### Context, Problems, Opportunities
Webhook-triggered runs are currently enqueued and remain pending unless a client
executes them over WebSocket or via CLI. This blocks production workflows (e.g.,
Slack replies) and reduces observability. A dedicated execution worker addresses
this gap with minimal changes to request handling.

### Product goals and Non-goals
Goals:
- Execute pending runs in the background using Celery and Redis.
- Update run status in the database so CLI and UI reflect execution outcomes.
- Keep execution semantics best effort (no retries or dedupe guarantees).

Non-goals:
- Exactly-once execution guarantees.
- Distributed tracing or advanced retry policies in this phase.
- Brokerless or in-process execution.
- Automatic recovery for runs left in non-terminal states after worker crashes (manual recovery via CLI is acceptable for v1; automatic recovery is a future consideration).

## PRODUCT DEFINITION
### Requirements
P0:
- Worker consumes pending runs and executes workflows asynchronously.
- Run status transitions are persisted (pending -> running -> succeeded/failed).
- Redis is used as the Celery broker.
- Systemd deployment target documentation.

P1:
- Minimal operational logging for worker lifecycle and run transitions.
- Basic configuration knobs (poll interval, concurrency, queue name).
- Health check endpoint for worker liveness monitoring.

### Designs (if applicable)
N/A

## TECHNICAL CONSIDERATIONS
### Architecture Overview
The FastAPI server continues to enqueue runs. A Celery worker listens on a Redis
queue and executes runs by invoking the workflow execution path, persisting
status updates to the database. Cron dispatch remains a separate scheduler
responsible for creating runs.

### Technical Requirements
- Celery configured with Redis broker.
- Worker tasks load run data, execute workflows, and update run status.
- Best-effort semantics: no dedupe, minimal retry configuration.
- systemd unit files for API, worker, and Celery Beat scheduler.

## LAUNCH/ROLLOUT PLAN
### Success metrics
| KPIs | Target & Rationale |
|------|--------------------|
| [Primary] % pending runs older than 5 minutes | 0% under normal load |
| [Secondary] webhook latency | unchanged from baseline |
| [Guardrail] worker crash rate | < 1 per day |

### Rollout Strategy
Deploy worker alongside API on a single node via systemd, validate run statuses,
then scale worker concurrency as needed.

## HYPOTHESIS & RISKS
Hypothesis: Offloading execution to a background worker will allow webhooks to
return immediately while still completing runs. Confidence is high because the
worker directly consumes pending runs and updates status in the database.

Risks: Best-effort semantics can drop runs on worker crash, and Redis outages
stall execution. Mitigation: add minimal monitoring and alerts for queue depth
and worker uptime.

## APPENDIX
