.PHONY: setup dev check test benchmark demo schema up down
setup:
	cd backend && uv sync --frozen
	cd frontend && npm ci
dev:
	python3 scripts/dev.py
check:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
	cd frontend && npm run lint && npm run build
test:
	cd backend && uv run pytest -q
	cd frontend && npm run test:e2e
benchmark:
	cd backend && uv run python ../scripts/benchmark_solver.py --output ../datasets/benchmark-smoke.json
demo:
	cd backend && uv run railshield generate --seed 42 --output ../datasets/demo
schema:
	cd backend && uv run railshield schema --output ../datasets/schema.json
up:
	docker compose up --build -d
down:
	docker compose down
