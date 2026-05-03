"""Dry-run mode — prints a structured preview without touching the filesystem."""

from scaffolder.context import Context
from scaffolder.generate import _collect
from scaffolder.ui import (
    BOLD,
    DIM,
    MAGENTA,
    RESET,
    dry_cmd,
    dry_dep,
    dry_file,
    dry_header,
    dry_section,
)


def _common_files() -> list[tuple[str, str]]:
    return [
        (".gitignore", "common"),
        (".pre-commit-config.yaml", "common"),
        (".envrc", "common — direnv + flake"),
    ]


def _template_files(ctx: Context) -> list[tuple[str, str]]:
    p = ctx.pkg_name
    if ctx.template == "fastapi":
        return [
            (f"src/{p}/__init__.py", "package init"),
            (f"src/{p}/main.py", "FastAPI app + router inclusion"),
            (f"src/{p}/lifecycle.py", "lifespan (startup/shutdown hooks)"),
            (f"src/{p}/settings.py", "pydantic-settings"),
            (f"src/{p}/exceptions.py", "shared HTTP exception classes"),
            (f"src/{p}/api/__init__.py", "api package"),
            (f"src/{p}/api/router.py", "top-level APIRouter"),
            (f"src/{p}/api/routes/__init__.py", "routes package"),
            (f"src/{p}/api/routes/health.py", "GET /health"),
            (f"src/{p}/core/__init__.py", "core package"),
            (f"src/{p}/core/security.py", "JWT + bcrypt helpers"),
            (f"src/{p}/db/__init__.py", "db package"),
            (f"src/{p}/db/base.py", "DeclarativeBase"),
            (f"src/{p}/db/session.py", "engine, session factory, get_session"),
            (f"src/{p}/models/__init__.py", "import models here for Alembic"),
            (f"src/{p}/models/mixins.py", "TimestampMixin"),
            (f"src/{p}/schemas/__init__.py", "schemas package"),
            (f"src/{p}/schemas/common.py", "PaginationParams, PaginatedResponse"),
            ("alembic.ini", "alembic config"),
            ("alembic/env.py", "async alembic env"),
            ("alembic/script.py.mako", "migration template"),
            ("alembic/versions/", "migrations directory"),
            ("tests/conftest.py", "pytest fixtures (session, anon_client, client)"),
            ("tests/integration/test_health.py", "GET /health smoke test"),
            ("tests/unit/", "unit tests directory"),
            ("tests/fixtures/", "shared test fixtures directory"),
            (".env", "local env vars (gitignored)"),
            (".env.example", "env template for teammates"),
        ]
    else:
        return [
            (f"src/{p}/__init__.py", "package init"),
            (f"src/{p}/main.py", "entry point"),
            (f"src/{p}/__main__.py", "python -m {p} support"),
            ("tests/test_main.py", "smoke test"),
        ]


def _generated_files() -> list[tuple[str, str]]:
    return [
        ("pyproject.toml", "project metadata + deps"),
        ("justfile", "task runner recipes"),
        ("flake.nix", "nix dev shell"),
        ("flake.lock", "locked nix inputs  (nix flake lock)"),
    ]


def _addon_files(ctx: Context) -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    for addon_id in ctx.addons:
        if addon_id == "docker":
            files += [
                ("Dockerfile", "multi-stage, uv-based"),
                ("compose.yml", "app service (+ redis/celery if selected)"),
                (".dockerignore", "excludes .venv, caches, secrets"),
            ]
        elif addon_id == "redis":
            files += [
                (
                    f"src/{ctx.pkg_name}/integrations/__init__.py",
                    "integrations package",
                ),
                (
                    f"src/{ctx.pkg_name}/integrations/redis.py",
                    "async pool + FastAPI dependency",
                ),
            ]
            if not ctx.has("docker"):
                files.append(("compose.redis.yml", "standalone redis service"))
        elif addon_id == "github-actions":
            files += [
                (".github/workflows/ci.yml", "lint + typecheck + test on push/PR"),
            ]
        elif addon_id == "celery":
            files += [
                (f"src/{ctx.pkg_name}/tasks/__init__.py", "tasks package"),
                (
                    f"src/{ctx.pkg_name}/tasks/celery_app.py",
                    "Celery instance + beat schedule",
                ),
                (f"src/{ctx.pkg_name}/tasks/example_tasks.py", "sample task"),
            ]
        elif addon_id == "sentry":
            files += [
                (
                    f"src/{ctx.pkg_name}/integrations/sentry.py",
                    "init_sentry() — no-ops when DSN unset",
                ),
            ]
    return files


def _commands(ctx: Context) -> list[str]:
    cmds = [
        "direnv allow",
        "nix flake lock",
        "git init",
        "git add .",
        'git commit -m "init: scaffold from sprout"',
    ]
    return cmds


def run_dry(ctx: Context) -> None:
    label = ctx.template
    if ctx.addons:
        label += " + " + ", ".join(ctx.addons)

    print(f"\n  {BOLD}{MAGENTA}Dry run:{RESET} {ctx.name}  {DIM}({label}){RESET}")
    print(f"  {DIM}Nothing will be written to disk.{RESET}")

    dry_header("Files")

    dry_section("common")
    for path, note in _common_files():
        dry_file(path, note)

    dry_section(f"template: {ctx.template}")
    for path, note in _template_files(ctx):
        dry_file(path, note)

    if ctx.addons:
        dry_section("addons")
        for path, note in _addon_files(ctx):
            dry_file(path, note)

    dry_section("generated")
    for path, note in _generated_files():
        dry_file(path, note)

    contributions = _collect(ctx)

    dry_header("Dependencies  (pyproject.toml)")

    dry_section("runtime")
    for dep in _base_deps(ctx):
        dry_dep(dep)
    for dep in contributions["extra_deps"]:
        dry_dep(dep, "addon")

    dry_section("dev")
    for dep in [
        "pytest>=8",
        "pytest-cov",
        "pytest-asyncio",
        "httpx",
        "mypy",
        "ipython",
    ]:
        dry_dep(dep)
    for dep in contributions["extra_dev_deps"]:
        dry_dep(dep, "addon")

    if contributions["extra_nix_packages"]:
        dry_header("Nix packages  (flake.nix)")
        for pkg in contributions["extra_nix_packages"]:
            dry_dep(pkg, "addon")

    if contributions["extra_just_recipes"]:
        dry_header("Extra just recipes")
        for block in contributions["extra_just_recipes"]:
            for line in block.strip().splitlines():
                print(f"  {DIM}{line}{RESET}")

    dry_header("Commands")
    for cmd in _commands(ctx):
        dry_cmd(cmd)

    print()
    print(f"  {DIM}Run without --dry-run to create the project.{RESET}\n")


def _base_deps(ctx: Context) -> list[str]:
    if ctx.template == "fastapi":
        return [
            "fastapi",
            "uvicorn[standard]",
            "sqlalchemy[asyncio]",
            "alembic",
            "asyncpg",
            "pydantic-settings",
            "passlib[bcrypt]",
            "python-jose[cryptography]",
            "email-validator",
            "python-multipart",
            "python-dotenv",
        ]
    return ["python-dotenv"]
