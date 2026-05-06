#!/usr/bin/env python3
"""jumpstart CLI – scaffold Python projects with optional addons."""

import importlib.util
import os
import secrets
import shutil
import sys
from collections.abc import Callable
from importlib.metadata import version as get_version
from pathlib import Path
from typing import Annotated

import typer

from scaffolder.context import Context
from scaffolder.generate import generate_all
from scaffolder.git import init_and_commit
from scaffolder.prompt import TEMPLATES, prompt_addons, prompt_template
from scaffolder.rollback import scaffold_or_rollback
from scaffolder.ui import confirm, info, success

app = typer.Typer(
    name="jumpstart",
    add_completion=False,
    pretty_exceptions_enable=False,
)


def _load_apply(path: Path) -> Callable[[Context], None]:
    """Import and return the apply() function from an old‑style apply.py file."""
    spec = importlib.util.spec_from_file_location("apply", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.apply  # type: ignore[no-any-return]


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", help="Show the version and exit"),
    ] = False,
) -> None:
    if version:
        print(get_version("jumpstart-cli"))
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        print(app.get_help(ctx))  # type: ignore[attr-defined]
        raise typer.Exit()


@app.command()
def scaffold(
    name: Annotated[str, typer.Argument(help="Project name to scaffold")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without writing")] = False,
) -> None:
    """Scaffold a new Python project from a template."""
    scaffolder_root = Path(os.environ.get("SCAFFOLDER_ROOT", Path(__file__).parent))
    pkg_name = name.replace("-", "_")

    from scaffolder.validate import check_preflight, validate_addon_deps, validate_name

    validate_name(name, pkg_name)

    if not dry_run:
        check_preflight()

    template = prompt_template()

    from scaffolder.addons._registry import get_available_addons

    available = get_available_addons()
    addons = prompt_addons(available, template)
    validate_addon_deps(addons, available)

    ctx = Context(
        name=name,
        pkg_name=pkg_name,
        template=template,
        addons=addons,
        scaffolder_root=scaffolder_root,
        project_dir=Path.cwd() / name,
    )

    if dry_run:
        from scaffolder.dryrun import run_dry

        run_dry(ctx)
        return

    if not confirm(ctx):
        print("\n  \033[0;33mAborted.\033[0m\n")
        raise typer.Exit(0)

    project_dir = ctx.project_dir
    with scaffold_or_rollback(project_dir):
        project_dir.mkdir()
        os.chdir(project_dir)

        _load_apply(scaffolder_root / "templates" / "_common" / "apply.py")(ctx)

        from scaffolder.assembler import apply_contributions, collect_all
        from scaffolder.templates._load_config import load_template_config

        template_config = load_template_config(scaffolder_root, template)
        selected_addon_configs = [cfg for cfg in available if cfg.id in addons]

        secret_key = secrets.token_hex(32) if template == "fastapi" else None

        contributions = collect_all(template_config, selected_addon_configs)

        # Build render_vars once — never pass name= explicitly alongside **render_vars
        render_vars: dict[str, object] = {
            "name": name,
            "pkg_name": pkg_name,
            "template": template,
            "secret_key": secret_key or "change-me-run-openssl-rand-hex-32",
            "has_postgres": template == "fastapi",
            "has_redis": "redis" in addons,
        }

        apply_contributions(
            ctx,
            contributions,
            template_config.extension_points,
            render_vars,
        )

        generate_all(ctx, template_config, contributions)

        init_and_commit(project_dir)

    print()
    success(
        f"Project '{name}' ready!  ({template}"
        + (" + " + ", ".join(addons) if addons else "")
        + ")"
    )
    print()
    print(f"  cd {name}")

    _print_commands_from_just(project_dir)

    if sys.platform == "win32":
        print()
        info("Your environment is managed by uv — no activation needed.")
        info("Every 'just' command runs through 'uv run' and syncs automatically.")
    elif not shutil.which("direnv"):
        print()
        info("direnv not detected — run 'uv sync' once to set up your environment,")
        info("or install direnv and run 'direnv allow' for auto-activation on cd.")

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
    from scaffolder.addons._registry import get_available_addons
    from scaffolder.ui import CYAN, DIM, RESET

    configs = get_available_addons()
    print()
    for cfg in configs:
        req_suffix = f"  {DIM}requires: {', '.join(cfg.requires)}{RESET}" if cfg.requires else ""
        print(f"  {CYAN}{cfg.id:<20}{RESET}  {DIM}{cfg.description}{RESET}{req_suffix}")
    print()


def main() -> None:
    app()


def _print_commands_from_just(project_dir: Path) -> None:
    import shutil
    import subprocess

    if not shutil.which("just"):
        return
    print()
    subprocess.run(["just", "--list"], cwd=project_dir)
