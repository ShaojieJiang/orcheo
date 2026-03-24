# Start Orcheo stack services

## Compose assets

Preferred source: `orcheo install` syncs stack assets into
`${ORCHEO_STACK_DIR:-$HOME/.orcheo/stack}` and uses versioned `stack-v*`
tag assets when available (with main-branch fallback).

## Environment setup (required before `docker compose up`)

Preferred path (recommended):

```bash
orcheo install --yes --start-stack
```

This command installs SDK/backend tooling, provisions stack assets into
`${ORCHEO_STACK_DIR:-$HOME/.orcheo/stack}`, creates `.env` from `.env.example` if missing,
and starts Docker Compose using that project directory.

Manual path (only if explicit compose control is required):

```bash
STACK_VERSION="${ORCHEO_STACK_VERSION:?set ORCHEO_STACK_VERSION (for example: 0.8.3)}"
orcheo install --yes --stack-version "$STACK_VERSION" --skip-stack
```

Manual sync should pin to an explicit stack version (for example
`STACK_VERSION=0.8.3`).

Required secrets to replace before starting local services:
- `ORCHEO_POSTGRES_PASSWORD`
- `ORCHEO_VAULT_ENCRYPTION_KEY`
- `VITE_ORCHEO_CHATKIT_DOMAIN_KEY`
- `ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN`

If these still use template values (`change-me`, `replace-with-64-hex-chars`, etc.), ask the user whether to configure real values now or proceed with placeholders for local testing.

## Bring up stack

Run from `${ORCHEO_STACK_DIR:-$HOME/.orcheo/stack}`, or pass `-f` and `--project-directory`
explicitly.

```bash
STACK_DIR="${ORCHEO_STACK_DIR:-$HOME/.orcheo/stack}"
docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" pull
docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" up -d
docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" ps
```

## Expected service names

- `backend`
- `canvas`
- `celery-beat`
- `postgres`
- `redis`
- `worker`

## Logs

```bash
STACK_DIR="${ORCHEO_STACK_DIR:-$HOME/.orcheo/stack}"
docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" logs -f backend
docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" logs -f worker
docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" logs -f celery-beat
docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" logs -f canvas
```

## Stop stack

```bash
STACK_DIR="${ORCHEO_STACK_DIR:-$HOME/.orcheo/stack}"
docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" down
```

## Notes

- Use PyPI-based images only (this compose builds backend from PyPI packages).
- Confirm `${ORCHEO_STACK_DIR:-$HOME/.orcheo/stack}/.env` exists before `up`.
- If reproducibility matters, pass `--stack-version <X.Y.Z>` to `orcheo install`.
