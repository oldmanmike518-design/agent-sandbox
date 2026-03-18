.PHONY: up down logs test fmt

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f api

test:
	./scripts/test_agent.sh
