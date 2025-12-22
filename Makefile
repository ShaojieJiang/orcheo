.PHONY: dev-server test lint format canvas-lint canvas-format canvas-test redis worker celery-beat \
       docker-up docker-down docker-build docker-logs

UV ?= uv
UV_CACHE_DIR ?= .cache/uv
UV_RUN = UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) run

lint:
	$(UV_RUN) ruff check src/orcheo packages/sdk/src packages/agentensor/src apps/backend/src
	$(UV_RUN) mypy src/orcheo packages/sdk/src packages/agentensor/src apps/backend/src --install-types --non-interactive
	$(UV_RUN) ruff format . --check

canvas-lint:
	npm --prefix apps/canvas run lint

canvas-format:
	npx --prefix apps/canvas prettier "apps/canvas/src/**/*.{ts,tsx,js,jsx,css,md}" --write

canvas-test:
	npm --prefix apps/canvas run test -- --run

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

redis:
	docker compose up -d redis

worker:
	$(UV_RUN) celery -A orcheo_backend.worker.celery_app worker --loglevel=info

celery-beat:
	$(UV_RUN) celery -A orcheo_backend.worker.celery_app beat --loglevel=info

# Docker Compose commands for full-stack development
docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker compose build

docker-logs:
	docker compose logs -f
