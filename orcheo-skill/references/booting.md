# Orcheo skill booting guide

Use this file as the required first-step runbook before any task-specific Orcheo command.

## Step 1: Verify prerequisites

1. Check `orcheo` CLI:
```bash
orcheo --version
```
2. If `orcheo` is missing, install it (macOS / Linux):
```bash
curl -fsSL https://ai-colleagues.com/install.sh | bash -s -- --yes --start-stack
orcheo --version
```
3. `uv` is not a required manual prerequisite for this flow. The installer handles its own internal dependencies.

## Step 2: Ensure CLI profile configuration exists

1. Validate profile settings:
```bash
orcheo config --check
```
2. If the check fails, follow [config.md](./config.md) to configure.

## Step 3: Detect local vs cloud target

1. Use the `api_url` value from Step 2's `orcheo config --check` output.
2. If `api_url` contains `localhost` or `127.0.0.1`, treat as local mode.
3. Otherwise, treat as cloud mode.

### Local mode checks

1. Verify stack status from the compose project directory:
```bash
STACK_DIR="${ORCHEO_STACK_DIR:-$HOME/.orcheo/stack}"
docker compose -f "$STACK_DIR/docker-compose.yml" --project-directory "$STACK_DIR" ps
```
2. Expected service names for the `orcheo install`-managed stack compose:
- `backend`
- `canvas`
- `celery-beat`
- `postgres`
- `redis`
- `worker`

If services are not healthy/running, continue with [local-services.md](./local-services.md).

### Cloud mode checks

1. Check OAuth status:
```bash
orcheo auth status
```
2. If not authenticated, run:
```bash
orcheo auth login
```

## Step 4: Mark boot complete

After checks pass, continue to task-specific references.

Report a short boot digest including:
- `orcheo` CLI version
- active profile (if set)
- target mode (`local` or `cloud`)
