.PHONY: up down logs migrate migrate-new test lint format shell-bot shell-api psql seed create-admin probe-mimo prod-build prod-up prod-down

up:
	docker compose up -d postgres redis minio
	@echo "infra up. waiting for healthy..."
	@sleep 3
	docker compose up -d bot api worker beat web

down:
	docker compose down

logs:
	docker compose logs -f --tail=100 bot api worker

migrate:
	docker compose run --rm api alembic upgrade head

migrate-new:
	docker compose run --rm api alembic revision --autogenerate -m "$(m)"

test:
	docker compose run --rm api pytest

lint:
	ruff check .
	mypy packages apps/api

format:
	ruff format .
	ruff check --fix .

shell-bot:
	docker compose exec bot python

shell-api:
	docker compose exec api python

psql:
	docker compose exec postgres psql -U $${POSTGRES_USER:-stager} -d $${POSTGRES_DB:-stager}

seed:
	docker compose run --rm api python scripts/seed_dev.py

create-admin:
	@read -p "email: " EMAIL; \
	read -s -p "password: " PASSWORD; echo; \
	docker compose run --rm api python -m apps.api.cli create-admin "$$EMAIL" "$$PASSWORD"

probe-mimo:
	docker compose run --rm api python scripts/probe_mimo.py $(F)

# ─── prod ────────────────────────────────────────────────────────────────────
prod-build:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml build

prod-up:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

prod-down:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml down

prod-migrate:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api alembic upgrade head

prod-logs:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail=100 bot api worker caddy
