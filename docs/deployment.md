# Deployment Recipes

This guide captures reference deployment flows for running Orcheo locally during development and hosting the service for teams. Each recipe lists the required environment variables, supporting services, and common verification steps.

## Local Development (SQLite, single process)

This setup mirrors the default configuration that the tests exercise. It is ideal when you want to iterate on nodes, run the FastAPI server, and execute LangGraph workflows from the command line.

1. **Install dependencies**
   ```bash
   uv sync --all-groups
   ```
2. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
3. **Start the API server**
   ```bash
   make dev-server
   ```
4. **Run an example workflow**
   - Send a websocket message to `ws://localhost:8000/ws/workflow/<workflow_id>` with a payload matching the schema in `tests/test_main.py`.

**Verification**: Run `uv run pytest` to validate the environment. The test suite opens an SQLite connection through the same helper used by the server.

_Vault note_: The default `.env.example` keeps credentials in an in-memory vault suitable for quick iteration. Switch `ORCHEO_VAULT_BACKEND` to `file` when you want encrypted secrets to persist between restarts.

## Docker Compose (SQLite, multi-container)

Use this recipe when you want an isolated environment that mimics production without provisioning a database. It pairs the FastAPI app with a volume-mounted SQLite database.

1. **Create `docker-compose.yml`**
   ```yaml
   services:
     orcheo:
       build: .
       command: uvicorn orcheo_backend.app:app --host 0.0.0.0 --port 8000
       environment:
         ORCHEO_HOST: 0.0.0.0
         ORCHEO_PORT: "8000"
         ORCHEO_CHECKPOINT_BACKEND: sqlite
         ORCHEO_SQLITE_PATH: /data/orcheo.sqlite3
         ORCHEO_VAULT_BACKEND: file
         ORCHEO_VAULT_ENCRYPTION_KEY: change-me
         ORCHEO_VAULT_LOCAL_PATH: /data/vault.sqlite
         ORCHEO_VAULT_TOKEN_TTL_SECONDS: "3600"
       ports:
         - "8000:8000"
       volumes:
         - orcheo-data:/data
   volumes:
     orcheo-data:
   ```
2. **Build and start**
   ```bash
   docker compose up --build
   ```
3. **Connect**
   Access the API via `http://localhost:8000`. The checkpoint database is stored inside the named volume so runs persist across container restarts.

**Verification**: `docker compose exec orcheo uv run pytest tests/test_main.py` confirms the container is healthy.

_Vault note_: The compose example writes encrypted secrets to `/data/vault.sqlite`. Rotate `ORCHEO_VAULT_ENCRYPTION_KEY` regularly and back up the volume alongside the checkpoint database.

## Managed Hosting (PostgreSQL, async pool)

This deployment targets platforms such as Fly.io, Railway, or Kubernetes where Postgres is available as a managed service.

1. **Provision PostgreSQL**
   - Create a database and note the DSN, e.g. `postgresql://user:pass@host:5432/orcheo`.
   - Ensure the `psycopg[binary,pool]` and `langgraph[postgres]` extras are installed (already defined in `pyproject.toml`).
2. **Configure environment variables**
   ```bash
   export ORCHEO_CHECKPOINT_BACKEND=postgres
   export ORCHEO_POSTGRES_DSN=postgresql://user:pass@host:5432/orcheo
   export ORCHEO_HOST=0.0.0.0
   export ORCHEO_PORT=8000
   export ORCHEO_VAULT_BACKEND=aws_kms
   export ORCHEO_VAULT_ENCRYPTION_KEY=alias/orcheo-runtime
   export ORCHEO_VAULT_AWS_REGION=us-west-2
   export ORCHEO_VAULT_AWS_KMS_KEY_ID=1234abcd-12ab-34cd-56ef-1234567890ab
   export ORCHEO_VAULT_TOKEN_TTL_SECONDS=900
   ```
3. **Run database migrations (if any)**
   - Check in migration scripts under `deploy/migrations` (placeholder today).
   - Execute them via `psql` or your platform's migration runner.
4. **Deploy the application**
   - **Docker image**: Build with `docker build -t orcheo-app .` and push to your registry.
   - **Fly.io example**:
     ```bash
     fly launch --no-deploy
     fly secrets set ORCHEO_POSTGRES_DSN=...
     fly deploy
     ```
  - Ensure the container command starts uvicorn: `uvicorn orcheo_backend.app:app --host 0.0.0.0 --port ${PORT}`.
5. **Health checks**
   - Expose `/docs` and `/openapi.json` for HTTP checks.
   - Use `/ws/workflow/{workflow_id}` for synthetic workflow runs during smoke tests.

**Verification**: Run `uv run pytest tests/test_persistence.py` locally with the `ORCHEO_CHECKPOINT_BACKEND=postgres` environment variable set and a reachable Postgres DSN to mirror production behavior.

_Vault note_: Managed environments should prefer KMS-integrated vaults. Configure IAM policies so only the Orcheo runtime can decrypt with the specified key.

## Operational Tips

- **Secrets**: Prefer platform-specific secret managers (Fly Secrets, Railway variables, AWS Parameter Store) and never bake DSNs or vault encryption keys into images.
- **Observability**: Route application logs to structured logging (e.g., stdout + centralized collector) and enable tracing once Milestone 6 instrumentation lands.
- **Scaling**: The FastAPI app is stateless. Scale horizontally by adding replicas while pointing them at the same checkpoint database.
- **Backups**: Schedule database backups (pg_dump or managed snapshots) to protect workflow history and run states.

These recipes will evolve as additional milestones introduce credential vaulting, trigger services, and observability pipelines.
