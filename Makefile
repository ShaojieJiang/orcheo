.PHONY: dev-backend test lint format

lint:
	ruff check src/aic_flow
	mypy src/aic_flow
	ruff format . --check
	# npx eslint --fix "src/frontend/**/*.{js,jsx,ts,tsx}" --rule "import/order: error" --rule "unused-imports/no-unused-imports: error"

format:
	ruff format .
	ruff check . --select I001 --fix
	ruff check . --select F401 --fix
	# npx prettier --write "src/frontend/**/*.{js,jsx,ts,tsx,css,json}"

test:
	pytest --cov --cov-report term-missing tests/

doc:
	mkdocs serve --dev-addr=0.0.0.0:8080

dev-backend:
	uvicorn aic_flow.main:app --reload --port 8000
