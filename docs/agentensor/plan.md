# Project Plan

## For Agentensor-powered optimization for Orcheo

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-16
- **Status:** Draft

---

## Overview

Plan to merge agentensor into the Orcheo repository and enable evaluation-driven optimization of AI nodes with persisted production parameters. This plan aligns with the requirements and design documents.

**Related Documents:**
- Requirements: docs/agentensor/requirements.md
- Design: docs/agentensor/design.md

---

## Milestones

### Milestone 1: Absorb agentensor into Orcheo

**Description:** Merge agentensor code, dependencies, and tooling into the Orcheo repo with passing lint/tests.

#### Task Checklist

- [ ] Task 1.1: Import agentensor source under `orcheo.agentensor` and align pyproject/uv.lock
  - Dependencies: Access to agentensor repo and licensing review
- [ ] Task 1.2: Add lint/typecheck/test coverage for merged modules
  - Dependencies: Task 1.1
- [ ] Task 1.3: Document install and build steps in README/Makefile
  - Dependencies: Task 1.1

---

### Milestone 2: Connect optimizers to AI nodes and evaluation outputs

**Description:** Enable Orcheo AI nodes to use agentensor optimizers and consume evaluation outputs as losses.

#### Task Checklist

- [ ] Task 2.1: Expose optimizer configuration on AI nodes and workflow definitions
  - Dependencies: Milestone 1
- [ ] Task 2.2: Build evaluation-to-optimizer bridge with schema validation and error surfacing
  - Dependencies: Task 2.1
- [ ] Task 2.3: Add integration tests covering optimizer loops with mocked evaluation nodes
  - Dependencies: Task 2.2

---

### Milestone 3: Persist and promote best parameters for production

**Description:** Store tuned prompts/hyper-parameters, promote versions to production, and provide observability/rollback.

#### Task Checklist

- [ ] Task 3.1: Implement parameter persistence with versioning, metadata, and approvals
  - Dependencies: Milestone 2
- [ ] Task 3.2: Wire production inference to fetch approved parameter versions by default
  - Dependencies: Task 3.1
- [ ] Task 3.3: Add promotion/rollback APIs/CLI plus dashboards or logs for artifacts
  - Dependencies: Task 3.1

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-16 | Codex | Initial draft |
