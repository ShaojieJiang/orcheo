.PHONY: dev-server test lint format canvas-lint canvas-format

UV ?= uv
UV_CACHE_DIR ?= .cache/uv
UV_RUN = UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) run

lint:
	$(UV_RUN) ruff check src/orcheo packages/sdk/src apps/backend/src
	$(UV_RUN) mypy src/orcheo packages/sdk/src apps/backend/src --install-types --non-interactive
	$(UV_RUN) ruff format . --check

canvas-lint:
	npm --prefix apps/canvas run lint

canvas-format:
	npx --prefix apps/canvas prettier "src/**/*.{ts,tsx,js,jsx,css,md}" --write

format:
	ruff format .
	ruff check . --select I001 --fix
	ruff check . --select F401 --fix

test:
	$(UV_RUN) pytest --cov --cov-report term-missing tests/

doc:
	mkdocs serve --dev-addr=0.0.0.0:8080

dev-server:
	uvicorn --app-dir apps/backend/src orcheo_backend.app:app --reload --port 8000
