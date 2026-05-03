"""Dry-run mode.

Collects what the scaffold *would* do and prints a structured preview
without creating any files, running any subprocesses, or making any
network calls (no nix flake lock, no git init, no direnv allow).
"""

import importlib.util
from pathlib import Path
from typing import Any

from scaffolder.context import Context
from scaffolder.generate import _collect
from scaffolder.ui import (
    BOLD,
    CYAN,
    DIM,
    GREEN,
    MAGENTA,
    RESET,
    YELLOW,
    dry_cmd,
    dry_dep,
    dry_file,
    dry_header,
    dry_section,
    step,
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
            (f"src/{p}/main.py", "FastAPI app + lifespan"),
            (f"src/{p}/database.py", "SQLAlchemy engine + session"),
            (f"src/{p}/models.py", "SQLAlchemy models (empty scaffold)"),
            (f"src/{p}/security.py", "JWT + bcrypt helpers"),
            (f"src/{p}/settings.py", "pydantic-settings"),
            (f"src/{p}/routes/__init__.py", "routes package"),
            ("alembic.ini", "alembic config"),
            ("alembic/env.py", "async alembic env"),
            ("alembic/script.py.mako", "migration template"),
            ("alembic/versions/", "migrations directory"),
            ("tests/conftest.py", "pytest fixtures (session, anon_client, client)"),
            ("tests/test_main.py", "GET / smoke test"),
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
                ("Dockerfile", "multi-stage, uv-based  (cmd depends on template)"),
                ("compose.yml", "app service (+ redis if selected)"),
                (".dockerignore", "excludes .venv, caches, secrets"),
            ]
        elif addon_id == "redis":
            files += [
                (
                    f"src/{ctx.pkg_name}/redis.py",
                    "async connection pool + FastAPI dependency",
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
                (
                    f"src/{ctx.pkg_name}/worker.py",
                    "Celery app instance + beat schedule",
                ),
                (f"src/{ctx.pkg_name}/tasks.py", "sample task + decorator pattern"),
            ]
        elif addon_id == "sentry":
            files += [
                (
                    f"src/{ctx.pkg_name}/sentry.py",
                    "init_sentry() — no-ops when DSN is unset",
                ),
            ]
    return files


def _commands(ctx: Context) -> list[str]:
    cmds = [
        "direnv allow",
        "nix flake lock",
        "git init",
        "git add .",
        'git commit -m "init: scaffold from new-python-project"',
    ]
    if ctx.template == "fastapi":
        cmds.insert(2, f"createdb {ctx.name}")
        cmds.insert(3, f"createdb {ctx.name}_test")
    return cmds


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_dry(ctx: Context) -> None:
    label = ctx.template
    if ctx.addons:
        label += " + " + ", ".join(ctx.addons)

    print(f"\n  {BOLD}{MAGENTA}Dry run:{RESET} {ctx.name}  {DIM}({label}){RESET}")
    print(f"  {DIM}Nothing will be written to disk.{RESET}")

    # --- Files that would be created ---
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

    # --- Dependencies ---
    contributions = _collect(ctx)

    dry_header("Dependencies  (pyproject.toml)")

    dry_section("runtime")
    base_deps = _base_deps(ctx)
    for dep in base_deps:
        dry_dep(dep)
    for dep in contributions["extra_deps"]:
        dry_dep(dep, "addon")

    dry_section("dev")
    base_dev = ["pytest>=8", "pytest-cov", "pytest-asyncio", "httpx", "mypy", "ipython"]
    for dep in base_dev:
        dry_dep(dep)
    for dep in contributions["extra_dev_deps"]:
        dry_dep(dep, "addon")

    # --- Nix packages ---
    if contributions["extra_nix_packages"]:
        dry_header("Nix packages  (flake.nix)")
        for pkg in contributions["extra_nix_packages"]:
            dry_dep(pkg, "addon")

    # --- Just recipes ---
    if contributions["extra_just_recipes"]:
        dry_header("Extra just recipes")
        for block in contributions["extra_just_recipes"]:
            for line in block.strip().splitlines():
                print(f"  {DIM}{line}{RESET}")

    # --- Commands that would run ---
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
