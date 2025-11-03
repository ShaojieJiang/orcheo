# Environment Variables

This document catalogues every environment variable consumed by the Orcheo
project and the components that rely on them. Unless noted otherwise, backend
services read configuration via Dynaconf with the `ORCHEO_` prefix.

## Core runtime configuration (backend)

| Variable | Default | Purpose |
| --- | --- | --- |
| `ORCHEO_CHECKPOINT_BACKEND` | `sqlite` | Selects the checkpoint persistence backend (`sqlite` or `postgres`).【F:src/orcheo/config.py†L14-L31】【F:src/orcheo/config.py†L224-L233】 |
| `ORCHEO_SQLITE_PATH` | `~/.orcheo/checkpoints.sqlite` | Path to the SQLite database when `sqlite` checkpoints are enabled.【F:src/orcheo/config.py†L14-L31】【F:src/orcheo/config.py†L234-L246】 |
| `ORCHEO_POSTGRES_DSN` | _none_ | Database connection string required when `ORCHEO_CHECKPOINT_BACKEND=postgres`.【F:src/orcheo/config.py†L14-L31】【F:src/orcheo/config.py†L224-L233】 |
| `ORCHEO_REPOSITORY_BACKEND` | `sqlite` | Controls the workflow repository backend (`sqlite` or `inmemory`).【F:src/orcheo/config.py†L14-L31】【F:src/orcheo/config.py†L163-L175】 |
| `ORCHEO_REPOSITORY_SQLITE_PATH` | `~/.orcheo/workflows.sqlite` | Location of the workflow repository SQLite database.【F:src/orcheo/config.py†L14-L31】【F:src/orcheo/config.py†L234-L246】 |
| `ORCHEO_CHATKIT_SQLITE_PATH` | `~/.orcheo/chatkit.sqlite` | Storage location for ChatKit conversation history when using SQLite storage.【F:src/orcheo/config.py†L14-L31】【F:apps/backend/src/orcheo_backend/app/chatkit_service.py†L552-L567】 |
| `ORCHEO_CHATKIT_STORAGE_PATH` | `~/.orcheo/chatkit` | Filesystem directory used by ChatKit for attachments and other assets.【F:src/orcheo/config.py†L14-L31】【F:src/orcheo/config.py†L234-L246】 |
| `ORCHEO_CHATKIT_RETENTION_DAYS` | `30` | Number of days ChatKit conversation history is retained before pruning.【F:src/orcheo/config.py†L14-L31】【F:apps/backend/src/orcheo_backend/app/__init__.py†L205-L208】 |
| `ORCHEO_HOST` | `0.0.0.0` | Network bind address for the FastAPI service.【F:src/orcheo/config.py†L14-L31】【F:src/orcheo/config.py†L234-L247】 |
| `ORCHEO_PORT` | `8000` | TCP port exposed by the FastAPI service (validated to be an integer).【F:src/orcheo/config.py†L14-L31】【F:src/orcheo/config.py†L210-L223】 |

### Vault configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `ORCHEO_VAULT_BACKEND` | `file` | Chooses credential vault backend (`file`, `inmemory`, or `aws_kms`).【F:src/orcheo/config.py†L14-L118】 |
| `ORCHEO_VAULT_LOCAL_PATH` | `~/.orcheo/vault.sqlite` | Filesystem location for the file-backed vault database.【F:src/orcheo/config.py†L14-L118】 |
| `ORCHEO_VAULT_ENCRYPTION_KEY` | _none_ | Pre-shared encryption key required for `aws_kms` vaults and used when available for other backends.【F:src/orcheo/config.py†L14-L118】 |
| `ORCHEO_VAULT_AWS_REGION` | _none_ | AWS region expected when `ORCHEO_VAULT_BACKEND=aws_kms`.【F:src/orcheo/config.py†L14-L118】 |
| `ORCHEO_VAULT_AWS_KMS_KEY_ID` | _none_ | Identifier of the AWS KMS key to use with the vault when `aws_kms` is active.【F:src/orcheo/config.py†L14-L118】 |
| `ORCHEO_VAULT_TOKEN_TTL_SECONDS` | `3600` | Lifetime for issued vault access tokens, validated to be a positive integer.【F:src/orcheo/config.py†L14-L118】 |

## Authentication service

| Variable | Default | Purpose |
| --- | --- | --- |
| `ORCHEO_AUTH_MODE` | `optional` | Governs whether authentication is disabled, optional, or required for API calls.【F:apps/backend/src/orcheo_backend/app/authentication.py†L1069-L1104】 |
| `ORCHEO_AUTH_JWT_SECRET` | _none_ | Shared secret for signing or validating symmetric JWTs.【F:apps/backend/src/orcheo_backend/app/authentication.py†L1069-L1107】 |
| `ORCHEO_AUTH_JWKS_URL` | _none_ | Remote JWKS endpoint for asymmetric JWT validation.【F:apps/backend/src/orcheo_backend/app/authentication.py†L1069-L1108】 |
| `ORCHEO_AUTH_JWKS` / `ORCHEO_AUTH_JWKS_STATIC` | _none_ | Inline JWKS definitions accepted as JSON text or structured data.【F:apps/backend/src/orcheo_backend/app/authentication.py†L1078-L1104】【F:apps/backend/src/orcheo_backend/app/authentication.py†L1121-L1139】 |
| `ORCHEO_AUTH_JWKS_CACHE_TTL` | `300` | Cache duration (seconds) for downloaded JWKS documents.【F:apps/backend/src/orcheo_backend/app/authentication.py†L1074-L1117】 |
| `ORCHEO_AUTH_JWKS_TIMEOUT` | `5.0` | Timeout (seconds) for HTTP requests when fetching JWKS documents.【F:apps/backend/src/orcheo_backend/app/authentication.py†L1074-L1117】 |
| `ORCHEO_AUTH_ALLOWED_ALGORITHMS` | `RS256, HS256` | Restricts acceptable JWT algorithms; defaults to both RS256 and HS256.【F:apps/backend/src/orcheo_backend/app/authentication.py†L1081-L1112】 |
| `ORCHEO_AUTH_AUDIENCE` | _none_ | Expected JWT audience values (comma or JSON-delimited).【F:apps/backend/src/orcheo_backend/app/authentication.py†L1085-L1117】 |
| `ORCHEO_AUTH_ISSUER` | _none_ | Expected JWT issuer claim used during validation.【F:apps/backend/src/orcheo_backend/app/authentication.py†L1085-L1117】 |
| `ORCHEO_AUTH_SERVICE_TOKENS` | _none_ | JSON, comma-delimited, or plaintext list of service token secrets/hashes for machine access.【F:apps/backend/src/orcheo_backend/app/authentication.py†L1088-L1117】 |
| `ORCHEO_AUTH_RATE_LIMIT_IP` | `0` | Maximum authentication failures per IP before temporary blocking (0 disables the limit).【F:apps/backend/src/orcheo_backend/app/authentication.py†L1092-L1117】 |
| `ORCHEO_AUTH_RATE_LIMIT_IDENTITY` | `0` | Maximum failures per identity before rate limiting (0 disables the limit).【F:apps/backend/src/orcheo_backend/app/authentication.py†L1092-L1117】 |
| `ORCHEO_AUTH_RATE_LIMIT_INTERVAL` | `60` | Sliding-window interval (seconds) for rate-limit counters.【F:apps/backend/src/orcheo_backend/app/authentication.py†L1092-L1117】 |

## ChatKit session tokens

| Variable | Default | Purpose |
| --- | --- | --- |
| `ORCHEO_CHATKIT_TOKEN_SIGNING_KEY` | _none_ | Primary secret for signing ChatKit session JWTs; required unless a client secret is supplied.【F:apps/backend/src/orcheo_backend/app/chatkit_tokens.py†L108-L132】 |
| `ORCHEO_CHATKIT_CLIENT_SECRET` | _none_ | Alternate secret used when a dedicated signing key is not configured (supports per-workflow overrides via `CHATKIT_CLIENT_SECRET_<WORKFLOW_ID>`).【F:apps/backend/src/orcheo_backend/app/chatkit_tokens.py†L108-L132】【F:apps/backend/README.md†L30-L31】 |
| `ORCHEO_CHATKIT_TOKEN_ISSUER` | `orcheo.chatkit` | Overrides the issuer claim embedded in ChatKit session tokens.【F:apps/backend/src/orcheo_backend/app/chatkit_tokens.py†L119-L132】 |
| `ORCHEO_CHATKIT_TOKEN_AUDIENCE` | `chatkit` | Custom audience claim for ChatKit tokens.【F:apps/backend/src/orcheo_backend/app/chatkit_tokens.py†L119-L132】 |
| `ORCHEO_CHATKIT_TOKEN_TTL_SECONDS` | `300` (minimum `60`) | Token lifetime in seconds; values below 60 are coerced up to ensure safety.【F:apps/backend/src/orcheo_backend/app/chatkit_tokens.py†L122-L132】 |
| `ORCHEO_CHATKIT_TOKEN_ALGORITHM` | `HS256` | JWT signing algorithm used for ChatKit session tokens.【F:apps/backend/src/orcheo_backend/app/chatkit_tokens.py†L123-L132】 |

## CLI and SDK configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `ORCHEO_API_URL` | `http://localhost:8000` | Base URL used by the CLI and SDK when invoking the Orcheo backend.【F:packages/sdk/src/orcheo_sdk/cli/config.py†L11-L89】 |
| `ORCHEO_SERVICE_TOKEN` | _none_ | Service authentication token supplied to the CLI and SDK, and embedded in generated code snippets.【F:packages/sdk/src/orcheo_sdk/cli/config.py†L11-L89】【F:packages/sdk/src/orcheo_sdk/services/codegen.py†L48-L66】 |
| `ORCHEO_PROFILE` | `default` | Selects which CLI profile to load from `cli.toml`; can be overridden per command.【F:packages/sdk/src/orcheo_sdk/cli/config.py†L11-L89】 |
| `ORCHEO_CONFIG_DIR` | `~/.config/orcheo` | Overrides the directory containing CLI configuration files.【F:packages/sdk/src/orcheo_sdk/cli/config.py†L11-L44】 |
| `ORCHEO_CACHE_DIR` | `~/.cache/orcheo` | Overrides the cache directory used for offline CLI data.【F:packages/sdk/src/orcheo_sdk/cli/config.py†L11-L44】 |
| `_TYPER_COMPLETE*` / `_ORCHEO_COMPLETE*` | _managed by Typer_ | Internal flags Typer sets during shell completion to avoid running full CLI initialization.【F:packages/sdk/src/orcheo_sdk/cli/main.py†L23-L66】 |

## Frontend (Canvas) build-time configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_ORCHEO_BACKEND_URL` | `http://localhost:8000` | Provides the base HTTP/WebSocket endpoint for the Canvas UI; invalid values fall back to the default URL.【F:apps/canvas/src/lib/config.ts†L34-L47】【F:apps/canvas/src/vite-env.d.ts†L1-L8】 |

## Logging and environment detection

| Variable | Default | Purpose |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | Controls the log level applied to FastAPI, Uvicorn, and Orcheo loggers.【F:apps/backend/src/orcheo_backend/app/__init__.py†L147-L160】 |
| `ORCHEO_ENV` / `ENVIRONMENT` / `NODE_ENV` | `production` | Determine whether the backend treats the environment as development for sensitive debugging output.【F:apps/backend/src/orcheo_backend/app/__init__.py†L164-L175】 |
| `LOG_SENSITIVE_DEBUG` | `0` | When set to `1`, enables detailed debug logging even outside development environments.【F:apps/backend/src/orcheo_backend/app/__init__.py†L164-L175】 |

## Example integrations

These variables are only required when running the optional example scripts.

| Variable | Used In | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | `examples/agent_example.py` | Supplies the OpenAI credential for the agent example workflow.【F:examples/agent_example.py†L34-L67】 |
| `TELEGRAM_TOKEN` | Agent, Feedly, and Telegram examples | Bot token required by Telegram integrations in example workflows.【F:examples/agent_example.py†L178-L208】【F:examples/feedly_news.py†L150-L171】【F:examples/telegram_example.py†L12-L37】 |
| `TELEGRAM_CHAT_ID` | Agent, Feedly, and Telegram examples | Target chat identifier for Telegram notifications.【F:examples/agent_example.py†L178-L208】【F:examples/feedly_news.py†L150-L171】【F:examples/telegram_example.py†L12-L37】 |
| `FEEDLY_USER_ID` | `examples/feedly_news.py` | Identifies the Feedly user whose unread items should be fetched.【F:examples/feedly_news.py†L150-L171】 |

