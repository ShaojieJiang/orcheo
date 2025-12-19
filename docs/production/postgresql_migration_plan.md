# PostgreSQL Migration Plan for Local Hosting

**Document Status:** Draft
**Created:** 2025-12-19
**Target Audience:** DevOps, Backend Engineers
**Estimated Effort:** 3-4 weeks (1 engineer)

## Executive Summary

This document outlines the technical plan for migrating Orcheo's local hosting deployment from SQLite to PostgreSQL. While LangGraph checkpoint storage already supports PostgreSQL, **7 major persistence subsystems** currently use SQLite and require PostgreSQL implementations.

**Current State:**
- ✅ LangGraph checkpoints: PostgreSQL-ready via `langgraph-checkpoint-postgres`
- ❌ Workflow Repository: SQLite-only
- ❌ Run History Store: SQLite-only
- ❌ Agentensor Checkpoints: SQLite-only
- ❌ ChatKit Store: SQLite-only
- ❌ Service Token Repository: SQLite-only
- ❌ Vault Storage: SQLite-only

**Key Benefits:**
- Better concurrency and multi-user support
- Production-grade ACID guarantees
- Native JSON/JSONB support
- Superior query performance at scale
- Industry-standard backup and replication

**Key Challenges:**
- 7 subsystems need parallel PostgreSQL implementations
- Both sync and async database patterns in use
- Schema differences (PRAGMA → SET, TEXT → JSONB, INTEGER → BOOLEAN)
- Connection pooling and resource management

---

## Table of Contents

1. [Current Architecture Analysis](#current-architecture-analysis)
2. [Migration Strategy](#migration-strategy)
3. [Implementation Phases](#implementation-phases)
4. [Technical Requirements](#technical-requirements)
5. [Schema Changes](#schema-changes)
6. [Code Changes by Subsystem](#code-changes-by-subsystem)
7. [Testing Strategy](#testing-strategy)
8. [Deployment & Operations](#deployment--operations)
9. [Rollback Plan](#rollback-plan)
10. [Timeline & Resources](#timeline--resources)

---

## 1. Current Architecture Analysis

### 1.1 Database Backends in Use

Orcheo currently uses **8 separate SQLite databases** for different persistence needs:

| Subsystem | Database Path | Status | Criticality |
|-----------|--------------|---------|-------------|
| LangGraph Checkpoints | `~/.orcheo/checkpoints.sqlite` | ✅ Postgres-ready | HIGH |
| Workflow Repository | `~/.orcheo/workflows.sqlite` | ❌ SQLite-only | CRITICAL |
| Run History | Embedded in repository DB | ❌ SQLite-only | HIGH |
| Agentensor Checkpoints | Embedded in repository DB | ❌ SQLite-only | MEDIUM |
| ChatKit Store | `~/.orcheo/chatkit.sqlite` | ❌ SQLite-only | MEDIUM |
| Service Tokens | Derived from repository path | ❌ SQLite-only | HIGH |
| Vault Storage | `~/.orcheo/vault.sqlite` | ❌ SQLite-only | LOW |

### 1.2 Configuration System

**Location:** [src/orcheo/config/](../../src/orcheo/config/)

Current configuration keys:
```python
# Checkpoint backend (✅ supports PostgreSQL)
CHECKPOINT_BACKEND: "sqlite" | "postgres"
SQLITE_PATH: "~/.orcheo/checkpoints.sqlite"
POSTGRES_DSN: Optional[str]  # Required when checkpoint_backend="postgres"

# Repository backend (❌ NO PostgreSQL support yet)
REPOSITORY_BACKEND: "inmemory" | "sqlite"  # Needs "postgres" option
REPOSITORY_SQLITE_PATH: "~/.orcheo/workflows.sqlite"
```

**Key Files:**
- [src/orcheo/config/types.py:7](../../src/orcheo/config/types.py#L7) - Backend type definitions
- [src/orcheo/config/app_settings.py:87-109](../../src/orcheo/config/app_settings.py#L87-L109) - Validators
- [src/orcheo/config/defaults.py](../../src/orcheo/config/defaults.py) - Default values

### 1.3 Database Access Patterns

**Async Pattern (Most Common):**
```python
# Current SQLite implementation
import aiosqlite

@asynccontextmanager
async def _connection(self) -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(str(self._database_path))
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()
```

**Sync Pattern (Vault, Service Tokens):**
```python
# Current SQLite implementation
import sqlite3
from queue import Queue

@contextmanager
def _acquire_connection(self) -> Iterator[sqlite3.Connection]:
    try:
        conn = self._connection_pool.get_nowait()
    except Empty:
        conn = self._create_connection()
    try:
        yield conn
    finally:
        self._release_connection(conn)
```

---

## 2. Migration Strategy

### 2.1 Recommended Approach: Parallel Implementation

**DO:** Create new PostgreSQL implementations alongside existing SQLite code
**DON'T:** Abstract SQLite code to support both backends

**Rationale:**
1. SQLite and PostgreSQL have fundamentally different characteristics
2. Abstraction would add complexity without significant benefit
3. Orcheo's architecture already uses protocols/interfaces (see [repository/protocol.py](../../apps/backend/src/orcheo_backend/app/repository/protocol.py))
4. Factory pattern can cleanly switch between implementations

### 2.2 Implementation Philosophy

```python
# Factory pattern at provider level
def create_repository(settings: AppSettings) -> WorkflowRepositoryProtocol:
    match settings.repository_backend:
        case "inmemory":
            return InMemoryWorkflowRepository()
        case "sqlite":
            return SqliteWorkflowRepository(settings.repository_sqlite_path)
        case "postgres":
            return PostgresWorkflowRepository(settings.postgres_dsn)  # NEW
```

### 2.3 Phased Rollout

**Phase 1: Foundation (Week 1)**
- Configuration updates
- PostgreSQL connection infrastructure
- Workflow Repository implementation
- Core CRUD operations testing

**Phase 2: Critical Features (Week 2)**
- Run History Store
- Service Token Repository
- Agentensor Checkpoints
- Integration testing

**Phase 3: Auxiliary Features (Week 3)**
- ChatKit Store
- Advanced features (search, filtering)
- Performance optimization

**Phase 4: Optional/Future (Week 4)**
- Vault migration (OR keep SQLite for local credentials)
- Data migration tools
- Documentation & deployment guides

---

## 3. Implementation Phases

### Phase 1: Foundation & Workflow Repository

**Goals:**
- Add PostgreSQL as valid `RepositoryBackend` option
- Implement core workflow CRUD operations
- Establish PostgreSQL patterns for remaining subsystems

**Deliverables:**

1. **Configuration Changes**
   - [ ] Update [src/orcheo/config/types.py](../../src/orcheo/config/types.py#L7)
     ```python
     RepositoryBackend = Literal["inmemory", "sqlite", "postgres"]  # Add "postgres"
     ```
   - [ ] Update [src/orcheo/config/app_settings.py](../../src/orcheo/config/app_settings.py#L100-L109) validators
   - [ ] Add `REPOSITORY_POSTGRES_DSN` config key
   - [ ] Add PostgreSQL connection pool settings (max_connections, timeout, etc.)

2. **New Directory Structure**
   ```
   apps/backend/src/orcheo_backend/app/repository_postgres/
   ├── __init__.py              # PostgresWorkflowRepository class
   ├── _base.py                 # PostgreSQL connection management
   ├── _persistence.py          # Core CRUD operations
   ├── _workflows.py            # Workflow-specific operations (mixin)
   ├── _versions.py             # Version-specific operations (mixin)
   ├── _runs.py                 # Run-specific operations (mixin)
   ├── _triggers.py             # Trigger-specific operations (mixin)
   └── schema.py                # PostgreSQL DDL statements
   ```

3. **Schema Implementation**
   - [ ] Convert SQLite schema to PostgreSQL ([See Section 5](#schema-changes))
   - [ ] Replace `TEXT` JSON columns with `JSONB`
   - [ ] Replace `INTEGER` booleans with `BOOLEAN`
   - [ ] Replace `TEXT` timestamps with `TIMESTAMP WITH TIME ZONE`
   - [ ] Replace `AUTOINCREMENT` with `SERIAL`/`BIGSERIAL`
   - [ ] Remove SQLite `PRAGMA` statements

4. **Connection Management**
   - [ ] Choose between `psycopg3` (recommended) or `asyncpg`
   - [ ] Implement async connection pool using `psycopg_pool.AsyncConnectionPool`
   - [ ] Add connection retry logic with exponential backoff
   - [ ] Implement health check queries (`SELECT 1`)

5. **Provider Updates**
   - [ ] Update [apps/backend/src/orcheo_backend/app/providers.py](../../apps/backend/src/orcheo_backend/app/providers.py)
   - [ ] Add `create_postgres_repository()` factory function
   - [ ] Update `create_repository()` to dispatch to PostgreSQL when configured

**Acceptance Criteria:**
- All workflow CRUD operations work with PostgreSQL
- Existing tests pass with PostgreSQL backend (via config override)
- No regression in SQLite functionality
- Connection pooling under load (100 concurrent requests)

---

### Phase 2: Critical Features

**Goals:**
- Implement remaining critical persistence subsystems
- Ensure production-ready transaction handling

**Deliverables:**

1. **Run History Store**
   - [ ] Create [apps/backend/src/orcheo_backend/app/history/postgres_store.py](../../apps/backend/src/orcheo_backend/app/history/)
   - [ ] Create [apps/backend/src/orcheo_backend/app/history/postgres_utils.py](../../apps/backend/src/orcheo_backend/app/history/)
   - [ ] Implement `PostgresRunHistoryStore` class
   - [ ] Replace `PRAGMA table_info()` migrations with information_schema queries
   - [ ] Convert trace data to JSONB

2. **Service Token Repository**
   - [ ] Create [apps/backend/src/orcheo_backend/app/service_token_repository/postgres_repository.py](../../apps/backend/src/orcheo_backend/app/service_token_repository/)
   - [ ] Implement `PostgresServiceTokenRepository` class
   - [ ] Add token indexing for performance
   - [ ] Implement secure token hashing (bcrypt/argon2)

3. **Agentensor Checkpoints**
   - [ ] Create [apps/backend/src/orcheo_backend/app/agentensor/postgres_checkpoint_store.py](../../apps/backend/src/orcheo_backend/app/agentensor/)
   - [ ] Implement `PostgresAgentensorCheckpointStore` class
   - [ ] Convert metrics/runnable_config to JSONB
   - [ ] Add composite indexes for query performance

**Acceptance Criteria:**
- Workflow execution history persists correctly
- Service token auth works with PostgreSQL
- Agentensor training checkpoints save/restore correctly
- All integration tests pass

---

### Phase 3: Auxiliary Features

**Goals:**
- Complete remaining subsystems
- Optimize query performance

**Deliverables:**

1. **ChatKit Store**
   - [ ] Create directory: `apps/backend/src/orcheo_backend/app/chatkit_store_postgres/`
   - [ ] Implement PostgreSQL versions of:
     - `base.py` - Connection management
     - `store.py` - Store operations
     - `threads.py` - Thread management
     - `items.py` - Item storage
     - `attachments.py` - Attachment handling
   - [ ] Replace `PRAGMA foreign_keys = ON` with FK constraints in DDL
   - [ ] Use JSONB for message content/metadata

2. **Performance Optimization**
   - [ ] Add database indexes based on query patterns
   - [ ] Implement query result caching where appropriate
   - [ ] Add query performance logging/monitoring
   - [ ] Run EXPLAIN ANALYZE on slow queries

3. **Advanced Features**
   - [ ] Full-text search using PostgreSQL's built-in FTS
   - [ ] Advanced filtering with JSONB operators
   - [ ] Pagination improvements with keyset pagination

**Acceptance Criteria:**
- ChatKit conversations work with PostgreSQL
- Query performance meets SLAs (< 100ms for simple queries)
- Full-text search returns relevant results

---

### Phase 4: Optional/Future Work

**Deliverables:**

1. **Vault Migration (OPTIONAL)**
   - **Decision Point:** Keep vault as SQLite for simplicity?
   - **Rationale:** Credentials are sensitive; local SQLite file may be simpler for local hosting
   - **If migrating:**
     - [ ] Create `src/orcheo/vault/postgres_*.py` implementations
     - [ ] Encrypt credentials using PostgreSQL pgcrypto extension
     - [ ] Implement key rotation mechanism

2. **Data Migration Tools**
   - [ ] Create `scripts/migrate_sqlite_to_postgres.py`
   - [ ] Export SQLite data to JSON/CSV
   - [ ] Import into PostgreSQL with schema validation
   - [ ] Verify data integrity post-migration

3. **Deployment Automation**
   - [ ] Docker Compose configuration with PostgreSQL
   - [ ] Kubernetes manifests with PostgreSQL StatefulSet
   - [ ] Terraform modules for cloud PostgreSQL (RDS, Cloud SQL)
   - [ ] Automated schema migration on deployment

4. **Documentation**
   - [ ] Update README with PostgreSQL setup instructions
   - [ ] Create deployment guide for local PostgreSQL
   - [ ] Document connection string format
   - [ ] Add troubleshooting guide

**Acceptance Criteria:**
- Migration tool successfully migrates test datasets
- Deployment automation tested in staging environment
- Documentation reviewed by DevOps team

---

## 4. Technical Requirements

### 4.1 Dependencies

**Add to pyproject.toml:**
```toml
[project.dependencies]
# Already included:
langgraph-checkpoint-postgres = ">=3.0.0"

# Add these:
psycopg = {version = ">=3.2.0", extras = ["binary", "pool"]}
# OR (alternative):
# asyncpg = ">=0.29.0"

[project.optional-dependencies]
postgres = [
    "psycopg[binary,pool]>=3.2.0",
    "pgbouncer>=1.21.0",  # Optional: external connection pooler
]
```

**Library Comparison:**

| Feature | psycopg3 | asyncpg |
|---------|----------|---------|
| API Style | DB-API 2.0 (standard) | Custom async API |
| Performance | Good | Excellent |
| Compatibility | Drop-in from psycopg2 | Requires code changes |
| Connection Pool | Built-in | Built-in |
| Type Conversion | Automatic | Manual registration |
| **Recommendation** | ✅ **Use for familiarity** | Use for max performance |

### 4.2 PostgreSQL Server Requirements

**Minimum Version:** PostgreSQL 14+

**Required Extensions:**
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- Encryption (if vault migrated)
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- Full-text search
```

**Recommended Configuration:**
```ini
# postgresql.conf
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 4MB
min_wal_size = 1GB
max_wal_size = 4GB
max_worker_processes = 4
max_parallel_workers_per_gather = 2
max_parallel_workers = 4
```

### 4.3 Connection Pool Configuration

**Recommended Settings:**
```python
# Config for local hosting (small-medium scale)
POSTGRES_MIN_POOL_SIZE = 2
POSTGRES_MAX_POOL_SIZE = 20
POSTGRES_TIMEOUT = 30  # seconds
POSTGRES_MAX_IDLE = 300  # 5 minutes

# Connection string format
POSTGRES_DSN = "postgresql://user:password@localhost:5432/orcheo"
# OR with connection params
POSTGRES_DSN = "postgresql://user:password@localhost:5432/orcheo?connect_timeout=10"
```

---

## 5. Schema Changes

### 5.1 Data Type Mapping

| SQLite Type | PostgreSQL Type | Example |
|-------------|----------------|---------|
| `TEXT` (JSON) | `JSONB` | Metrics, metadata, config |
| `TEXT` (timestamp) | `TIMESTAMP WITH TIME ZONE` | created_at, updated_at |
| `INTEGER` (boolean) | `BOOLEAN` | is_active, is_best |
| `TEXT` | `TEXT` or `VARCHAR(n)` | IDs, names |
| `INTEGER` | `INTEGER` or `BIGINT` | Counters, versions |
| `REAL` | `DOUBLE PRECISION` | Floating point |
| `BLOB` | `BYTEA` | Binary data |

### 5.2 Example Schema Conversion

**Before (SQLite):**
```sql
-- From apps/backend/src/orcheo_backend/app/agentensor/checkpoint_store.py
CREATE TABLE IF NOT EXISTS agentensor_checkpoints (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    config_version INTEGER NOT NULL,
    runnable_config TEXT NOT NULL,      -- JSON as TEXT
    metrics TEXT NOT NULL,               -- JSON as TEXT
    metadata TEXT NOT NULL DEFAULT '{}', -- JSON as TEXT
    artifact_url TEXT NULL,
    is_best INTEGER NOT NULL DEFAULT 0,  -- Boolean as INTEGER
    created_at TEXT NOT NULL             -- Timestamp as TEXT
);

CREATE INDEX IF NOT EXISTS idx_workflow_id
    ON agentensor_checkpoints(workflow_id);

CREATE INDEX IF NOT EXISTS idx_config_version
    ON agentensor_checkpoints(config_version);
```

**After (PostgreSQL):**
```sql
CREATE TABLE IF NOT EXISTS agentensor_checkpoints (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    config_version INTEGER NOT NULL,
    runnable_config JSONB NOT NULL,                         -- Native JSONB
    metrics JSONB NOT NULL,                                  -- Native JSONB
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,            -- Native JSONB with default
    artifact_url TEXT NULL,
    is_best BOOLEAN NOT NULL DEFAULT FALSE,                 -- Native BOOLEAN
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()  -- Timestamp with timezone
);

-- Indexes
CREATE INDEX idx_workflow_id ON agentensor_checkpoints(workflow_id);
CREATE INDEX idx_config_version ON agentensor_checkpoints(config_version);

-- JSONB indexes for performance
CREATE INDEX idx_metrics_gin ON agentensor_checkpoints USING GIN(metrics);
CREATE INDEX idx_metadata_gin ON agentensor_checkpoints USING GIN(metadata);

-- Composite index for common queries
CREATE INDEX idx_workflow_config ON agentensor_checkpoints(workflow_id, config_version);
```

### 5.3 Auto-Increment Changes

**Before (SQLite):**
```sql
CREATE TABLE workflows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);
```

**After (PostgreSQL):**
```sql
CREATE TABLE workflows (
    id SERIAL PRIMARY KEY,  -- or BIGSERIAL for 64-bit
    name TEXT NOT NULL
);
```

### 5.4 PRAGMA Statement Replacements

**SQLite PRAGMAs:**
```sql
PRAGMA journal_mode = WAL;        -- Write-Ahead Logging
PRAGMA foreign_keys = ON;         -- Enable foreign key constraints
PRAGMA synchronous = NORMAL;      -- Fsync mode
```

**PostgreSQL Equivalents:**
```sql
-- These are server-level configs, set in postgresql.conf:
wal_level = replica                    -- Similar to WAL mode
synchronous_commit = on                -- Similar to synchronous
-- Foreign keys are ALWAYS enforced in PostgreSQL (no need to enable)

-- Or set per-session:
SET synchronous_commit = on;
```

---

## 6. Code Changes by Subsystem

### 6.1 Workflow Repository

**Current:** [apps/backend/src/orcheo_backend/app/repository_sqlite/](../../apps/backend/src/orcheo_backend/app/repository_sqlite/)

**New Implementation:**

**File:** `apps/backend/src/orcheo_backend/app/repository_postgres/_base.py`
```python
"""PostgreSQL base class for workflow repository."""

from contextlib import asynccontextmanager
from typing import AsyncIterator
import psycopg
from psycopg_pool import AsyncConnectionPool

class PostgresRepositoryBase:
    def __init__(self, postgres_dsn: str):
        self._dsn = postgres_dsn
        self._pool: AsyncConnectionPool | None = None
        self._initialized = False

    async def _ensure_pool(self) -> None:
        """Ensure connection pool is initialized."""
        if self._pool is not None:
            return
        self._pool = AsyncConnectionPool(
            conninfo=self._dsn,
            min_size=2,
            max_size=20,
            timeout=30.0,
        )
        await self._pool.open()

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[psycopg.AsyncConnection]:
        """Get connection from pool."""
        await self._ensure_pool()
        assert self._pool is not None
        async with self._pool.connection() as conn:
            try:
                yield conn
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise

    async def _ensure_initialized(self) -> None:
        """Initialize database schema."""
        if self._initialized:
            return

        async with self._connection() as conn:
            # PostgreSQL doesn't support executescript, run individually
            statements = POSTGRES_SCHEMA.split(';')
            for statement in statements:
                if statement.strip():
                    await conn.execute(statement)

        self._initialized = True

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool is not None:
            await self._pool.close()
```

**File:** `apps/backend/src/orcheo_backend/app/repository_postgres/schema.py`
```python
"""PostgreSQL schema for workflow repository."""

POSTGRES_SCHEMA = """
-- Workflows table
CREATE TABLE IF NOT EXISTS workflows (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Workflow versions table
CREATE TABLE IF NOT EXISTS workflow_versions (
    id SERIAL PRIMARY KEY,
    workflow_id INTEGER NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    config JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(workflow_id, version_number)
);

-- Workflow runs table
CREATE TABLE IF NOT EXISTS workflow_runs (
    id TEXT PRIMARY KEY,
    workflow_id INTEGER NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    version_id INTEGER REFERENCES workflow_versions(id) ON DELETE SET NULL,
    status TEXT NOT NULL,
    input JSONB,
    output JSONB,
    error TEXT,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_workflow_versions_workflow_id
    ON workflow_versions(workflow_id);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow_id
    ON workflow_runs(workflow_id);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_status
    ON workflow_runs(status);

-- JSONB indexes
CREATE INDEX IF NOT EXISTS idx_workflow_versions_config_gin
    ON workflow_versions USING GIN(config);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_metadata_gin
    ON workflow_runs USING GIN(metadata);
"""
```

### 6.2 Run History Store

**Current:** [apps/backend/src/orcheo_backend/app/history/sqlite_store.py](../../apps/backend/src/orcheo_backend/app/history/sqlite_store.py)

**New:** `apps/backend/src/orcheo_backend/app/history/postgres_store.py`

**Key Changes:**
1. Replace `aiosqlite` with `psycopg` (async)
2. Replace `PRAGMA table_info()` with information_schema queries:
   ```python
   # Old (SQLite)
   cursor = await conn.execute("PRAGMA table_info(execution_history)")

   # New (PostgreSQL)
   cursor = await conn.execute("""
       SELECT column_name
       FROM information_schema.columns
       WHERE table_name = 'execution_history'
   """)
   ```
3. Store trace data as JSONB instead of TEXT

### 6.3 Service Token Repository

**Current:** [apps/backend/src/orcheo_backend/app/service_token_repository/sqlite_repository.py](../../apps/backend/src/orcheo_backend/app/service_token_repository/sqlite_repository.py)

**New:** `apps/backend/src/orcheo_backend/app/service_token_repository/postgres_repository.py`

**Key Changes:**
1. **CRITICAL:** Currently uses **synchronous** sqlite3 - needs async PostgreSQL
2. Convert from sync context manager to async
3. Add token hashing using bcrypt or argon2
4. Add index on token hash for fast lookups

**Example Schema:**
```sql
CREATE TABLE IF NOT EXISTS service_tokens (
    id SERIAL PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,  -- bcrypt hash
    name TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_token_hash ON service_tokens(token_hash);
CREATE INDEX idx_expires_at ON service_tokens(expires_at) WHERE expires_at IS NOT NULL;
```

### 6.4 Agentensor Checkpoints

**Current:** [apps/backend/src/orcheo_backend/app/agentensor/checkpoint_store.py](../../apps/backend/src/orcheo_backend/app/agentensor/checkpoint_store.py)

**New:** `apps/backend/src/orcheo_backend/app/agentensor/postgres_checkpoint_store.py`

**Key Changes:**
1. Convert `runnable_config` and `metrics` to JSONB
2. Add GIN indexes for JSONB columns
3. Use native BOOLEAN for `is_best`
4. Use TIMESTAMP WITH TIME ZONE for `created_at`

### 6.5 ChatKit Store

**Current:** [apps/backend/src/orcheo_backend/app/chatkit_store_sqlite/](../../apps/backend/src/orcheo_backend/app/chatkit_store_sqlite/)

**New Directory:** `apps/backend/src/orcheo_backend/app/chatkit_store_postgres/`

**Files to Create:**
- `base.py` - PostgreSQL connection management
- `schema.py` - PostgreSQL DDL
- `store.py` - Store operations
- `threads.py` - Thread management
- `items.py` - Item storage
- `attachments.py` - Attachment handling

**Key Schema Changes:**
```sql
-- Example: threads table
CREATE TABLE IF NOT EXISTS chatkit_threads (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,  -- JSONB instead of TEXT
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Example: messages table
CREATE TABLE IF NOT EXISTS chatkit_messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES chatkit_threads(id) ON DELETE CASCADE,
    content JSONB NOT NULL,                       -- JSONB for message content
    role TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_messages_thread_id ON chatkit_messages(thread_id);
CREATE INDEX idx_messages_created_at ON chatkit_messages(created_at);
CREATE INDEX idx_messages_content_gin ON chatkit_messages USING GIN(content);
```

### 6.6 Vault Storage (OPTIONAL)

**Current:** [src/orcheo/vault/](../../src/orcheo/vault/)
- `sqlite_core.py`
- `sqlite_credentials.py`
- `sqlite_storage.py`
- `sqlite_templates.py`
- `sqlite_alerts.py`

**Decision Point:** Keep SQLite for vault?

**Option 1: Keep SQLite (RECOMMENDED for local hosting)**
- **Pros:** Simpler security model, no network exposure, easier local file permissions
- **Cons:** Not scalable for multi-node deployments

**Option 2: Migrate to PostgreSQL**
- **Pros:** Centralized credential management, better for multi-node
- **Cons:** Requires additional encryption layer, network security considerations
- **Implementation:** Use PostgreSQL pgcrypto extension for encryption at rest

**Recommendation:** Keep vault as SQLite for local hosting use case. Revisit if multi-node deployment becomes a requirement.

---

## 7. Testing Strategy

### 7.1 Unit Tests

**For each new PostgreSQL implementation:**

1. **Connection Management Tests**
   ```python
   # tests/backend/test_postgres_connection.py
   async def test_connection_pool_initialization():
       """Test connection pool initializes correctly."""

   async def test_connection_pool_exhaustion():
       """Test behavior when pool is exhausted."""

   async def test_connection_retry_logic():
       """Test connection retry with exponential backoff."""
   ```

2. **CRUD Operation Tests**
   ```python
   # tests/backend/test_postgres_workflow_repository.py
   async def test_create_workflow():
       """Test workflow creation with PostgreSQL."""

   async def test_list_workflows_pagination():
       """Test pagination with large datasets."""

   async def test_update_workflow_concurrent():
       """Test concurrent workflow updates."""
   ```

3. **Schema Migration Tests**
   ```python
   # tests/backend/test_postgres_schema.py
   async def test_schema_initialization():
       """Test initial schema creation."""

   async def test_schema_migration():
       """Test schema version upgrades."""
   ```

### 7.2 Integration Tests

**File:** `tests/integration/test_postgres_integration.py`

```python
import pytest
from orcheo.config import AppSettings

@pytest.fixture
async def postgres_settings():
    """Fixture providing PostgreSQL settings."""
    return AppSettings(
        repository_backend="postgres",
        postgres_dsn="postgresql://test:test@localhost:5432/orcheo_test",
    )

@pytest.mark.integration
async def test_end_to_end_workflow_execution(postgres_settings):
    """Test complete workflow execution with PostgreSQL backend."""
    # 1. Create workflow
    # 2. Create version
    # 3. Execute workflow
    # 4. Check run history
    # 5. Verify checkpoints
    pass

@pytest.mark.integration
async def test_concurrent_workflow_execution(postgres_settings):
    """Test multiple workflows executing concurrently."""
    pass
```

### 7.3 Performance Tests

**File:** `tests/performance/test_postgres_performance.py`

```python
import pytest
import asyncio
from time import perf_counter

@pytest.mark.performance
async def test_query_performance():
    """Test query response times under load."""
    # Target: < 100ms for simple queries
    pass

@pytest.mark.performance
async def test_concurrent_writes():
    """Test write throughput with concurrent clients."""
    # Target: 1000 writes/sec
    pass

@pytest.mark.performance
async def test_connection_pool_under_load():
    """Test connection pool behavior under high load."""
    # Simulate 100 concurrent connections
    pass
```

### 7.4 Compatibility Tests

**Ensure SQLite functionality is not broken:**

```python
@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
async def test_workflow_crud_compatibility(backend):
    """Test CRUD operations work identically on both backends."""
    pass
```

### 7.5 Test Database Setup

**Docker Compose for Testing:**

```yaml
# docker-compose.test.yml
version: '3.8'
services:
  postgres-test:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: orcheo_test
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
    ports:
      - "5432:5432"
    volumes:
      - postgres-test-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres-test-data:
```

**Run tests:**
```bash
# Start test database
docker-compose -f docker-compose.test.yml up -d

# Run tests with PostgreSQL
REPOSITORY_BACKEND=postgres \
POSTGRES_DSN=postgresql://test:test@localhost:5432/orcheo_test \
pytest tests/backend/test_postgres_*.py

# Cleanup
docker-compose -f docker-compose.test.yml down -v
```

---

## 8. Deployment & Operations

### 8.1 Local Development Setup

**Prerequisites:**
```bash
# Install PostgreSQL
# macOS
brew install postgresql@16
brew services start postgresql@16

# Ubuntu/Debian
sudo apt-get install postgresql-16
sudo systemctl start postgresql

# Create database and user
createdb orcheo_dev
createuser -P orcheo_user  # Set password when prompted
psql -d orcheo_dev -c "GRANT ALL PRIVILEGES ON DATABASE orcheo_dev TO orcheo_user;"
```

**Configuration:**
```bash
# .env.local
REPOSITORY_BACKEND=postgres
POSTGRES_DSN=postgresql://orcheo_user:your_password@localhost:5432/orcheo_dev

CHECKPOINT_BACKEND=postgres
# Can reuse same DSN or use different database
```

### 8.2 Docker Deployment

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  orcheo:
    build: .
    ports:
      - "8000:8000"
    environment:
      REPOSITORY_BACKEND: postgres
      POSTGRES_DSN: postgresql://orcheo:orcheo@postgres:5432/orcheo
      CHECKPOINT_BACKEND: postgres
    depends_on:
      postgres:
        condition: service_healthy

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: orcheo
      POSTGRES_USER: orcheo
      POSTGRES_PASSWORD: orcheo  # Change in production!
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql  # Initial schema
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U orcheo"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres-data:
```

**init.sql (optional):**
```sql
-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Schemas will be created by application on first run
```

### 8.3 Production Deployment Considerations

**Security:**
- [ ] Use SSL/TLS for PostgreSQL connections (`sslmode=require` in DSN)
- [ ] Store credentials in secrets manager (AWS Secrets Manager, HashiCorp Vault)
- [ ] Use least-privilege database user (no SUPERUSER, CREATEDB, CREATEROLE)
- [ ] Enable row-level security (RLS) if multi-tenant
- [ ] Regularly rotate database passwords

**High Availability:**
- [ ] Set up PostgreSQL replication (primary + replica)
- [ ] Use connection pooler (PgBouncer) for connection management
- [ ] Implement read replicas for read-heavy workloads
- [ ] Configure automatic failover (Patroni, repmgr)

**Backup & Recovery:**
- [ ] Set up automated daily backups (pg_dump or WAL archiving)
- [ ] Store backups in separate location (S3, GCS)
- [ ] Test restoration process regularly
- [ ] Implement point-in-time recovery (PITR)

**Monitoring:**
- [ ] Track connection pool metrics (active, idle, waiting)
- [ ] Monitor query performance (slow query log)
- [ ] Alert on replication lag
- [ ] Track database size growth
- [ ] Monitor checkpoint activity

**Performance Tuning:**
- [ ] Run VACUUM ANALYZE regularly
- [ ] Monitor and optimize indexes
- [ ] Partition large tables (runs, history)
- [ ] Use table partitioning for time-series data

### 8.4 Cloud Deployments

**AWS RDS:**
```bash
# Example DSN
POSTGRES_DSN=postgresql://orcheo:password@orcheo-db.xxxxx.us-west-2.rds.amazonaws.com:5432/orcheo?sslmode=require
```

**Google Cloud SQL:**
```bash
# Using Cloud SQL Proxy
POSTGRES_DSN=postgresql://orcheo:password@/orcheo?host=/cloudsql/project:region:instance
```

**Azure Database for PostgreSQL:**
```bash
POSTGRES_DSN=postgresql://orcheo@servername:password@servername.postgres.database.azure.com:5432/orcheo?sslmode=require
```

---

## 9. Rollback Plan

### 9.1 Configuration Rollback

**Simple rollback via configuration:**
```bash
# Revert to SQLite in .env or config
REPOSITORY_BACKEND=sqlite
CHECKPOINT_BACKEND=sqlite

# Restart application
systemctl restart orcheo
```

### 9.2 Data Migration Rollback

**If data was migrated from SQLite → PostgreSQL:**

1. **Stop application**
   ```bash
   systemctl stop orcheo
   ```

2. **Restore SQLite backups**
   ```bash
   cp ~/.orcheo/backups/workflows.sqlite.backup ~/.orcheo/workflows.sqlite
   cp ~/.orcheo/backups/checkpoints.sqlite.backup ~/.orcheo/checkpoints.sqlite
   ```

3. **Revert configuration**
   ```bash
   REPOSITORY_BACKEND=sqlite
   CHECKPOINT_BACKEND=sqlite
   ```

4. **Restart application**
   ```bash
   systemctl start orcheo
   ```

### 9.3 Code Rollback

**Using Git:**
```bash
# Identify last good commit
git log --oneline

# Create rollback branch
git checkout -b rollback-postgres-migration

# Revert merge commit
git revert -m 1 <merge-commit-hash>

# Deploy rollback
git push origin rollback-postgres-migration
```

### 9.4 Rollback Validation

**Post-rollback checks:**
- [ ] All workflows load correctly
- [ ] Workflow execution works
- [ ] Run history is accessible
- [ ] Checkpoints restore properly
- [ ] No data loss detected
- [ ] All tests pass

---

## 10. Timeline & Resources

### 10.1 Estimated Timeline (1 Engineer)

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| **Phase 1: Foundation** | Week 1 (5 days) | - Config updates<br>- PostgreSQL connection infra<br>- Workflow Repository implementation<br>- Core tests passing |
| **Phase 2: Critical Features** | Week 2 (5 days) | - Run History Store<br>- Service Token Repository<br>- Agentensor Checkpoints<br>- Integration tests passing |
| **Phase 3: Auxiliary Features** | Week 3 (5 days) | - ChatKit Store<br>- Performance optimization<br>- Advanced features<br>- All tests passing |
| **Phase 4: Polish & Docs** | Week 4 (5 days) | - Data migration tools<br>- Deployment automation<br>- Documentation<br>- Production readiness review |
| **Total** | **4 weeks** | Full PostgreSQL support for local hosting |

### 10.2 Accelerated Timeline (2 Engineers)

| Phase | Duration | Team Split |
|-------|----------|------------|
| **Phase 1** | 3 days | Engineer A: Workflow Repo<br>Engineer B: Config + History Store |
| **Phase 2** | 4 days | Engineer A: Agentensor + ChatKit<br>Engineer B: Service Tokens + Testing |
| **Phase 3** | 3 days | Engineer A: Performance<br>Engineer B: Migration tools |
| **Total** | **2 weeks** | Parallel implementation |

### 10.3 Resource Requirements

**Development Team:**
- 1-2 Backend Engineers (Python, FastAPI, PostgreSQL)
- 0.5 DevOps Engineer (Docker, deployment automation)

**Infrastructure:**
- Development PostgreSQL instance (local or cloud)
- Staging PostgreSQL instance (for integration testing)
- CI/CD pipeline updates (GitHub Actions, GitLab CI)

**Tools & Services:**
- PostgreSQL 14+ server
- Docker & Docker Compose
- Database migration tools (Alembic or custom)
- Monitoring (pgAdmin, Grafana)

### 10.4 Success Metrics

**Technical Metrics:**
- [ ] All 7 subsystems have PostgreSQL implementations
- [ ] 100% test coverage for new code
- [ ] Zero regressions in SQLite functionality
- [ ] Query performance < 100ms for 95th percentile
- [ ] Connection pool handles 100+ concurrent connections

**Operational Metrics:**
- [ ] Deployment automation tested in staging
- [ ] Documentation complete and reviewed
- [ ] Rollback plan tested successfully
- [ ] Production deployment successful with zero downtime

---

## Appendix A: File Locations Reference

### Configuration Files
- [src/orcheo/config/types.py:7](../../src/orcheo/config/types.py#L7) - `RepositoryBackend` type definition
- [src/orcheo/config/app_settings.py:87-109](../../src/orcheo/config/app_settings.py#L87-L109) - Backend validators
- [src/orcheo/config/defaults.py](../../src/orcheo/config/defaults.py) - Default configuration values

### Current SQLite Implementations
- [apps/backend/src/orcheo_backend/app/repository_sqlite/](../../apps/backend/src/orcheo_backend/app/repository_sqlite/) - Workflow repository
- [apps/backend/src/orcheo_backend/app/history/sqlite_store.py](../../apps/backend/src/orcheo_backend/app/history/sqlite_store.py) - Run history
- [apps/backend/src/orcheo_backend/app/agentensor/checkpoint_store.py](../../apps/backend/src/orcheo_backend/app/agentensor/checkpoint_store.py) - Agentensor checkpoints
- [apps/backend/src/orcheo_backend/app/chatkit_store_sqlite/](../../apps/backend/src/orcheo_backend/app/chatkit_store_sqlite/) - ChatKit storage
- [apps/backend/src/orcheo_backend/app/service_token_repository/sqlite_repository.py](../../apps/backend/src/orcheo_backend/app/service_token_repository/sqlite_repository.py) - Service tokens
- [src/orcheo/vault/](../../src/orcheo/vault/) - Vault storage

### Protocol Interfaces
- [apps/backend/src/orcheo_backend/app/repository/protocol.py](../../apps/backend/src/orcheo_backend/app/repository/protocol.py) - Repository protocol interface

### Provider System
- [apps/backend/src/orcheo_backend/app/providers.py](../../apps/backend/src/orcheo_backend/app/providers.py) - Factory functions for backends

### Existing PostgreSQL Support
- [src/orcheo/persistence.py:19-98](../../src/orcheo/persistence.py#L19-L98) - LangGraph checkpoint PostgreSQL support
- [tests/integration/test_postgres_persistence.py](../../tests/integration/test_postgres_persistence.py) - Existing PostgreSQL tests

---

## Appendix B: SQLite-Specific Code Patterns

### Pattern 1: PRAGMA Statements
```python
# SQLite
await conn.execute("PRAGMA journal_mode = WAL;")
await conn.execute("PRAGMA foreign_keys = ON;")

# PostgreSQL
# WAL mode: configured at server level (postgresql.conf)
# Foreign keys: always enforced (no need to enable)
```

### Pattern 2: Schema Introspection
```python
# SQLite
cursor = await conn.execute("PRAGMA table_info(my_table)")

# PostgreSQL
cursor = await conn.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'my_table'
""")
```

### Pattern 3: JSON Storage
```python
# SQLite (JSON as TEXT)
await conn.execute(
    "INSERT INTO table (data) VALUES (?)",
    (json.dumps({"key": "value"}),)
)

# PostgreSQL (Native JSONB)
await conn.execute(
    "INSERT INTO table (data) VALUES (%s)",
    (Json({"key": "value"}),)  # psycopg3 Json adapter
)
```

### Pattern 4: Boolean Values
```python
# SQLite (INTEGER 0/1)
await conn.execute(
    "INSERT INTO table (is_active) VALUES (?)",
    (1,)  # True as 1
)

# PostgreSQL (Native BOOLEAN)
await conn.execute(
    "INSERT INTO table (is_active) VALUES (%s)",
    (True,)  # Native boolean
)
```

### Pattern 5: Timestamp Handling
```python
# SQLite (TEXT)
from datetime import datetime
await conn.execute(
    "INSERT INTO table (created_at) VALUES (?)",
    (datetime.now().isoformat(),)
)

# PostgreSQL (TIMESTAMP WITH TIME ZONE)
from datetime import datetime, timezone
await conn.execute(
    "INSERT INTO table (created_at) VALUES (%s)",
    (datetime.now(timezone.utc),)  # Timezone-aware datetime
)
```

---

## Appendix C: Useful PostgreSQL Commands

### Schema Management
```sql
-- List all tables
\dt

-- Describe table
\d table_name

-- List indexes
\di

-- Show table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Performance Analysis
```sql
-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM workflows WHERE name = 'test';

-- Check slow queries
SELECT
    query,
    calls,
    total_exec_time,
    mean_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;
```

### Connection Monitoring
```sql
-- Active connections
SELECT
    pid,
    usename,
    application_name,
    client_addr,
    state,
    query
FROM pg_stat_activity
WHERE state = 'active';

-- Kill connection
SELECT pg_terminate_backend(pid);
```

### Maintenance
```sql
-- Vacuum and analyze
VACUUM ANALYZE workflows;

-- Reindex
REINDEX TABLE workflows;

-- Check for bloat
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS indexes_size
FROM pg_tables
WHERE schemaname = 'public';
```

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-19 | Claude Code | Initial draft based on codebase analysis |

---

**Next Steps:**
1. Review this plan with engineering team
2. Get stakeholder approval for timeline and resources
3. Set up project tracking (GitHub Issues, Jira)
4. Begin Phase 1 implementation
5. Schedule weekly review meetings during implementation

**Questions or Concerns:**
- Contact: [Add engineering lead contact]
- Slack: [Add relevant Slack channel]
- GitHub: [Add repository link for issues]
