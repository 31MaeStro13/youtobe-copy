.PHONY: up down build logs seed test clean

up:
	docker compose up --build -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

seed:
	docker compose exec backend python3 scripts/seed_data.py

test:
	docker compose exec backend pytest -v

clean:
	docker compose down -v
