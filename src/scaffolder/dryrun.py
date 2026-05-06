"""Dry-run mode — faithful preview by running the scaffold pipeline with a
recording context that captures every file operation without touching disk."""

from __future__ import annotations

import secrets
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
    """A ``Context`` subclass that records every file operation instead of
    executing it, leaving the filesystem completely untouched."""

    # List of (action, path, details) tuples recorded during the dry run.
    recorded_files: list[tuple[str, str, str]]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.recorded_files = []
        object.__setattr__(self, "_dry_run", True)

    @property
    def dry_run(self) -> bool:
        return True

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
    """Run the scaffold pipeline with a ``DryRunContext`` and print the manifest."""
    dry_ctx = DryRunContext(
        name=ctx.name,
        pkg_name=ctx.pkg_name,
        template=ctx.template,
        addons=ctx.addons,
        scaffolder_root=ctx.scaffolder_root,
        project_dir=ctx.project_dir,
    )

    from scaffolder.main import _load_apply

    sr = dry_ctx.scaffolder_root
    _load_apply(sr / "templates" / "_common" / "apply.py")(dry_ctx)

    from scaffolder.addons._registry import get_available_addons
    from scaffolder.assembler import apply_contributions, collect_all
    from scaffolder.templates._load_config import load_template_config

    available = get_available_addons()
    template_config = load_template_config(sr, dry_ctx.template)
    selected_addon_configs = [cfg for cfg in available if cfg.id in dry_ctx.addons]

    secret_key = secrets.token_hex(32) if dry_ctx.template == "fastapi" else None

    contributions = collect_all(template_config, selected_addon_configs)

    render_vars: dict[str, object] = {
        "name": ctx.name,
        "pkg_name": ctx.pkg_name,
        "template": ctx.template,
        "secret_key": secret_key or "change-me-run-openssl-rand-hex-32",
        "has_postgres": ctx.template == "fastapi",
        "has_redis": "redis" in ctx.addons,
    }

    apply_contributions(
        dry_ctx,
        contributions,
        template_config.extension_points,
        render_vars,
    )

    generate_all(dry_ctx, template_config, contributions)

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
            suffix = f"  {DIM}{details}{RESET}" if details else ""
            print(f"  {GREEN}+{RESET} {path}{suffix}")
        elif action == "append":
            print(f"  {GREEN}+{RESET} {path}  {DIM}(appended){RESET}")
        elif action == "modify":
            print(f"  {GREEN}△{RESET} {path}  {DIM}{details}{RESET}")

    print()
    dry_section("Dependencies (pyproject.toml)")
    dry_section("  runtime")
    for dep in template_config.deps:
        dry_dep(dep)
    for dep in contributions.deps:
        dry_dep(dep, "addon")
    dry_section("  dev")
    for dep in [
        "pytest>=8",
        "pytest-cov",
        "pytest-asyncio",
        "httpx",
        "mypy",
        "ipython",
    ]:
        dry_dep(dep)
    for dep in template_config.dev_deps:
        dry_dep(dep, "template")
    for dep in contributions.dev_deps:
        dry_dep(dep, "addon")

    dry_header("Generated config files")
    for file_name in ["pyproject.toml", "justfile"]:
        dry_dep(file_name)

    dry_header("Commands that would run")
    for cmd in [
        "direnv allow",
        "git init",
        "git add .",
        'git commit -m "init: scaffold from zenit"',
    ]:
        dry_cmd(cmd)

    print()
    print(f"  {DIM}Run without --dry-run to create the project.{RESET}\n")
