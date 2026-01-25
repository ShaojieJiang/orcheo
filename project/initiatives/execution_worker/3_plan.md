# Project Plan

## For Execution Worker (Celery + Redis)

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-22
- **Status:** Completed

---

## Overview

Deliver a production execution worker that processes pending runs asynchronously
using Celery with Redis as the broker. Runs update status in the database so the
CLI and UI reflect execution outcomes. Deployment target is systemd.

**Related Documents:**
- Requirements: `./1_requirements.md`
- Design: `./2_design.md`
- Deployment: `../../../docs/execution_worker/deployment.md`

---

## Milestones

### Milestone 1: Worker Foundations

**Description:** Introduce Celery worker process and task wiring for workflow
execution.

#### Task Checklist

- [x] Task 1.0: Add Celery and Redis dependencies to apps/backend/pyproject.toml
  - Dependencies: None
  - Note: Backend service owns deployment infrastructure (Celery), not orcheo core
- [x] Task 1.1: Add Redis to local dev environment (docker-compose/Makefile)
  - Dependencies: None
- [x] Task 1.2: Create Celery app configuration (apps/backend/src/orcheo_backend/worker/celery_app.py)
  - Dependencies: Task 1.0, Task 1.1
- [x] Task 1.3: Implement execute_run task in apps/backend/src/orcheo_backend/worker/tasks.py
  - Dependencies: Task 1.2
  - Note: Task imports workflow execution from orcheo core (src/orcheo/)
- [x] Task 1.4: Modify webhook/cron endpoints in apps/backend/src/orcheo_backend/app/routers/triggers.py to enqueue Celery tasks after creating runs
  - Dependencies: Task 1.3
- [x] Task 1.5: Add race condition handling (check status before updating to running)
  - Dependencies: Task 1.3
- [x] Task 1.6: Add basic logging and error handling for best-effort execution
  - Dependencies: Task 1.3
- [x] Task 1.7: Add integration tests with Redis/Celery worker (not just unit tests)
  - Dependencies: Task 1.4, Task 1.1
- [x] Task 1.8: Add Makefile target for running worker locally (e.g., make worker)
  - Dependencies: Task 1.2

---

### Milestone 2: Scheduling and Deployment

**Description:** Ensure cron dispatch and deployment are workable in production.

#### Task Checklist

- [x] Task 2.1: Configure Celery Beat to periodically call /api/triggers/cron/dispatch
  - Dependencies: Milestone 1
  - Note: Beat will trigger HTTP call to cron dispatch endpoint, which creates pending runs that workers execute
- [x] Task 2.2: Add systemd unit templates for API, worker, and Celery Beat
  - Dependencies: None
- [x] Task 2.3: Document environment variables (REDIS_URL, Celery config) in README or deployment docs
  - Dependencies: None
- [x] Task 2.4: Update CLAUDE.md with worker commands (make worker, make celery-beat)
  - Dependencies: Task 1.8
- [x] Task 2.5: Document operational runbook for start/stop/monitor
  - Dependencies: Task 2.2

---

### Milestone 3: Validation

**Description:** Verify webhook and cron runs execute end-to-end.

#### Task Checklist

- [x] Task 3.1: Integration test for webhook -> run -> status update
  - Dependencies: Milestone 1
- [x] Task 3.2: Manual QA for cron dispatch -> run -> status update
  - Dependencies: Milestone 2

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-22 | Codex | Initial draft |
| 2025-12-22 | Claude | Implementation complete |
