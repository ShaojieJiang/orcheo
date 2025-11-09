# Environment Variables

This document catalogues every environment variable consumed by the Orcheo
project and the components that rely on them. Unless noted otherwise, backend
services read configuration via Dynaconf with the `ORCHEO_` prefix.

## Core runtime configuration (backend)

| Variable | Default | Purpose |
| --- | --- | --- |
| `ORCHEO_CHECKPOINT_BACKEND` | `sqlite` | Selects the checkpoint persistence backend (`sqlite` or `postgres`). See [config.py](../src/orcheo/config.py). |
| `ORCHEO_SQLITE_PATH` | `~/.orcheo/checkpoints.sqlite` | Path to the SQLite database when `sqlite` checkpoints are enabled. See [config.py](../src/orcheo/config.py). |
| `ORCHEO_POSTGRES_DSN` | _none_ | Database connection string required when `ORCHEO_CHECKPOINT_BACKEND=postgres`. See [config.py](../src/orcheo/config.py). |
| `ORCHEO_REPOSITORY_BACKEND` | `sqlite` | Controls the workflow repository backend (`sqlite` or `inmemory`). See [config.py](../src/orcheo/config.py). |
| `ORCHEO_REPOSITORY_SQLITE_PATH` | `~/.orcheo/workflows.sqlite` | Location of the workflow repository SQLite database. See [config.py](../src/orcheo/config.py). |
| `ORCHEO_CHATKIT_SQLITE_PATH` | `~/.orcheo/chatkit.sqlite` | Storage location for ChatKit conversation history when using SQLite storage. See [config.py](../src/orcheo/config.py) and [chatkit/server.py](../apps/backend/src/orcheo_backend/app/chatkit/server.py). |
| `ORCHEO_CHATKIT_STORAGE_PATH` | `~/.orcheo/chatkit` | Filesystem directory used by ChatKit for attachments and other assets. See [config.py](../src/orcheo/config.py). |
| `ORCHEO_CHATKIT_RETENTION_DAYS` | `30` | Number of days ChatKit conversation history is retained before pruning. See [config.py](../src/orcheo/config.py) and [apps/backend/app/__init__.py](../apps/backend/src/orcheo_backend/app/__init__.py). |
| `ORCHEO_HOST` | `0.0.0.0` | Network bind address for the FastAPI service. See [config.py](../src/orcheo/config.py). |
| `ORCHEO_PORT` | `8000` | TCP port exposed by the FastAPI service (validated to be an integer). See [config.py](../src/orcheo/config.py). |
| `ORCHEO_CORS_ALLOW_ORIGINS` | `["http://localhost:5173","http://127.0.0.1:5173"]` | Comma-separated string or JSON array of browser origins allowed to call the API with credentials (used for ChatKit/public Canvas). Set this to your deployed Canvas/public hostnames in production. |

### Vault configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `ORCHEO_VAULT_BACKEND` | `file` | Chooses credential vault backend (`file`, `inmemory`, or `aws_kms`). See [config.py](../src/orcheo/config.py). |
| `ORCHEO_VAULT_LOCAL_PATH` | `~/.orcheo/vault.sqlite` | Filesystem location for the file-backed vault database. See [config.py](../src/orcheo/config.py). |
| `ORCHEO_VAULT_ENCRYPTION_KEY` | _none_ | Pre-shared encryption key required for `aws_kms` vaults and used when available for other backends. See [config.py](../src/orcheo/config.py). |
| `ORCHEO_VAULT_AWS_REGION` | _none_ | AWS region expected when `ORCHEO_VAULT_BACKEND=aws_kms`. See [config.py](../src/orcheo/config.py). |
| `ORCHEO_VAULT_AWS_KMS_KEY_ID` | _none_ | Identifier of the AWS KMS key to use with the vault when `aws_kms` is active. See [config.py](../src/orcheo/config.py). |
| `ORCHEO_VAULT_TOKEN_TTL_SECONDS` | `3600` | Lifetime for issued vault access tokens, validated to be a positive integer. See [config.py](../src/orcheo/config.py). |

## Authentication service

| Variable | Default | Purpose |
| --- | --- | --- |
| `ORCHEO_AUTH_MODE` | `optional` | Governs whether authentication is disabled, optional, or required for API calls. See [authentication.py](../apps/backend/src/orcheo_backend/app/authentication.py). |
| `ORCHEO_AUTH_JWT_SECRET` | _none_ | Shared secret for signing or validating symmetric JWTs. See [authentication.py](../apps/backend/src/orcheo_backend/app/authentication.py). |
| `ORCHEO_AUTH_JWKS_URL` | _none_ | Remote JWKS endpoint for asymmetric JWT validation. See [authentication.py](../apps/backend/src/orcheo_backend/app/authentication.py). |
| `ORCHEO_AUTH_JWKS` / `ORCHEO_AUTH_JWKS_STATIC` | _none_ | Inline JWKS definitions accepted as JSON text or structured data. See [authentication.py](../apps/backend/src/orcheo_backend/app/authentication.py). |
| `ORCHEO_AUTH_JWKS_CACHE_TTL` | `300` | Cache duration (seconds) for downloaded JWKS documents. See [authentication.py](../apps/backend/src/orcheo_backend/app/authentication.py). |
| `ORCHEO_AUTH_JWKS_TIMEOUT` | `5.0` | Timeout (seconds) for HTTP requests when fetching JWKS documents. See [authentication.py](../apps/backend/src/orcheo_backend/app/authentication.py). |
| `ORCHEO_AUTH_ALLOWED_ALGORITHMS` | `RS256, HS256` | Restricts acceptable JWT algorithms; defaults to both RS256 and HS256. See [authentication.py](../apps/backend/src/orcheo_backend/app/authentication.py). |
| `ORCHEO_AUTH_AUDIENCE` | _none_ | Expected JWT audience values (comma or JSON-delimited). See [authentication.py](../apps/backend/src/orcheo_backend/app/authentication.py). |
| `ORCHEO_AUTH_ISSUER` | _none_ | Expected JWT issuer claim used during validation. See [authentication.py](../apps/backend/src/orcheo_backend/app/authentication.py). |
| `ORCHEO_AUTH_SERVICE_TOKEN_DB_PATH` | `~/.orcheo/service_tokens.sqlite` | Path to the SQLite database storing service tokens. Defaults to the same directory as `ORCHEO_REPOSITORY_SQLITE_PATH`. Service tokens are now managed via the CLI (`orcheo token`) or API endpoints (`/api/admin/service-tokens`) and stored in the database with full audit logging. See [authentication.py](../apps/backend/src/orcheo_backend/app/authentication.py) and [service_token_repository.py](../apps/backend/src/orcheo_backend/app/service_token_repository.py). |
| `ORCHEO_AUTH_RATE_LIMIT_IP` | `0` | Maximum authentication failures per IP before temporary blocking (0 disables the limit). See [authentication.py](../apps/backend/src/orcheo_backend/app/authentication.py). |
| `ORCHEO_AUTH_RATE_LIMIT_IDENTITY` | `0` | Maximum failures per identity before rate limiting (0 disables the limit). See [authentication.py](../apps/backend/src/orcheo_backend/app/authentication.py). |
| `ORCHEO_AUTH_RATE_LIMIT_INTERVAL` | `60` | Sliding-window interval (seconds) for rate-limit counters. See [authentication.py](../apps/backend/src/orcheo_backend/app/authentication.py). |
| `ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN` | _none_ | **Bootstrap token for initial setup**: A long-lived service token read directly from the environment (not stored in the database). This token is intended for bootstrapping authentication when no persistent tokens exist yet. It grants full admin access by default and should be removed after creating persistent tokens via the CLI or API. Use constant-time comparison for security. See [authentication.py](../apps/backend/src/orcheo_backend/app/authentication.py). |
| `ORCHEO_AUTH_BOOTSTRAP_TOKEN_SCOPES` | `admin:*` | Comma or space-delimited scopes granted to the bootstrap service token. Defaults to full admin access (`admin:tokens:read`, `admin:tokens:write`, `workflows:read`, `workflows:write`, `workflows:execute`, `vault:read`, `vault:write`). See [authentication.py](../apps/backend/src/orcheo_backend/app/authentication.py). |
| `ORCHEO_AUTH_BOOTSTRAP_TOKEN_EXPIRES_AT` | _none_ | Optional expiration timestamp (ISO 8601 or UNIX epoch) applied to the bootstrap service token. When the timestamp passes, the token is rejected with `auth.token_expired`. See [authentication.py](../apps/backend/src/orcheo_backend/app/authentication.py). |

### Service token management

Service tokens are no longer configured via environment variables. Instead, they are managed dynamically through:

- **CLI commands**: `orcheo token create`, `orcheo token list`, `orcheo token rotate`, `orcheo token revoke`
- **API endpoints**: `/api/admin/service-tokens` (requires `admin:tokens:read` or `admin:tokens:write` scopes)

All service tokens are stored in a SQLite database with SHA256-hashed secrets, never plaintext. The database includes full audit logging of token creation, usage, rotation, and revocation events. See [service_token_endpoints.py](../apps/backend/src/orcheo_backend/app/service_token_endpoints.py) for API details and [cli/service_token.py](../packages/sdk/src/orcheo_sdk/cli/service_token.py) for CLI usage.

## ChatKit session tokens

| Variable | Default | Purpose |
| --- | --- | --- |
| `ORCHEO_CHATKIT_TOKEN_SIGNING_KEY` | _none_ | Primary secret for signing ChatKit session JWTs; required unless a client secret is supplied. See [chatkit_tokens.py](../apps/backend/src/orcheo_backend/app/chatkit_tokens.py). |
| `ORCHEO_CHATKIT_CLIENT_SECRET` | _none_ | Alternate secret used when a dedicated signing key is not configured (supports per-workflow overrides via `CHATKIT_CLIENT_SECRET_<WORKFLOW_ID>`). See [chatkit_tokens.py](../apps/backend/src/orcheo_backend/app/chatkit_tokens.py) and the [backend README](../apps/backend/README.md). |
| `ORCHEO_CHATKIT_TOKEN_ISSUER` | `orcheo.chatkit` | Overrides the issuer claim embedded in ChatKit session tokens. See [chatkit_tokens.py](../apps/backend/src/orcheo_backend/app/chatkit_tokens.py). |
| `ORCHEO_CHATKIT_TOKEN_AUDIENCE` | `chatkit` | Custom audience claim for ChatKit tokens. See [chatkit_tokens.py](../apps/backend/src/orcheo_backend/app/chatkit_tokens.py). |
| `ORCHEO_CHATKIT_TOKEN_TTL_SECONDS` | `300` (minimum `60`) | Token lifetime in seconds; values below 60 are coerced up to ensure safety. See [chatkit_tokens.py](../apps/backend/src/orcheo_backend/app/chatkit_tokens.py). |
| `ORCHEO_CHATKIT_TOKEN_ALGORITHM` | `HS256` | JWT signing algorithm used for ChatKit session tokens. See [chatkit_tokens.py](../apps/backend/src/orcheo_backend/app/chatkit_tokens.py). |

### ChatKit rate-limit tuning

| Variable | Default | Purpose |
| --- | --- | --- |
| `ORCHEO_CHATKIT_RATE_LIMIT_IP_LIMIT` / `ORCHEO_CHATKIT_RATE_LIMIT_IP_INTERVAL` | `120` / `60` | Per-IP request cap and interval (seconds) enforced by `/api/chatkit`. See [chatkit.py](../apps/backend/src/orcheo_backend/app/routers/chatkit.py) and [chatkit_rate_limit_settings.py](../src/orcheo/config/chatkit_rate_limit_settings.py). |
| `ORCHEO_CHATKIT_RATE_LIMIT_JWT_LIMIT` / `ORCHEO_CHATKIT_RATE_LIMIT_JWT_INTERVAL` | `120` / `60` | Sliding-window limit for JWT-authenticated requests and its interval (seconds). |
| `ORCHEO_CHATKIT_RATE_LIMIT_PUBLISH_LIMIT` / `ORCHEO_CHATKIT_RATE_LIMIT_PUBLISH_INTERVAL` | `60` / `60` | Rate limit applied to publish-token authenticated requests and the evaluation window. |
| `ORCHEO_CHATKIT_RATE_LIMIT_SESSION_LIMIT` / `ORCHEO_CHATKIT_RATE_LIMIT_SESSION_INTERVAL` | `60` / `60` | Limits repeated ChatKit session initialisation attempts per session identifier within the supplied window. |

## CLI and SDK configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `ORCHEO_API_URL` | `http://localhost:8000` | Base URL used by the CLI and SDK when invoking the Orcheo backend. See [cli/config.py](../packages/sdk/src/orcheo_sdk/cli/config.py). |
| `ORCHEO_SERVICE_TOKEN` | _none_ | Service authentication token supplied to the CLI and SDK, and embedded in generated code snippets. See [cli/config.py](../packages/sdk/src/orcheo_sdk/cli/config.py) and [services/codegen.py](../packages/sdk/src/orcheo_sdk/services/codegen.py). |
| `ORCHEO_PROFILE` | `default` | Selects which CLI profile to load from `cli.toml`; can be overridden per command. See [cli/config.py](../packages/sdk/src/orcheo_sdk/cli/config.py). |
| `ORCHEO_CONFIG_DIR` | `~/.config/orcheo` | Overrides the directory containing CLI configuration files. See [cli/config.py](../packages/sdk/src/orcheo_sdk/cli/config.py). |
| `ORCHEO_CACHE_DIR` | `~/.cache/orcheo` | Overrides the cache directory used for offline CLI data. See [cli/config.py](../packages/sdk/src/orcheo_sdk/cli/config.py). |
| `_TYPER_COMPLETE*` / `_ORCHEO_COMPLETE*` | _managed by Typer_ | Internal flags Typer sets during shell completion to avoid running full CLI initialization. See [cli/main.py](../packages/sdk/src/orcheo_sdk/cli/main.py). |

## Frontend (Canvas) build-time configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_ORCHEO_BACKEND_URL` | `http://localhost:8000` | Provides the base HTTP/WebSocket endpoint for the Canvas UI; invalid values fall back to the default URL. See [lib/config.ts](../apps/canvas/src/lib/config.ts) and [vite-env.d.ts](../apps/canvas/src/vite-env.d.ts). |

## Logging and environment detection

| Variable | Default | Purpose |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | Controls the log level applied to FastAPI, Uvicorn, and Orcheo loggers. See [apps/backend/app/__init__.py](../apps/backend/src/orcheo_backend/app/__init__.py). |
| `ORCHEO_ENV` / `ENVIRONMENT` / `NODE_ENV` | `production` | Determine whether the backend treats the environment as development for sensitive debugging output. See [apps/backend/app/__init__.py](../apps/backend/src/orcheo_backend/app/__init__.py). |
| `LOG_SENSITIVE_DEBUG` | `0` | When set to `1`, enables detailed debug logging even outside development environments. See [apps/backend/app/__init__.py](../apps/backend/src/orcheo_backend/app/__init__.py). |
