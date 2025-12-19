# Project Plan

## For PostgreSQL migration for local hosting

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-19
- **Status:** Draft

---

## Overview

Split persistence into parallel PostgreSQL implementations for local hosting while preserving SQLite behavior. This plan sequences the work by subsystem criticality and aligns with configuration updates, testing, and deployment documentation.

**Related Documents:**
- Requirements: `docs/postgres/requirements.md`
- Design: `docs/postgres/design.md`

---

## Milestones

### Milestone 1: Foundation and workflow repository

**Description:** Add PostgreSQL configuration and core workflow repository implementation with schema and connection pooling.

#### Task Checklist

- [ ] Task 1.1: Update config types and validators for `postgres` backend
  - Dependencies: None
- [ ] Task 1.2: Add PostgreSQL DSN and pool configuration settings
  - Dependencies: Task 1.1
- [ ] Task 1.3: Implement repository_postgres base, schema, and CRUD
  - Dependencies: Task 1.1
- [ ] Task 1.4: Update providers to dispatch to PostgreSQL repository
  - Dependencies: Task 1.3
- [ ] Task 1.5: Add workflow repository tests for PostgreSQL
  - Dependencies: Task 1.3

---

### Milestone 2: Critical subsystems

**Description:** Implement PostgreSQL backends for run history, service tokens, and agentensor checkpoints with integration tests.

#### Task Checklist

- [ ] Task 2.1: Implement run history PostgreSQL store
  - Dependencies: Milestone 1
- [ ] Task 2.2: Implement service token PostgreSQL repository with hashing
  - Dependencies: Milestone 1
- [ ] Task 2.3: Implement agentensor PostgreSQL checkpoint store
  - Dependencies: Milestone 1
- [ ] Task 2.4: Add integration tests for PostgreSQL workflows
  - Dependencies: Task 2.1

---

### Milestone 3: Auxiliary features

**Description:** Add ChatKit PostgreSQL store and performance improvements.

#### Task Checklist

- [ ] Task 3.1: Implement ChatKit PostgreSQL store and schema
  - Dependencies: Milestone 2
- [ ] Task 3.2: Add indexes and query optimizations
  - Dependencies: Task 3.1
- [ ] Task 3.3: Add optional advanced features (FTS, JSONB filtering, keyset pagination)
  - Dependencies: Task 3.2

---

### Milestone 4: Optional and future work

**Description:** Address optional vault migration, data migration tools, and deployment documentation.

#### Task Checklist

- [ ] Task 4.1: Decide on vault migration scope
  - Dependencies: Milestone 3
- [ ] Task 4.2: Implement SQLite to PostgreSQL migration tooling
  - Dependencies: Milestone 3
- [ ] Task 4.3: Add deployment automation (compose/manifests)
  - Dependencies: Task 4.2
- [ ] Task 4.4: Update documentation and troubleshooting guides
  - Dependencies: Task 4.3

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-19 | Codex | Initial draft |
