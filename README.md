# jumpstart

A CLI that scaffolds a new Python project from a template with optional addons — sets up the package structure, dev tooling, config files, and an initial git commit, then tells you what to run next.

```
jumpstart my-api
```

---

## What it does

1. Asks you to pick a **template** (blank or FastAPI)
2. Asks you to pick **addons** (Docker, Redis, Celery, Sentry, GitHub Actions)
3. Generates the project directory, all files, `pyproject.toml`, and `justfile`
4. Runs `git init` and makes the first commit

It does not run `uv sync`, start servers, or do anything network-dependent. You get a directory you can immediately `cd` into and start working.

---

## Requirements

All platforms need:

- **Python 3.14+**
- **uv 0.4+** — [install](https://docs.astral.sh/uv/getting-started/installation/)
- **git**
- **just** — [install](https://github.com/casey/just#installation) (optional but the generated projects use it heavily)
- **direnv** — optional, auto-activates the virtualenv on `cd` (see per-platform notes below)

The `fastapi` template additionally needs **Docker** running locally.

---

## Installation

### macOS

```bash
# Install uv if you haven't
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install jumpstart
uv tool install jumpstart-cli

# Or run without installing
uvx jumpstart-cli my-project
```

**direnv** (recommended):
```bash
brew install direnv
# Add to ~/.zshrc or ~/.bash_profile:
eval "$(direnv hook zsh)"   # or bash
```

---

### Linux (non-NixOS)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install jumpstart-cli
```

**direnv**:
```bash
# Ubuntu/Debian
sudo apt install direnv

# Arch
sudo pacman -S direnv

# Fedora
sudo dnf install direnv

# Add to ~/.bashrc or ~/.zshrc:
eval "$(direnv hook bash)"   # or zsh
```

---

### NixOS

NixOS does not allow uv to download or manage its own Python binaries — `UV_PYTHON_DOWNLOADS` must be set to `never` and uv must use the system Python. jumpstart handles this for you when run via the Nix flake, but you need Python 3.14+ available in your environment first.

**Option A — run directly from the flake (recommended):**

```bash
nix run github:BojanKonjevic/jumpstart -- my-project
```

This uses the bundled flake which sets `UV_PYTHON_DOWNLOADS=never` and points uv at the Nix-provided Python 3.14 automatically.

**Option B — install and run manually:**

```bash
# Make sure python3.14 is in your PATH (via nix-shell, home-manager, etc.)
# Then:
UV_PYTHON_DOWNLOADS=never uv tool install jumpstart-cli
UV_PYTHON_DOWNLOADS=never jumpstart my-project
```

**Generated projects on NixOS:**

When jumpstart detects it's running on NixOS (by checking `/etc/NIXOS`), it generates a `.envrc` that uses `use nix shell.nix` instead of uv's own environment management, and writes a `shell.nix` that provides the correct `LD_LIBRARY_PATH` for compiled wheels like greenlet. So the generated project will also work correctly on NixOS.

**direnv on NixOS** — add to your `configuration.nix`:
```nix
programs.direnv.enable = true;
```
Or install it in your user environment:
```bash
nix-env -iA nixpkgs.direnv
# Add to ~/.bashrc or ~/.zshrc:
eval "$(direnv hook bash)"
```

---

### Windows

Windows is supported. The generated `justfile` uses `cmd` as the shell, and all `just` recipes work without WSL.

```powershell
# Install uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install jumpstart
uv tool install jumpstart-cli
```

**direnv on Windows** — direnv does not have an official Windows build. Your options:

1. **Skip it** — instead of auto-activation, run `uv sync` once after scaffolding, then `uv run <command>` (or just use `just`, which routes through `uv run` already).
2. **Use WSL2** — install direnv inside WSL2 as per the Linux instructions above.
3. **Use `scoop`** — a community-maintained build exists: `scoop install direnv` (not officially supported).

jumpstart will copy `.envrc` regardless, but will warn you if direnv is not found rather than failing.

---

## Usage

```
jumpstart <project-name>            scaffold a new project
jumpstart <project-name> --dry-run  preview what would be created (nothing is written)
jumpstart list-templates            show available templates
jumpstart list-addons               show available addons
jumpstart --version
```

The interactive prompt uses arrow keys and space to select. If stdin is not a tty (e.g. piped input or CI), it falls back to numbered selection.

---

## Templates

### `blank`

A minimal Python package with dev tooling. Good for CLIs, scripts, and libraries.

```
my-project/
  src/my_project/
    __init__.py
    main.py
    __main__.py
  tests/
    test_main.py
  pyproject.toml
  justfile
  .gitignore
  .envrc
```

Includes: pytest, ruff, mypy, pytest-cov, ipython.

### `fastapi`

A production-oriented FastAPI setup. **Requires the `docker` addon** (selected automatically).

```
my-project/
  src/my_project/
    main.py           FastAPI app + lifespan
    lifecycle.py      startup/shutdown logic
    settings.py       pydantic-settings (reads from .env)
    exceptions.py     HTTP exception helpers
    api/
      router.py
      routes/
        health.py     GET /health → {"status": "ok"}
    core/
      security.py     JWT encode/decode, bcrypt hashing
    db/
      base.py         SQLAlchemy DeclarativeBase
      session.py      async engine, session factory, get_session dep
    models/
      mixins.py       TimestampMixin (created_at, updated_at)
    schemas/
      common.py       PaginationParams, PaginatedResponse
  alembic/
    env.py            async-compatible Alembic env
    versions/
  tests/
    conftest.py       session + anon_client + client fixtures
    integration/
      test_health.py
    unit/
    fixtures/
  scripts/
    wait_db.py        waits for postgres container to be ready
  .env                auto-generated with a random SECRET_KEY
  .env.example
  alembic.ini
```

---

## Addons

Addons are selected interactively and can be mixed freely with either template, with a few constraints noted below.

### `docker`

Generates a multi-stage `Dockerfile` (uv-based, minimal final image), `compose.yml`, and `.dockerignore`.

- For `blank`: compose starts just the app container.
- For `fastapi`: compose also starts a `db` (postgres:16) service.
- Required by `fastapi` (auto-selected).

### `redis`

Adds `src/<pkg>/integrations/redis.py` — an async connection pool with a `get_redis` FastAPI dependency and a `close_redis` shutdown helper.

- If `docker` is also selected: appends a `redis:7-alpine` service to `compose.yml`.
- If `docker` is not selected: writes a standalone `compose.redis.yml`.
- For `fastapi`: also patches `settings.py` to add a `redis_url` field.
- Required by `celery`.

### `celery`

Adds `src/<pkg>/tasks/celery_app.py` (Celery app configured against Redis) and `tasks/example_tasks.py` with a trivial `add` task.

- Requires `redis`.
- If `docker` is selected: appends `celery-worker` and `celery-beat` services to `compose.yml`.

### `sentry`

Adds `src/<pkg>/integrations/sentry.py` with an `init_sentry()` function that no-ops when `SENTRY_DSN` is unset — safe to commit and run locally without a DSN.

- For `fastapi`: patches `lifecycle.py` to call `init_sentry()` on startup, and patches `settings.py` and `.env` to add `SENTRY_DSN` / `SENTRY_ENVIRONMENT`.
- For `blank`: patches `main.py` to call `init_sentry()` at startup.

### `github-actions`

Writes `.github/workflows/ci.yml` that runs lint (`ruff check`), format check (`ruff format --check`), type check (`mypy`), and tests (`pytest`) on push and pull requests.

- Spins up a `postgres:16` service automatically when the `fastapi` template is used.
- Spins up a `redis:7-alpine` service automatically when `redis` is selected.
- Runs migrations before tests when postgres is present.

---

## Generated commands (`just`)

All generated projects come with a `justfile`. Run `just` with no arguments to list what's available.

| Command | What it does |
|---|---|
| `just test` | run pytest |
| `just cov` | pytest with coverage report |
| `just lint` | ruff check |
| `just fmt` | ruff format |
| `just fix` | ruff check --fix + ruff format |
| `just check` | mypy |
| `just run` | start the app (uvicorn --reload for fastapi, python -m for blank) |

**FastAPI only:**

| Command | What it does |
|---|---|
| `just migrate "message"` | generate an Alembic migration |
| `just upgrade` | apply all pending migrations |
| `just downgrade` | roll back one step |
| `just db-create` | start db container, create app + test databases, migrate |
| `just db-reset` | drop and recreate both databases |
| `just wait-db` | wait until postgres is accepting connections |

**Docker addon:**

| Command | What it does |
|---|---|
| `just docker-up` | docker compose up --build |
| `just docker-down` | docker compose down |

**Redis addon:**

| Command | What it does |
|---|---|
| `just redis-up` | start redis |
| `just redis-down` | stop redis |
| `just redis-cli` | open redis-cli |

**Celery addon:**

| Command | What it does |
|---|---|
| `just celery-up` | start worker + beat via compose |
| `just celery-down` | stop worker + beat |
| `just celery-flower` | open Flower monitoring UI on port 5555 |
| `just celery-logs` | tail worker logs |

**Sentry addon:**

| Command | What it does |
|---|---|
| `just sentry-check` | print sentry-sdk version |
| `just sentry-test` | print whether SENTRY_DSN is set |

---

## Dry run

Pass `--dry-run` to preview everything that would happen without touching disk:

```
jumpstart my-api --dry-run
```

Output shows every file that would be created or modified, every dependency that would be added to `pyproject.toml`, every `just` recipe, and every git command — then exits without writing anything.

---

## Adding auth to a FastAPI project

The `fastapi` template lays out the security plumbing but stops short of generating auth routes (everyone's auth is different). When you're ready:

1. Define `User` and `RefreshToken` models in `models/` — import them in `models/__init__.py` so Alembic discovers them.
2. Add `core/dependencies.py` with a `get_current_user` dependency using `decode_access_token` from `core/security.py`.
3. Add `api/routes/auth.py` with register, login, and refresh endpoints.
4. Register it in `api/router.py`.
5. Uncomment the auth block in `tests/conftest.py` to enable the authenticated `client` fixture.
6. Run `just db-create && just migrate "add users" && just upgrade`.

---

## Running from source

If you want to hack on jumpstart itself:

```bash
git clone https://github.com/BojanKonjevic/jumpstart.git
cd jumpstart
uv sync
uv run python main.py my-project
```

On NixOS, enter the dev shell first:
```bash
nix develop
python main.py my-project
```

---

## License

MIT — see [LICENSE](LICENSE).

