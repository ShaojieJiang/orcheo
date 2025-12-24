# Design Document

## For PostgreSQL migration for local hosting

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-19
- **Status:** Approved

---

## Overview

This design adds PostgreSQL support to Orcheo's local hosting persistence layer by introducing parallel PostgreSQL implementations for seven SQLite-only subsystems. The approach avoids shared abstraction layers and relies on existing protocol and factory patterns for backend selection. The goal is to improve concurrency, ACID guarantees, and JSON support while preserving SQLite compatibility and enabling configuration-based rollback.

## Components

- **Configuration (orcheo.config)**
  - Adds `postgres` backend options and DSN/pool settings with `psycopg[binary,pool]`.
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

Configuration is provided via settings and environment variables (for example, `ORCHEO_POSTGRES_DSN`) and consumed by a `psycopg` async pool.

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
- Compatibility tests to ensure SQLite behavior is unchanged (SQLite ↔ PostgreSQL matrix for repository and checkpoints).
- Migration validation tests that exercise export/import flows with checksum verification and dry-run guards.
- Performance tests targeting 100+ concurrent requests and p95 query latency under 100 ms using pooled connections.

## Migration Strategy

- **Export/import**: Batch SQLite exports (JSON/CSV) with per-batch checksums, imported via COPY into PostgreSQL tables.
- **Downtime**: Target <5 minutes of write downtime during cutover; reads may continue from SQLite snapshots during backfill.
- **Rollback**: Preserve SQLite files; rollback by reverting `ORCHEO_REPOSITORY_BACKEND`/`ORCHEO_CHECKPOINT_BACKEND` to `sqlite` and unsetting `ORCHEO_POSTGRES_DSN`.
- **Validation**: Row counts and checksums compared post-import; spot-check JSONB columns for type fidelity.

## Rollout Plan

1. Phase 1: Config updates and PostgreSQL workflow repository.
2. Phase 2: Run history, service tokens, agentensor checkpoints.
3. Phase 3: ChatKit store and performance optimizations.
4. Phase 4: Optional vault migration, data migration tooling, and docs.

## Docker Compose Deployment

After migration to PostgreSQL, Docker Compose must start the PostgreSQL service alongside the application. The `docker-compose.yml` should include:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: orcheo
      POSTGRES_USER: orcheo
      POSTGRES_PASSWORD: orcheo
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U orcheo -d orcheo"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    # ... existing config ...
    environment:
      - ORCHEO_REPOSITORY_BACKEND=postgres
      - ORCHEO_CHECKPOINT_BACKEND=postgres
      - ORCHEO_POSTGRES_DSN=postgresql://orcheo:orcheo@postgres:5432/orcheo
    depends_on:
      postgres:
        condition: service_healthy

  worker:
    # ... existing config ...
    environment:
      - ORCHEO_REPOSITORY_BACKEND=postgres
      - ORCHEO_CHECKPOINT_BACKEND=postgres
      - ORCHEO_POSTGRES_DSN=postgresql://orcheo:orcheo@postgres:5432/orcheo
    depends_on:
      postgres:
        condition: service_healthy

  celery-beat:
    # ... existing config ...
    environment:
      - ORCHEO_REPOSITORY_BACKEND=postgres
      - ORCHEO_CHECKPOINT_BACKEND=postgres
      - ORCHEO_POSTGRES_DSN=postgresql://orcheo:orcheo@postgres:5432/orcheo
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  pgdata: {}
```

Key considerations:
- Use `service_healthy` condition to ensure PostgreSQL is ready before starting dependent services.
- The `pg_isready` healthcheck validates both connection and database availability.
- All services requiring persistence (backend, worker, celery-beat) must include PostgreSQL environment variables.
- Use internal Docker network hostname (`postgres`) for DSN connections between containers.

## Decisions & Follow-ups

- Vault migration is deferred for local hosting; continue using file/KMS vaults.
- Migration tooling ships as `orcheo.tooling.postgres_migration` with resumable batch imports.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-19 | Codex | Initial draft |
