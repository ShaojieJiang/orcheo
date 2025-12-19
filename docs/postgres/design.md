# Design Document

## For PostgreSQL migration for local hosting

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-19
- **Status:** Draft

---

## Overview

This design adds PostgreSQL support to Orcheo's local hosting persistence layer by introducing parallel PostgreSQL implementations for seven SQLite-only subsystems. The approach avoids shared abstraction layers and relies on existing protocol and factory patterns for backend selection. The goal is to improve concurrency, ACID guarantees, and JSON support while preserving SQLite compatibility and enabling configuration-based rollback.

## Components

- **Configuration (orcheo.config)**
  - Adds `postgres` backend options and DSN/pool settings.
  - Validates repository backend and connection configuration.

- **Workflow Repository (repository_postgres)**
  - Implements CRUD and versioning in PostgreSQL.
  - Initializes schema and maintains indexes.

- **Run History Store (history/postgres_store.py)**
  - Persists run execution history in PostgreSQL.
  - Stores trace data as JSONB.

- **Service Token Repository (service_token_repository/postgres_repository.py)**
  - Stores and validates token hashes using PostgreSQL.
  - Adds performance indexes for lookup and expiry.

- **Agentensor Checkpoints (agentensor/postgres_checkpoint_store.py)**
  - Persists checkpoint metadata as JSONB with GIN indexes.

- **ChatKit Store (chatkit_store_postgres)**
  - Stores threads, messages, and attachments in PostgreSQL.

- **Optional Vault Migration (vault/postgres_*)**
  - Remains SQLite by default; PostgreSQL option is optional.

## Request Flows

### Flow 1: Workflow repository CRUD
1. API handler calls repository factory using configured backend.
2. PostgreSQL repository acquires async connection from pool.
3. Repository executes CRUD queries in a transaction.
4. Results are returned through protocol interfaces.

### Flow 2: Run history persistence
1. Workflow execution emits run history events.
2. PostgreSQL run history store writes JSONB trace data.
3. Store commits transaction and returns status.

### Flow 3: Service token validation
1. Auth middleware receives a service token.
2. Token hash lookup queries PostgreSQL index.
3. Repository returns token metadata and expiry status.

### Flow 4: ChatKit message storage
1. ChatKit thread or message event arrives.
2. Store writes JSONB content and metadata.
3. Queries use indexes for thread and time ordering.

## API Contracts

There are no external API contract changes. Backend selection follows existing provider patterns:

```
create_repository(settings)
  -> InMemoryWorkflowRepository
  -> SqliteWorkflowRepository
  -> PostgresWorkflowRepository  # new
```

Configuration is provided via settings and environment variables (for example, `ORCHEO_POSTGRES_DSN`).

## Data Models / Schemas

### SQLite to PostgreSQL type mapping

| SQLite Type | PostgreSQL Type | Example |
|-------------|----------------|---------|
| TEXT (JSON) | JSONB | Metrics, metadata, config |
| TEXT (timestamp) | TIMESTAMP WITH TIME ZONE | created_at, updated_at |
| INTEGER (boolean) | BOOLEAN | is_active, is_best |
| TEXT | TEXT | IDs, names |
| INTEGER | INTEGER or BIGINT | Counters, versions |
| REAL | DOUBLE PRECISION | Floating point |
| BLOB | BYTEA | Binary data |

### Example: agentensor checkpoints

```sql
CREATE TABLE IF NOT EXISTS agentensor_checkpoints (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    config_version INTEGER NOT NULL,
    runnable_config JSONB NOT NULL,
    metrics JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    artifact_url TEXT NULL,
    is_best BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_workflow_id ON agentensor_checkpoints(workflow_id);
CREATE INDEX idx_config_version ON agentensor_checkpoints(config_version);
CREATE INDEX idx_metrics_gin ON agentensor_checkpoints USING GIN(metrics);
CREATE INDEX idx_metadata_gin ON agentensor_checkpoints USING GIN(metadata);
```

## Security Considerations

- Use TLS for PostgreSQL connections in production (`sslmode=require`).
- Store DSNs in secrets manager or `.env` for local use.
- Use least-privilege database users.
- For optional vault migration, use `pgcrypto` for encryption at rest.

## Performance Considerations

- Use async connection pooling with sane defaults (min/max pool size, timeouts).
- Add GIN indexes for JSONB columns and composite indexes for common queries.
- Validate query performance with EXPLAIN ANALYZE on slow paths.

## Testing Strategy

- Unit tests for connection pooling, schema initialization, and repository CRUD.
- Integration tests to validate end-to-end workflow execution on PostgreSQL.
- Compatibility tests to ensure SQLite behavior is unchanged.
- Optional performance tests for throughput and latency targets.

## Rollout Plan

1. Phase 1: Config updates and PostgreSQL workflow repository.
2. Phase 2: Run history, service tokens, agentensor checkpoints.
3. Phase 3: ChatKit store and performance optimizations.
4. Phase 4: Optional vault migration, data migration tooling, and docs.

## Open Issues

- Decide on `psycopg` vs `asyncpg` for async access and pool usage.
- Confirm whether vault migration is required for local hosting.
- Define SQLite to PostgreSQL data migration strategy and tooling scope.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-19 | Codex | Initial draft |
