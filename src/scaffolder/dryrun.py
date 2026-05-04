"""Dry-run mode — faithful preview by running apply functions with a recording context."""

from typing import Any

from scaffolder.context import Context
from scaffolder.generate import _collect, generate_all
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
        # Let the dataclass init do its thing (including setting _dry_run to False)
        super().__init__(**kwargs)
        self.recorded_files = []
        # Force dry_run to be True by setting the private attribute directly
        object.__setattr__(self, "_dry_run", True)

    @property
    def dry_run(self) -> bool:  # always True
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


def run_dry(ctx_template: Context) -> None:
    """Scaffold with a DryRunContext and display the resulting manifest."""
    dry_ctx = DryRunContext(
        name=ctx_template.name,
        pkg_name=ctx_template.pkg_name,
        template=ctx_template.template,
        addons=ctx_template.addons,
        scaffolder_root=ctx_template.scaffolder_root,
        project_dir=ctx_template.project_dir,
    )

    # Import apply loaders (private helpers from main)
    from scaffolder.main import _load_apply

    # Run common, template, and addon applies – exactly as a real scaffold would
    sr = dry_ctx.scaffolder_root
    _load_apply(sr / "templates" / "_common" / "apply.py")(dry_ctx)
    _load_apply(sr / "templates" / dry_ctx.template / "apply.py")(dry_ctx)
    for addon_id in dry_ctx.addons:
        addon_apply = sr / "addons" / addon_id / "apply.py"
        if addon_apply.exists():
            _load_apply(addon_apply)(dry_ctx)

    # Generate config files (pyproject.toml, justfile)
    generate_all(dry_ctx)

    # Collect extra deps / just recipes
    contributions = _collect(dry_ctx)
    base_deps = _base_deps(dry_ctx)

    # ── Display the manifest ───────────────────────────────────────────

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
    for dep in base_deps:
        dry_dep(dep)
    for dep in contributions["extra_deps"]:
        dry_dep(dep, "addon")
    dry_section("  dev")
    for dep in ["pytest>=8", "pytest-cov", "pytest-asyncio", "httpx", "mypy", "ipython"]:
        dry_dep(dep)
    for dep in contributions["extra_dev_deps"]:
        dry_dep(dep, "addon")

    dry_header("Generated config files")
    for template_name in ["pyproject.toml", "justfile"]:
        dry_dep(template_name)

    dry_header("Commands that would run")
    for cmd in [
        "direnv allow",
        "git init",
        "git add .",
        'git commit -m "init: scaffold from sprout"',
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
