# zenit

Scaffold a new Python project with one command.

```
zenit my-project
```

Picks a template, applies addons, writes all files, generates `pyproject.toml` and `justfile`, runs `git init`, and tells you what to do next. Nothing network-dependent — you get a directory you can immediately work in.

---

## Requirements

- **Python 3.14+**
- **uv 0.4+** — [install](https://docs.astral.sh/uv/getting-started/installation/)
- **git**
- **just** — optional, but generated projects use it heavily
- **direnv** — optional, auto-activates the virtualenv on `cd`

The `fastapi` template additionally requires **Docker** running locally.

---

## Installation

```bash
uv tool install zenit

# or run without installing
uvx zenit my-project
```

**NixOS:** `UV_PYTHON_DOWNLOADS=never` must be set. Generated projects detect NixOS automatically and write a `shell.nix` + `.envrc` that works with the system Python.

---

## Usage

```
zenit create <name>                scaffold a new project

zenit add [addon]                  add an addon to the current project
zenit remove [addon]               remove an addon from the current project
zenit doctor                       check project health

zenit list-templates
zenit list-addons
zenit config                       show config file path and current settings
zenit --version
```

All commands that modify files support `--dry-run`. Interactive prompts use arrow keys; fall back to numbered input in CI.

---

## Templates

**`blank`** — minimal Python package with pytest, ruff, mypy, and a `justfile`.

**`fastapi`** — production-oriented FastAPI setup with SQLAlchemy (async), Alembic, asyncpg, pydantic-settings, a health endpoint, and test fixtures. Requires the `docker` addon.

---

## Addons

Addons can be selected at scaffold time or added/removed later with `zenit add` and `zenit remove`.

| Addon | Description |
|---|---|
| `docker` | Dockerfile, compose.yml, .dockerignore |
| `redis` | Async Redis connection helper + compose service |
| `celery` | Celery worker + beat, backed by Redis |
| `sentry` | Sentry SDK initialisation (no-ops when DSN is unset) |
| `github-actions` | CI workflow: lint, type-check, test on push/PR |
| `auth-manual` | JWT auth: register, login, refresh, logout (fastapi only) |

Dependencies are enforced (`celery` requires `redis`) and tracked in `.zenit.toml`.

---

## Adding and removing addons

```bash
cd my-project

zenit add              # interactive picker
zenit add redis        # direct
zenit add celery --dry-run

zenit remove sentry
```

Both commands update `.zenit.toml`, `pyproject.toml`, `justfile`, `compose.yml`, and `.env` as needed. Run `uv sync` after to install/uninstall packages.

---

## Health checks

```bash
zenit doctor
```

Checks that all expected files exist, sentinels are intact, dependencies match the installed addons, compose services are present, and env vars are defined. Exits with code 1 if errors are found.

---

## Configuration

Optional config file for personal defaults:

| Platform | Path |
|---|---|
| Linux / macOS | `~/.config/zenit/zenit.toml` |
| Windows | `%APPDATA%\zenit\zenit.toml` |

```toml
default_template = "fastapi"
default_addons = ["docker", "github-actions"]
```

Defaults appear as pre-selections in the interactive prompt — you can still change them before confirming.

---

## How zenit tracks your project

Every scaffolded project gets a `.zenit.toml` at the root:

```toml
[project]
template = "fastapi"
addons = ["docker", "redis"]
zenit_version = "1.0.8"
```

This is the source of truth for `zenit add`, `zenit remove`, and `zenit doctor`. Commit it. Don't edit it manually — use the CLI instead.

---

## Running from source

```bash
git clone https://github.com/BojanKonjevic/zenit.git
cd zenit
uv sync
uv run python main.py my-project
```

---

## License

MIT — see [LICENSE](LICENSE).
