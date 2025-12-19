# Requirements Document

## METADATA
- **Authors:** Codex
- **Project/Feature Name:** PostgreSQL migration for local hosting
- **Type:** Enhancement
- **Summary:** Migrate local hosting persistence from SQLite to PostgreSQL by adding parallel PostgreSQL implementations for seven subsystems while keeping SQLite compatibility.
- **Owner (if different than authors):** Shaojie Jiang
- **Date Started:** 2025-12-19

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| Design Doc | `docs/postgres/design.md` | Shaojie Jiang | PostgreSQL Migration Design |
| Project Plan | `docs/postgres/plan.md` | Shaojie Jiang | PostgreSQL Migration Plan |
| Config Types | `src/orcheo/config/types.py` | Shaojie Jiang | Config Types |
| App Settings Validators | `src/orcheo/config/app_settings.py` | Shaojie Jiang | Settings Validators |

## PROBLEM DEFINITION
### Objectives
Migrate local hosting persistence from SQLite to PostgreSQL to improve concurrency, reliability, and scalability. Provide PostgreSQL implementations for all critical subsystems while preserving SQLite behavior and configuration.

### Target users
DevOps and backend engineers operating local hosting deployments; developers who need production-grade persistence locally.

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| DevOps engineer | configure a PostgreSQL DSN for local hosting | local deployments handle concurrent usage reliably | P0 | PostgreSQL backend works end-to-end with expected configuration keys |
| Backend engineer | use repository, run history, and tokens with PostgreSQL | persistence is consistent across subsystems | P0 | All critical subsystems have PostgreSQL implementations and tests |
| Operator | roll back to SQLite by config | failures can be mitigated quickly | P1 | Config-only rollback restores SQLite behavior |

### Context, Problems, Opportunities
Orcheo uses multiple SQLite databases for persistence. While LangGraph checkpoints already support PostgreSQL, seven subsystems remain SQLite-only. This limits concurrency and production-grade reliability for local hosting deployments. A parallel PostgreSQL implementation provides better ACID guarantees, JSONB support, and scalable query performance.

### Product goals and Non-goals
Goals:
- Enable PostgreSQL backend for all critical persistence subsystems.
- Maintain SQLite compatibility and allow configuration-based rollback.
- Improve concurrency and operational readiness for local hosting.

Non-goals:
- Replace or refactor existing SQLite implementations.
- Force PostgreSQL for all deployments.
- Migrate vault storage unless explicitly required.

## PRODUCT DEFINITION
### Requirements
P0:
- Add `postgres` option to repository backend configuration.
- Implement PostgreSQL workflow repository with full CRUD support.
- Add PostgreSQL implementations for run history, service tokens, agentensor checkpoints, and ChatKit store.
- Convert SQLite schemas to PostgreSQL equivalents (JSONB, BOOLEAN, TIMESTAMPTZ).
- Implement async connection pooling and health checks.
- Provide targeted tests for PostgreSQL backends.

P1:
- Add performance indexes (GIN, composite) for common query patterns.
- Add advanced features: full-text search, JSONB filtering, keyset pagination.
- Provide migration tooling from SQLite to PostgreSQL.
- Update local deployment documentation and examples.

P2/Optional:
- Vault migration to PostgreSQL using pgcrypto.

### Designs (if applicable)
Design doc: `docs/postgres/design.md`

### [Optional] Other Teams Impacted
- DevOps: PostgreSQL deployment, backups, and monitoring.
- Backend: repository and store implementations, tests, and config updates.

## TECHNICAL CONSIDERATIONS
### Architecture Overview
Adopt a parallel implementation strategy: keep SQLite code intact and add PostgreSQL implementations per subsystem. Use existing protocol/factory patterns to switch by configuration.

### Technical Requirements
- PostgreSQL 14+.
- Dependencies: `psycopg[binary,pool]>=3.2.0` (preferred) or `asyncpg`.
- Required extensions: `uuid-ossp`, `pgcrypto` (if vault), `pg_trgm` (FTS).
- Connection pooling settings configurable (min/max pool size, timeout, idle).

## MARKET DEFINITION (for products or large features)
Not applicable. This is an internal enhancement for local hosting.

## LAUNCH/ROLLOUT PLAN
### Success metrics
| KPIs | Target & Rationale |
|------|--------------------|
| All subsystems supported | 7 subsystems have PostgreSQL implementations with tests |
| Regression-free rollout | SQLite behavior unchanged and rollback works by config |
| Performance | p95 query < 100ms for simple queries |
| Reliability | Connection pool handles 100+ concurrent requests |

### Rollout Strategy
Phased rollout aligned with subsystem criticality: foundation, critical features, auxiliary features, then optional work.

### Experiment Plan (if applicable)
Not applicable.

### Estimated Launch Phases (if applicable)
| Phase | Target | Description |
|-------|--------|-------------|
| **Phase 1** | Core persistence | Workflow repository and config updates |
| **Phase 2** | Critical subsystems | Run history, service tokens, agentensor checkpoints |
| **Phase 3** | Auxiliary features | ChatKit store and performance optimization |
| **Phase 4** | Optional | Vault migration, data migration tools, docs |

## HYPOTHESIS & RISKS
Hypothesis: Providing PostgreSQL backends for local hosting improves concurrency, reliability, and operational readiness without changing the application surface.

Risks:
- Behavior divergence between SQLite and PostgreSQL implementations.
- Schema conversion errors or inconsistent JSON handling.
- Connection pool misconfiguration causing latency or exhaustion.

Risk Mitigation:
- Maintain protocol-based compatibility tests across backends.
- Add schema initialization and migration tests.
- Provide sane default pool settings and health checks.

## APPENDIX
- Current SQLite usage spans multiple databases (workflows, run history, service tokens, agentensor checkpoints, ChatKit, vault).
- LangGraph checkpoints already support PostgreSQL via `langgraph-checkpoint-postgres`.
