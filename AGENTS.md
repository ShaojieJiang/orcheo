# Repository Guidelines

## Project Structure & Module Organization
- Source: `src/orcheo/` — core package. Key areas: `graph/` (state, builder), `nodes/` (task/AI/integrations), `main.py` (FastAPI app/WebSocket).
- Tests: `tests/` — mirrors package layout (e.g., `tests/graph/`, `tests/nodes/`).
- Docs & examples: `docs/`, `examples/`, experimental `playground/`.
- Config: `pyproject.toml` (tooling), `.pre-commit-config.yaml`, `.env` (local secrets), `Makefile` (common tasks).

## Build, Test, and Development Commands
- Install deps (all groups): `uv sync --all-groups`
- Lint/typecheck/format (check): `make lint`
- Auto-format and organize imports: `make format`
- Run tests with coverage: `make test`
- Run dev API (FastAPI): `make dev-server` then visit `http://localhost:8000`
- Serve docs locally: `make doc` (MkDocs at `http://localhost:8080`)

Tip: Prefix with `uv run` when invoking tools directly, e.g. `uv run pytest -k nodes`.

## Coding Style & Naming Conventions
- Python 3.12, type hints required (mypy: `disallow_untyped_defs = true`).
- Formatting/linting via Ruff; line length 88; Google-style docstrings.
- Import rules: no relative imports (TID252); always use absolute package paths (`from orcheo...`).
- Naming: modules/files `snake_case.py`; classes `PascalCase`; functions/vars `snake_case`.
- Keep functions focused; prefer small units with clear docstrings and types.

## Testing Guidelines
- Framework: `pytest` with `pytest-asyncio` and `pytest-cov`.
- Location: place tests under `tests/` mirroring package paths.
- Names: test files `test_*.py`, tests `test_*` functions; include async tests where relevant.
- Coverage: CI enforces 95% project coverage and 100% diff coverage. Add tests for new code and branches.
- Run subsets: `uv run pytest tests/nodes -q`.

**CRITICAL QUALITY REQUIREMENTS**:
- `make lint` MUST pass with ZERO errors or warnings before completing any task
- `make test` MUST pass with all tests green
- Run both commands after ANY code modification

## Commit & Pull Request Guidelines
- Commits: concise, imperative subject; include scope/ticket where helpful (e.g., `AF-12 Add RSSNode`). Keep changes focused.
- PRs: clear description, rationale, and testing notes; link issues; include screenshots for UI (if any); update docs/examples when behavior changes.
- CI must pass: lint, type check, tests, and coverage thresholds.

## Security & Configuration Tips
- Load secrets from `.env` (via `python-dotenv`); never commit secrets.
- Prefer `uv run` for tooling parity with CI; ensure `uv.lock` stays updated when adding deps.
