# Project Plan

## For PostgreSQL migration for local hosting

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-19
- **Status:** Approved

---

## Overview

Split persistence into parallel PostgreSQL implementations for local hosting while preserving SQLite behavior. This plan sequences the work by subsystem criticality and aligns with configuration updates, testing, and deployment documentation.

**Related Documents:**
- Requirements: `./1_requirements.md`
- Design: `./2_design.md`

---

## Milestones

### Milestone 1: Foundation and workflow repository

**Description:** Add PostgreSQL configuration and core workflow repository implementation with schema and connection pooling.

#### Task Checklist

- [x] Task 1.0: Finalize `psycopg[binary,pool]` driver selection and document DSN requirements
  - Dependencies: None
- [x] Task 1.1: Update config types and validators for `postgres` backend
  - Dependencies: None
- [x] Task 1.2: Add PostgreSQL DSN and pool configuration settings
  - Dependencies: Task 1.1
- [x] Task 1.3: Implement repository_postgres base, schema, and CRUD
  - Dependencies: Task 1.1
- [x] Task 1.4: Update providers to dispatch to PostgreSQL repository
  - Dependencies: Task 1.3
- [x] Task 1.5: Add workflow repository tests for PostgreSQL
  - Dependencies: Task 1.3

---

### Milestone 2: Critical subsystems

**Description:** Implement PostgreSQL backends for run history, service tokens, and agentensor checkpoints with integration tests.

#### Task Checklist

- [x] Task 2.1: Implement run history PostgreSQL store
  - Dependencies: Milestone 1
- [x] Task 2.2: Implement service token PostgreSQL repository with hashing
  - Dependencies: Milestone 1
- [x] Task 2.3: Implement agentensor PostgreSQL checkpoint store
  - Dependencies: Milestone 1
- [x] Task 2.4: Add integration tests for PostgreSQL workflows
  - Dependencies: Task 2.1

---

### Milestone 3: Auxiliary features

**Description:** Add ChatKit PostgreSQL store and performance improvements.

#### Task Checklist

- [x] Task 3.1: Implement ChatKit PostgreSQL store and schema
  - Dependencies: Milestone 2
- [x] Task 3.2: Add indexes and query optimizations
  - Dependencies: Task 3.1
- [x] Task 3.3: Add optional advanced features (FTS, JSONB filtering, keyset pagination)
  - Dependencies: Task 3.2

---

### Milestone 4: Optional and future work

**Description:** Address optional vault migration, data migration tools, and deployment documentation.

#### Task Checklist

- [x] Task 4.1: Decide on vault migration scope
  - Dependencies: Milestone 3
- [x] Task 4.2: Implement SQLite to PostgreSQL migration tooling (export with checksums, batched imports, validation)
  - Dependencies: Milestone 3
- [x] Task 4.3: Update docker-compose.yml to include PostgreSQL service with healthcheck
  - Dependencies: Task 4.2
- [x] Task 4.4: Add deployment automation (manifests) plus rollback runbooks
  - Dependencies: Task 4.3
- [x] Task 4.5: Update documentation and troubleshooting guides
  - Dependencies: Task 4.4

## Testing Strategy

- Backend switching: regression matrix across SQLite ↔ PostgreSQL for repository and checkpoints with data parity verification.
- Performance: p95 latency and concurrency targets validated via load tests (100+ concurrent requests) using pooled connections.
- Migration validation: export/import checksum verification and dry-run modes for SQLite → PostgreSQL transitions.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-19 | Codex | Initial draft |
| 2025-12-23 | Claude | Implemented Milestones 1-2 core tasks and Task 4.3 |
| 2025-12-24 | Claude | Added PostgreSQL repository tests (Task 1.5) and integration tests (Task 2.4) |
