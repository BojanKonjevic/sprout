# sprout

A Nix-based Python project scaffolder. Generates a new project from a template with optional addons, then drops you into a working dev shell.

## Requirements

- **uv** (>= 0.4) – [install](https://docs.astral.sh/uv/getting-started/installation/)
- **git**
- **direnv** (optional but recommended) – auto‑activates the environment on `cd`

For the `fastapi` template you will also need **Docker**.

## Usage

Clone the repository and install sprout:

```bash
git clone https://github.com/bojankonjevic/sprout.git
cd sprout
uv sync

## Options

```
sprout <project-name>       scaffold a new project
sprout <project-name> --dry-run   preview what would be created
sprout --list-templates     show available templates
sprout --list-addons        show available addons
```

## Templates

**`blank`** — Python package with dev tooling only. Gets you pytest, ruff, mypy, a justfile, and a Nix dev shell. Good starting point for CLIs, scripts, and libraries.

**`fastapi`** — Production-oriented FastAPI setup. Includes:
- FastAPI with a structured package layout (`api/`, `core/`, `db/`, `models/`, `schemas/`)
- SQLAlchemy (async) + Alembic migrations
- pydantic-settings for environment-based config
- JWT + bcrypt helpers in `core/security.py`
- Health endpoint at `GET /health`
- pytest with async fixtures and a test database

## Addons

Addons are selected interactively during scaffolding and can be combined freely with either template.

**`docker`** — Multi-stage Dockerfile (uv-based) + `compose.yml` + `.dockerignore`.

**`redis`** — Async connection pool in `integrations/redis.py` with a FastAPI dependency, settings patch, and a Redis compose service.

**`celery`** — Celery worker and beat scheduler in `tasks/celery_app.py`, with an example task in `tasks/example_tasks.py`. Requires the redis addon.

**`sentry`** — `integrations/sentry.py` with an `init_sentry()` that no-ops when `SENTRY_DSN` is unset. Injected into the FastAPI lifespan automatically.

**`github-actions`** — CI workflow at `.github/workflows/ci.yml` that runs lint, type-check, and tests on push and pull requests. Spins up Postgres and Redis services automatically when those addons are present.

## Generated structure

### blank

```
src/myproject/
    __init__.py
    main.py
tests/
    test_main.py
```

### fastapi

```
src/myproject/
    main.py           FastAPI app
    lifecycle.py      lifespan (startup/shutdown)
    settings.py       pydantic-settings
    exceptions.py     shared HTTP exceptions
    api/
        router.py
        routes/
            health.py
    core/
        security.py   JWT + bcrypt
    db/
        base.py       DeclarativeBase
        session.py    engine, session factory, get_session
    models/
        mixins.py     TimestampMixin
    schemas/
        common.py     PaginationParams, PaginatedResponse
alembic/
tests/
    conftest.py
    integration/
    unit/
    fixtures/
```

## Adding auth

When you're ready to add authentication to a FastAPI project:

1. Define `User` and `RefreshToken` models in `models/`
2. Add `core/dependencies.py` with a `get_current_user` dependency
3. Add `api/routes/auth.py`
4. Register it in `api/router.py`
5. Activate the `client` fixture in `tests/conftest.py`
6. Run `just db-create && just migrate 'add users' && just upgrade`
