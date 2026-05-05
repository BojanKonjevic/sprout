import importlib.util
import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from scaffolder.context import Context
from scaffolder.generate import generate_all
from scaffolder.git import init_and_commit
from scaffolder.prompt import TEMPLATES, prompt_addons, prompt_template
from scaffolder.rollback import scaffold_or_rollback
from scaffolder.ui import confirm, error, info, step, success

app = typer.Typer(
    name="sprout",
    add_completion=False,
    pretty_exceptions_enable=False,
)


def _load_apply(path: Path) -> Callable[[Context], None]:
    spec = importlib.util.spec_from_file_location("apply", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.apply  # type: ignore[no-any-return]


def _load_addon_registry(scaffolder_root: Path) -> list[tuple[str, str, list[str]]]:
    registry_path = scaffolder_root / "addons" / "_registry.py"
    spec = importlib.util.spec_from_file_location("_registry", registry_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.ADDONS  # type: ignore[no-any-return]


@app.command()
def scaffold(
    name: Annotated[str, typer.Argument(help="Project name to scaffold")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without writing")] = False,
) -> None:
    """Scaffold a new Python project from a template."""
    scaffolder_root = Path(os.environ.get("SCAFFOLDER_ROOT", Path(__file__).parent.parent.parent))
    pkg_name = name.replace("-", "_")

    from scaffolder.validate import check_preflight, validate_addon_deps, validate_name

    validate_name(name, pkg_name)

    if not dry_run:
        check_preflight()

    template = prompt_template()
    available_addons = _load_addon_registry(scaffolder_root)
    addons = prompt_addons(available_addons, template)
    validate_addon_deps(addons, available_addons)

    ctx = Context(
        name=name,
        pkg_name=pkg_name,
        template=template,
        addons=addons,
        scaffolder_root=scaffolder_root,
        project_dir=Path.cwd() / name,
    )

    if dry_run:
        from scaffolder.dryrun import DryRunContext, run_dry

        dry_ctx = DryRunContext(
            name=name,
            pkg_name=pkg_name,
            template=template,
            addons=addons,
            scaffolder_root=scaffolder_root,
            project_dir=Path.cwd() / name,
        )
        run_dry(dry_ctx)
        return

    if not confirm(ctx):
        print("\n  \033[0;33mAborted.\033[0m\n")
        raise typer.Exit(0)

    project_dir = ctx.project_dir
    with scaffold_or_rollback(project_dir):
        project_dir.mkdir()
        os.chdir(project_dir)

        _load_apply(scaffolder_root / "templates" / "_common" / "apply.py")(ctx)
        _load_apply(scaffolder_root / "templates" / template / "apply.py")(ctx)

        for addon_id in addons:
            addon_apply = scaffolder_root / "addons" / addon_id / "apply.py"
            if not addon_apply.exists():
                error(f"Addon '{addon_id}' has no apply.py — skipping.")
                continue
            step(f"Applying addon: {addon_id}")
            _load_apply(addon_apply)(ctx)

        generate_all(ctx)
        init_and_commit(project_dir)

    print()
    success(f"Project '{name}' ready!  ({template}{' + ' + ', '.join(addons) if addons else ''})")
    print()
    print(f"  cd {name}")

    _print_commands(template, pkg_name, addons)

    if sys.platform == "win32":
        print()
        info("Your environment is managed by uv — no activation needed.")
        info("Every 'just' command runs through 'uv run' and syncs automatically.")
    elif not shutil.which("direnv"):
        print()
        info("direnv not detected — run 'uv sync' once to set up your environment,")
        info("or install direnv and run 'direnv allow' for auto-activation on cd.")

    if "docker" in addons:
        print()
        info("Docker:")
        print("    just docker-up    # build + start all services")
        print("    just docker-down  # stop")

    if "redis" in addons:
        print()
        info("Redis:")
        print("    just redis-up     # start redis via compose")

    if "github-actions" in addons:
        print()
        info("GitHub Actions CI is set up at .github/workflows/ci.yml")
        print("    Push to GitHub and it will lint, type-check, and test automatically.")


@app.command("list-templates")
def cmd_list_templates() -> None:
    """Show available project templates."""
    from scaffolder.ui import CYAN, DIM, RESET

    print()
    for name, desc in TEMPLATES:
        print(f"  {CYAN}{name:<12}{RESET}  {DIM}{desc}{RESET}")
    print()


@app.command("list-addons")
def cmd_list_addons() -> None:
    """Show available addons."""
    from scaffolder.ui import CYAN, DIM, RESET

    scaffolder_root = Path(os.environ.get("SCAFFOLDER_ROOT", Path(__file__).parent.parent.parent))
    addons = _load_addon_registry(scaffolder_root)
    print()
    for addon_id, desc, requires in addons:
        req_suffix = f"  {DIM}requires: {', '.join(requires)}{RESET}" if requires else ""
        print(f"  {CYAN}{addon_id:<20}{RESET}  {DIM}{desc}{RESET}{req_suffix}")
    print()


def main() -> None:
    app()


def _print_commands(template: str, pkg_name: str, addons: list[str]) -> None:
    BOLD = "\033[1m"
    CYAN = "\033[0;36m"
    RESET = "\033[0m"

    def cmd(label: str, desc: str) -> None:
        print(f"  {CYAN}{label:<26}{RESET} {desc}")

    print()
    print(f"  {BOLD}Available commands:{RESET}")
    print()
    cmd("just test", "run tests")
    cmd("just cov", "coverage report")
    cmd("just lint", "ruff check")
    cmd("just fmt", "ruff format")
    cmd("just check", "mypy")

    if template == "fastapi":
        cmd("just run", "start dev server (--reload)")
        cmd('just migrate "msg"', "generate migration")
        cmd("just upgrade", "apply migrations")
        cmd("just downgrade", "roll back one step")
        cmd("just db-create", "start db + create databases + migrate")
        cmd("just db-reset", "drop + recreate databases")
    else:
        cmd("just run", "run the app")

    for addon_id in addons:
        if addon_id in ("docker", "redis"):
            cmd(f"just {addon_id}-up", f"start {addon_id} (compose)")
            cmd(f"just {addon_id}-down", f"stop {addon_id} (compose)")
        if addon_id == "celery":
            cmd("just celery-up", "start celery worker + beat")
            cmd("just celery-down", "stop celery")
            cmd("just celery-flower", "flower monitoring UI")
            cmd("just celery-logs", "tail worker logs")
        if addon_id == "sentry":
            cmd("just sentry-check", "verify SDK version")
            cmd("just sentry-test", "check DSN is set")
    print()
