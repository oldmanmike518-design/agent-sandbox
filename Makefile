.PHONY: up down logs test test-unit lint fmt

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f api

test:
	./scripts/test_agent.sh

test-unit:
	.venv/bin/python -m pytest -q

lint:
	.venv/bin/python -m ruff check app scripts tests
