# Design Document

## For Execution Worker (Celery + Redis)

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-22
- **Status:** Approved

---

## Overview

This design introduces a background execution worker that processes pending
workflow runs asynchronously. The worker is built on Celery with Redis as the
broker and is deployed via systemd alongside the existing FastAPI service. The
primary goal is to transition runs from pending to completion without requiring
interactive WebSocket clients, while keeping webhook latency low.

Execution semantics are best effort: if a worker crashes mid-run, the run may
remain in a non-terminal state until manually retried. Status updates are stored
in the database so CLI commands and UI can reflect running/succeeded/failed.

Operational recovery is manual in this phase. Operators can identify stuck runs
via the CLI and re-run them explicitly once the worker is healthy.

## Components

- **API Server (FastAPI)**
  - Responsibility: Accept webhooks/cron dispatches and enqueue workflow runs.
  - Dependencies: Database persistence layer for run records.

- **Execution Worker (Celery)**
  - Responsibility: Consume pending runs, execute workflows, update run status.
  - Dependencies: Redis broker, database access, workflow execution module.

- **Redis Broker**
  - Responsibility: Queue run execution tasks for worker consumption.
  - Dependencies: None (external service).

- **Scheduler (Celery Beat)**
  - Responsibility: Trigger cron dispatch to enqueue scheduled runs.
  - Dependencies: API endpoint `/triggers/cron/dispatch` if using HTTP trigger.

## Request Flows

### Flow 1: Webhook-triggered execution
1. Slack sends webhook to `/api/workflows/{id}/triggers/webhook`.
2. API validates request and creates a pending run in the database.
3. API enqueues a Celery task referencing the run ID.
4. Worker consumes task, marks run as running, executes workflow.
5. Worker updates run status to succeeded/failed and persists results.

### Flow 2: Scheduled execution
1. Scheduler invokes cron dispatch (Celery Beat + HTTP call).
2. API creates pending runs for due schedules.
3. API enqueues Celery tasks for each run ID.
4. Worker executes each run and updates status.

## API Contracts

No new public HTTP APIs are required. The worker operates on existing workflow
execution primitives and run records. The cron dispatch endpoint
(`/api/triggers/cron/dispatch`) already exists.

If cron is triggered via HTTP (API routes are prefixed with `/api`):

```
POST /api/triggers/cron/dispatch
Headers:
  Authorization: Bearer <token> (if enabled)
Body:
  { "now": "2025-12-22T10:00:00Z" } (optional)
```

## Data Models / Schemas

Run status transitions (persisted in DB):

| Field | Type | Description |
|-------|------|-------------|
| status | string | pending -> running -> succeeded/failed |
| started_at | datetime | Set by worker when execution begins |
| finished_at | datetime | Set by worker on completion |
| error | string | Optional error summary on failure |

### Implementation Details

**Celery Task Signature:**
```python
# apps/backend/src/orcheo_backend/worker/tasks.py
from celery import Task
from orcheo_backend.worker.celery_app import celery_app

@celery_app.task(bind=True, max_retries=0)
def execute_run(self: Task, run_id: str) -> dict:
    """
    Execute a workflow run by ID.

    Args:
        run_id: UUID of the run to execute

    Returns:
        dict with keys: status (succeeded/failed), finished_at, error (optional)
    """
    # Implementation will:
    # 1. Load run from database
    # 2. Update status to 'running' and set started_at
    # 3. Execute workflow via existing execution path (import from orcheo core)
    # 4. Update status to succeeded/failed with finished_at
    # 5. Return execution result
    pass
```

**API Enqueue Mechanism:**
```python
# apps/backend/src/orcheo_backend/app/routers/triggers.py (webhook/cron endpoints)
from orcheo_backend.worker.tasks import execute_run

async def webhook_handler(workflow_id: str, payload: dict):
    # Create pending run in database
    run = await create_run(workflow_id, trigger_type="webhook", payload=payload)

    # Enqueue Celery task
    execute_run.delay(str(run.id))

    # Return immediately
    return {"run_id": str(run.id), "status": "pending"}
```

**Celery App Configuration:**
```python
# apps/backend/src/orcheo_backend/worker/celery_app.py
from celery import Celery
import os

celery_app = Celery(
    "orcheo-backend",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=None,  # No result backend needed for fire-and-forget
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # Acknowledge after execution completes
    worker_prefetch_multiplier=1,  # Fetch one task at a time for fairness
)
```

**Status Update Race Condition Handling:**

If a run is already in `running` state when the worker picks it up (e.g., duplicate task or manual CLI execution), the worker should:
1. Check current status before updating to `running`
2. Skip execution if status is not `pending`
3. Log a warning about the duplicate execution attempt

## Security Considerations

- Reuse existing authentication/authorization policies for cron dispatch.
- Ensure worker uses least-privilege credentials for database access.
- Avoid logging sensitive payloads; redact secrets from execution logs.

## Performance Considerations

- Worker concurrency should be tuned to prevent overwhelming external services.
- Redis broker should be configured with AOF persistence (`appendfsync everysec`)
  for a good balance of durability and performance in production environments.
- Use backpressure controls (queue length alerts) to detect overload.

## Testing Strategy

- **Unit tests**: task dispatch and run status transitions.
- **Integration tests**: enqueue run -> worker executes -> status updated.
- **Manual QA checklist**: webhook -> Slack reply; cron dispatch -> run executes.

## Rollout Plan

1. Phase 1: Deploy Redis and a single worker instance; verify run status updates.
2. Phase 2: Enable cron scheduler; validate scheduled runs complete.
3. Phase 3: Scale worker concurrency and add monitoring for queue depth.

## Future Considerations

- **Stale run recovery**: Implement a mechanism to detect runs stuck in `running`
  state after worker crashes and automatically retry or mark them as failed. This
  could be a periodic sweep that checks `started_at` against a configurable timeout.

## Open Issues

- [ ] Confirm error handling strategy for best-effort semantics.
- [ ] Define retention for failed run diagnostics.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-22 | Codex | Initial draft |
