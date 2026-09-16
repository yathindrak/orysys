.PHONY: setup verify migrate-check compose-check image pilot pilot-live logs down

setup:
	uv sync --locked --all-groups

verify:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy src
	uv run pytest

migrate-check:
	docker compose up --detach --wait postgres
	DATABASE_URL=postgresql://orysys:local-postgres-change-me@127.0.0.1:55432/orysys uv run alembic upgrade head
	DATABASE_URL=postgresql://orysys:local-postgres-change-me@127.0.0.1:55432/orysys uv run alembic current

compose-check:
	docker compose config -q

image:
	docker build --target runtime -t orysys:local .

pilot:
	docker compose up --build --wait postgres redis mcp-server api ui

pilot-live:
	docker compose -f compose.yaml -f compose.live.yaml up --build --wait postgres redis mcp-server api ui

logs:
	docker compose logs --follow api ui mcp-server

down:
	docker compose down
