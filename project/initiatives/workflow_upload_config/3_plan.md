# Project Plan

## For Workflow Upload Runnable Config

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-21
- **Status:** Draft

---

## Overview

Add upload-time runnable config support so workflows can ship with initial configuration using `--config` or `--config-file`, and persist that config on workflow versions in the configured repository backend (SQLite by default). This plan coordinates CLI, API, repository, and runtime merge behavior.

**Related Documents:**
- Requirements: `./1_requirements.md`
- Design: `./2_design.md`

**Priority Mapping:** P0 work is covered in Milestones 1 and 2. P1 work is covered in Milestone 3 (runtime merge, documentation, and regression coverage).

---

## Milestones

### Milestone 1: CLI and SDK Support

**Description:** Expose `--config` and `--config-file` on workflow upload and forward validated config to upload services.

#### Task Checklist

- [x] Task 1.1: Add `--config` and `--config-file` options to `orcheo workflow upload` with mutual exclusion and JSON validation
  - Dependencies: None
- [x] Task 1.2: Reuse `_resolve_runnable_config` and thread parsed config through `upload_workflow_data` and LangGraph ingestion helpers
  - Dependencies: Task 1.1
- [x] Task 1.3: Update CLI tests for JSON and script uploads to cover config inputs and invalid JSON cases
  - Dependencies: Task 1.2

---

### Milestone 2: Backend API and Persistence

**Description:** Accept and persist runnable config on workflow versions.

#### Task Checklist

- [x] Task 2.1: Extend workflow version create/ingest schemas to accept `runnable_config` and validate with `RunnableConfigModel`
  - Dependencies: Milestone 1
- [x] Task 2.2: Persist runnable config in workflow version payloads in the configured repository backend (SQLite by default; in-memory for tests/dev and only retained for the process lifetime)
  - Dependencies: Task 2.1
- [x] Task 2.3: Add migrations if a new column is introduced; otherwise verify payload compatibility across existing records
  - Dependencies: Task 2.2
  - Notes: If adding a column, make it nullable with a default of null; existing versions without runnable_config must continue to behave as empty.

---

### Milestone 3: Runtime Merge and Documentation

**Description:** Use stored config during execution and document the new workflow upload behavior.

#### Task Checklist

- [x] Task 3.1: Merge stored config with per-run config in workflow execution (run config precedence)
  - Dependencies: Milestone 2
- [x] Task 3.2: Expose stored config in workflow version responses and `workflow show` output
  - Dependencies: Task 3.1
- [x] Task 3.3: Update README and workflow upload docs with examples and warnings about secrets
  - Dependencies: Task 3.2
- [x] Task 3.4: Add regression tests for runs without stored config and with overrides
  - Dependencies: Task 3.1

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-21 | Codex | Initial draft |

---

## Rollback / Contingency

- Disable or hide the CLI flags and ignore runnable_config in upload handlers if needed.
- Keep stored runnable_config in payloads; no data rollback required.
