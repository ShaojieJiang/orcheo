# PostgreSQL Migration Plan (Production & Local)

This guide describes how to enable PostgreSQL across Orcheo's persistence
surfaces (workflow repository, LangGraph checkpoints, and related services) and
how to roll back to SQLite if needed. All configuration is loaded with the
`ORCHEO_` environment variable prefix via `src/orcheo/config/loader.py`; the
examples below use that prefix everywhere to ensure settings are applied.

## Quick start (local validation)

Run targeted tests against PostgreSQL to confirm connectivity and schema
compatibility before rolling out more broadly:

```bash
export ORCHEO_REPOSITORY_BACKEND=postgres
export ORCHEO_CHECKPOINT_BACKEND=postgres
export ORCHEO_CHATKIT_BACKEND=postgres
export ORCHEO_POSTGRES_DSN=postgresql://user:pass@localhost:5432/orcheo

uv run pytest tests/integration/test_postgres_persistence.py -q
uv run pytest tests/test_persistence.py -q
```

These tests cover both the repository factory and the LangGraph checkpoint
adapter. Leaving off the `ORCHEO_` prefix will cause the loader to ignore the
variables and default back to SQLite, so keep the prefix in every command.

## Local `.env` template

Create a `.env` file to run the FastAPI app or CLI against PostgreSQL:

```dotenv
ORCHEO_REPOSITORY_BACKEND=postgres
ORCHEO_CHECKPOINT_BACKEND=postgres
ORCHEO_CHATKIT_BACKEND=postgres
ORCHEO_POSTGRES_DSN=postgresql://user:pass@localhost:5432/orcheo
ORCHEO_HOST=0.0.0.0
ORCHEO_PORT=8000
```

Optional values for performance tuning:

- `ORCHEO_POSTGRES_POOL_MIN_SIZE` / `ORCHEO_POSTGRES_POOL_MAX_SIZE` (future)
- `ORCHEO_POSTGRES_POOL_TIMEOUT` (future)

## Docker Compose example

```yaml
services:
  orcheo:
    image: ghcr.io/orcheo/app:latest
    environment:
      ORCHEO_REPOSITORY_BACKEND: postgres
      ORCHEO_CHECKPOINT_BACKEND: postgres
      ORCHEO_CHATKIT_BACKEND: postgres
      ORCHEO_POSTGRES_DSN: postgresql://user:pass@postgres:5432/orcheo
      ORCHEO_HOST: 0.0.0.0
      ORCHEO_PORT: 8000
    ports:
      - "8000:8000"
    depends_on:
      - postgres
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: orcheo
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata: {}
```

## Cloud deployment DSN

Supply a managed PostgreSQL URL using the same prefix:

```bash
export ORCHEO_REPOSITORY_BACKEND=postgres
export ORCHEO_CHECKPOINT_BACKEND=postgres
export ORCHEO_CHATKIT_BACKEND=postgres
export ORCHEO_POSTGRES_DSN=postgresql://user:pass@db.example.com:5432/orcheo
```

For platforms that manage secrets, store `ORCHEO_POSTGRES_DSN` as a secret and
inject it at runtime.

## Rollback to SQLite

Switch back without data migration by resetting the backends and unsetting the
DSN:

```bash
export ORCHEO_REPOSITORY_BACKEND=sqlite
export ORCHEO_CHECKPOINT_BACKEND=sqlite
export ORCHEO_CHATKIT_BACKEND=sqlite
unset ORCHEO_POSTGRES_DSN
```

Existing SQLite file paths will revert to the defaults in
`src/orcheo/config/defaults.py` unless overridden.

## SQLite to PostgreSQL migration

Use the built-in migration tool to export SQLite data into checksummed batches,
import them into PostgreSQL, and validate row counts before switching the
backend configuration.

```bash
uv run python -m orcheo.tooling.postgres_migration export \\
  --output ./migration-export

uv run python -m orcheo.tooling.postgres_migration import \\
  --input ./migration-export \\
  --postgres-dsn postgresql://user:pass@localhost:5432/orcheo

uv run python -m orcheo.tooling.postgres_migration validate \\
  --input ./migration-export \\
  --postgres-dsn postgresql://user:pass@localhost:5432/orcheo
```

The export captures workflows, run history, agentensor checkpoints, service
tokens, and ChatKit threads. Vault data is excluded and should remain in its
existing backend. If an import is interrupted, re-run the import command; it
will resume from `migration-export/import_state.json`.

## Troubleshooting

- **Checksum mismatch**: Delete the affected batch file, re-run `export`, then
  retry the import for that export directory.
- **Validation mismatch**: Re-run `validate` after confirming all services are
  pointed at the same PostgreSQL DSN and no new SQLite writes occurred.
