"""Dry‑run mode – faithful preview by running apply functions with a recording context."""

from __future__ import annotations

from typing import Any

from scaffolder.context import Context
from scaffolder.generate import generate_all
from scaffolder.ui import (
    BOLD,
    DIM,
    GREEN,
    MAGENTA,
    RESET,
    dry_cmd,
    dry_dep,
    dry_header,
    dry_section,
)


class DryRunContext(Context):
    """A context that records every file operation without touching the disk."""

    recorded_files: list[tuple[str, str, str]]  # (action, path, details)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.recorded_files = []
        object.__setattr__(self, "_dry_run", True)

    @property
    def dry_run(self) -> bool:
        return True

    # Recording hooks
    def _record_write(self, path: str, content: str = "") -> None:
        self.recorded_files.append(("create", path, ""))

    def _record_dir(self, path: str) -> None:
        self.recorded_files.append(("mkdir", path, ""))

    def _record_copy(self, path: str) -> None:
        self.recorded_files.append(("copy", path, ""))

    def _record_append(self, path: str, content: str) -> None:
        preview = content.replace("\n", " ").strip()[:80]
        self.recorded_files.append(("append", path, preview))

    def _record_action(self, action: str, path: str, description: str) -> None:
        self.recorded_files.append((action, path, description))


def run_dry(ctx: Context) -> None:
    """Scaffold with a DryRunContext and display the resulting manifest."""
    dry_ctx = DryRunContext(
        name=ctx.name,
        pkg_name=ctx.pkg_name,
        template=ctx.template,
        addons=ctx.addons,
        scaffolder_root=ctx.scaffolder_root,
        project_dir=ctx.project_dir,
    )

    # 1. Common files (still imperative)
    from scaffolder.main import _load_apply

    sr = dry_ctx.scaffolder_root
    _load_apply(sr / "templates" / "_common" / "apply.py")(dry_ctx)

    # 2. Template files (imperative)
    _load_apply(sr / "templates" / dry_ctx.template / "apply.py")(dry_ctx)

    # 3. Declarative addon contributions (NEW)
    from scaffolder.addons._registry import get_available_addons
    from scaffolder.templates._load_config import load_template_config
    from scaffolder.assembler import collect_contributions, apply_contributions

    available = get_available_addons()
    selected = [cfg for cfg in available if cfg.id in dry_ctx.addons]
    contributions = collect_contributions(selected)

    template_config = load_template_config(sr, dry_ctx.template)

    apply_contributions(
        dry_ctx,
        contributions,
        template_config.extension_points,
        render_vars={
            "name": ctx.name,
            "pkg_name": ctx.pkg_name,
            "template": ctx.template,
        },
    )

    # 4. Generate config files (pyproject.toml / justfile)
    generate_all(dry_ctx, contributions)

    # ---- Display the manifest (unchanged from original) ----
    label = dry_ctx.template
    if dry_ctx.addons:
        label += " + " + ", ".join(dry_ctx.addons)

    print(f"\n  {BOLD}{MAGENTA}Dry run:{RESET} {dry_ctx.name}  {DIM}({label}){RESET}")
    print(f"  {DIM}Nothing will be written to disk.{RESET}\n")

    dry_header("Files that would be created or modified")

    for action, path, details in dry_ctx.recorded_files:
        if action == "mkdir":
            print(f"  {MAGENTA}►{RESET} {path}/")
        elif action in ("create", "copy"):
            print(f"  {GREEN}+{RESET} {path}{'  ' + DIM + details + RESET if details else ''}")
        elif action == "append":
            print(f"  {GREEN}+{RESET} {path}  {DIM}(appended){RESET}")
        elif action == "modify":
            print(f"  {GREEN}△{RESET} {path}  {DIM}{details}{RESET}")

    print()
    dry_section("Dependencies (pyproject.toml)")
    dry_section("  runtime")
    for dep in _base_deps(dry_ctx):
        dry_dep(dep)
    for dep in contributions.deps:
        dry_dep(dep, "addon")
    dry_section("  dev")
    for dep in ["pytest>=8", "pytest-cov", "pytest-asyncio", "httpx", "mypy", "ipython"]:
        dry_dep(dep)
    for dep in contributions.dev_deps:
        dry_dep(dep, "addon")

    dry_header("Generated config files")
    for template_name in ["pyproject.toml", "justfile"]:
        dry_dep(template_name)

    dry_header("Commands that would run")
    for cmd in [
        "direnv allow",
        "git init",
        "git add .",
        'git commit -m "init: scaffold from jumpstart"',
    ]:
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
