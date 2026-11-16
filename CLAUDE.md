# CLAUDE.md: Instructions for Claude Code / Autonomous Agents

## Build and Run Commands
- Local Dev Setup: `uv sync`
- Run Backend: `uv run uvicorn backend.src.main:app --reload --port 8000`
- Run Migrations: `uv run alembic upgrade head`
- Run Celery Worker: `uv run celery -A backend.src.worker.celery_app worker --loglevel=info`
- Run Tests: `uv run pytest tests/`
- Full Docker Stack: `docker compose up --build -d`

## Code Conventions
- Formatting: Black/Ruff compatible, strict Python 3.12+ type hints.
- Database: SQLAlchemy 2.0 declarative models with `Mapped[]`, async session.
- Schemas: Pydantic v2 `BaseModel` with `model_config = ConfigDict(from_attributes=True)`.
- Errors: Always raise structured `HTTPException` with clear error codes.
