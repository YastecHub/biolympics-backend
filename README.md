# BIOLYMPICS LIVE — Backend

FastAPI + SQLAlchemy 2 (async) + PostgreSQL + Redis + Celery. Powers the public
read API, admin/score-official write API, live WebSocket feed and push jobs.

## Stack
- Python 3.12, FastAPI, Pydantic v2
- SQLAlchemy 2 async, Alembic, PostgreSQL (SQLite for tests)
- Redis (cache + WebSocket fan-out + Celery broker)
- Celery worker + beat for notifications
- Argon2 password hashing, JWT access + rotating refresh tokens
- structlog JSON logging, Ruff, mypy, pytest

## Local development (without Docker)

```bash
uv venv .venv --python 3.12
uv pip install -e ".[dev]"

# Tests use SQLite — no services needed:
.venv/Scripts/python -m pytest -q          # Windows
.venv/bin/python -m pytest -q              # macOS/Linux

# Run the API (needs Postgres + Redis, or point DATABASE_URL at SQLite):
uvicorn app.main:app --reload
```

With Docker, prefer the root `docker compose up` which wires Postgres, Redis,
MinIO, the API, Celery worker and beat together.

## Database

```bash
alembic upgrade head                       # apply migrations
alembic revision --autogenerate -m "msg"   # create a migration
python -m app.cli seed                      # load tournament + demo data
python -m app.cli seed --no-demo            # tournament structure only
```

## CLI

```bash
python -m app.cli seed [--no-demo]
python -m app.cli create-admin --email you@faculty.edu --role SUPER_ADMIN
python -m app.cli generate-vapid            # web-push keypair
python -m app.cli simulate                  # demo live-score ticker (dev only)
```

## Layout

```
app/
├── api/v1/           # routers: public, auth, admin, push, ws
├── core/             # config, security, logging, middleware
├── db/               # async engine, session, declarative base
├── models/           # SQLAlchemy models (39 tables)
├── schemas/          # Pydantic request/response models
├── services/         # standings, scoring, lifecycle, events, notifications…
├── seeds/            # tournament seed data + seeding logic
├── websocket/        # connection manager
└── workers/          # Celery app + tasks
```

## Key design notes
- **Optimistic concurrency:** every live mutation checks `expected_version`;
  stale writes get `409 Conflict` (see `services/scoring.py`).
- **Standings** are recomputed server-side, deterministically, on completion /
  correction / cancellation (`services/recompute.py`).
- **Events** flow through Redis pub/sub so multiple API instances stay in sync;
  falls back to in-process delivery when Redis is absent (`services/events.py`).
- Secrets are never logged (denylist scrubber in `core/logging.py`).
