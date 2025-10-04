# Orcheo Backend

This package exposes the FastAPI application that powers the Orcheo runtime. It wraps the core `orcheo` package so that deployment targets can import a lightweight entrypoint (`orcheo_backend.app`).

## Local development

```bash
uv sync --all-groups
uv run uvicorn orcheo_backend.app:app --reload --host 0.0.0.0 --port 8000
```

## Testing & linting

The shared repository `Makefile` includes convenience targets:

```bash
uv run make lint
uv run make test
```

These commands ensure Ruff, MyPy, and pytest with coverage run in CI as well.
