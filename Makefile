.PHONY: dev-server test lint format canvas-lint canvas-format

lint:
	ruff check src/orcheo packages/sdk/src apps/backend/src
	mypy src/orcheo packages/sdk/src apps/backend/src --install-types --non-interactive
	ruff format . --check

canvas-lint:
	npm --prefix apps/canvas run lint

canvas-format:
	npx --prefix apps/canvas prettier "src/**/*.{ts,tsx,js,jsx,css,md}" --write

format:
	ruff format .
	ruff check . --select I001 --fix
	ruff check . --select F401 --fix

test:
	uv run pytest --cov --cov-report term-missing tests/

doc:
	mkdocs serve --dev-addr=0.0.0.0:8080

dev-server:
	uvicorn --app-dir apps/backend/src orcheo_backend.app:app --reload --port 8000
