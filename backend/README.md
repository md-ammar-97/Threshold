# Backend — Instamart Discovery Engine

FastAPI + Celery + PostgreSQL/pgvector + Redis. See `../docs/architecture.md` for the full service design and `../docs/implementationplan.md` for what each phase adds here.

## Local setup (without Docker)

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows
# source .venv/bin/activate && pip install -e ".[dev]"  # macOS/Linux
cp ../.env.example ../.env   # fill in DATABASE_URL, REDIS_URL, GROQ_API_KEY
```

Requires a running PostgreSQL (with `vector` extension available) and Redis — either via `docker compose up postgres redis` from the repo root, or your own local instances.

## Running

```bash
# apply migrations
./.venv/Scripts/python.exe -m alembic upgrade head

# API (http://localhost:8000, docs at /docs, health at /health)
./.venv/Scripts/python.exe -m uvicorn instamart_engine.api.main:app --reload --port 8000

# worker (a later phase; harmless to start now with no tasks registered)
./.venv/Scripts/python.exe -m celery -A instamart_engine.core.celery_app worker --loglevel=info --pool=solo
```

## Testing and quality gates

```bash
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/python.exe -m ruff check src tests
./.venv/Scripts/python.exe -m mypy src
```

## Adding a migration

```bash
./.venv/Scripts/python.exe -m alembic revision -m "short description"
# hand-write upgrade()/downgrade() — see alembic/versions/b454289024bc_* for the pattern
./.venv/Scripts/python.exe -m alembic upgrade head
```

Every new domain module's models must be imported in `alembic/env.py` (see the comment there) so `Base.metadata` — and therefore `--autogenerate` — can see them.

## Production deployment

This directory's `Dockerfile` is dev-only (editable install, `--reload`). Production builds use `Dockerfile.prod` from the repo root context and deploy to Render — see [`../docs/deployment.md`](../docs/deployment.md) for the full guide, including the daily extraction cron job and the complete environment-variable reference.
