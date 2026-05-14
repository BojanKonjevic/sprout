#!/usr/bin/env python3
"""zenit — scaffold Python projects from a template with optional addons."""

from importlib.metadata import version as get_version
from typing import Annotated

import typer

from scaffolder.addons.add import add_addon
from scaffolder.config.config import config_path, load_config
from scaffolder.core.scaffold import scaffold_project
from scaffolder.doctor.doctor import print_results, run_doctor

app = typer.Typer(
    name="zenit",
    add_completion=False,
    pretty_exceptions_enable=False,
    no_args_is_help=True,
)


@app.callback()
def main_callback(
    version: Annotated[
        bool,
        typer.Option("--version", help="Show the version and exit"),
    ] = False,
) -> None:
    """Scaffold Python projects from a template with optional addons."""
    if version:
        print(get_version("zenit"))
        raise typer.Exit()


@app.command("create")
def cmd_create(
    name: Annotated[str, typer.Argument(help="Name of the project to create")],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview without writing anything")
    ] = False,
) -> None:
    """Create a new project from a template."""
    scaffold_project(name, dry_run=dry_run)


@app.command("list-templates")
def cmd_list_templates() -> None:
    """Show available project templates."""
    from scaffolder.cli.prompt._render import TEMPLATES
    from scaffolder.cli.ui import CYAN, DIM, RESET

    print()
    for name, desc in TEMPLATES:
        print(f"  {CYAN}{name:<12}{RESET}  {DIM}{desc}{RESET}")
    print()


@app.command("list-addons")
def cmd_list_addons() -> None:
    """Show available addons."""
    from scaffolder.addons._registry import get_available_addons
    from scaffolder.cli.ui import CYAN, DIM, RESET

    configs = get_available_addons()
    print()
    for cfg in configs:
        req_suffix = (
            f"  {DIM}requires: {', '.join(cfg.requires)}{RESET}" if cfg.requires else ""
        )
        print(f"  {CYAN}{cfg.id:<20}{RESET}  {DIM}{cfg.description}{RESET}{req_suffix}")
    print()


@app.command("config")
def cmd_config() -> None:
    """Show the config file path and current settings."""
    from scaffolder.cli.ui import BOLD, CYAN, DIM, GREEN, RESET

    path = config_path()
    cfg = load_config()

    print(f"\n  {BOLD}Config file:{RESET}  {CYAN}{path}{RESET}")
    if path.exists():
        print(f"  {GREEN}✓{RESET}  {DIM}file exists{RESET}")
    else:
        print(f"  {DIM}file does not exist — using built‑in defaults{RESET}")

    print()
    template_val = (
        f"{cfg.default_template}" if cfg.default_template else f"{DIM}not set{RESET}"
    )
    addons_val = (
        ", ".join(cfg.default_addons) if cfg.default_addons else f"{DIM}not set{RESET}"
    )
    print(f"  default_template  =  {template_val}")
    print(f"  default_addons    =  {addons_val}")

    if not path.exists():
        print()
        print(f"  {DIM}Create the file to set your own defaults.  Example:{RESET}")
        print()
        print(f'  {DIM}  default_template = "fastapi"{RESET}')
        print(f'  {DIM}  default_addons = ["docker", "github-actions"]{RESET}')

    print()


@app.command("add")
def cmd_add(
    addon: Annotated[
        str | None,
        typer.Argument(
            help="Addon to add to the current project (omit for interactive selection)"
        ),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview without writing anything")
    ] = False,
) -> None:
    """Add an addon to an existing zenit project in the current directory.

    Run without arguments to select addons interactively.
    """
    if addon is None:
        # Interactive mode — show the TUI to pick addons
        from scaffolder.addons.add import add_addon_interactive

        add_addon_interactive(dry_run=dry_run)
    else:
        # Direct mode — add the specified addon
        add_addon(addon, dry_run=dry_run)


@app.command("remove")
def cmd_remove(
    addon: Annotated[
        str | None,
        typer.Argument(
            help="Addon to remove from the current project (omit for interactive selection)"
        ),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview without writing anything")
    ] = False,
) -> None:
    """Remove an addon from an existing zenit project in the current directory.

    Run without arguments to select an addon interactively.
    """
    if addon is None:
        from scaffolder.addons.remove import remove_addon_interactive

        remove_addon_interactive(dry_run=dry_run)
    else:
        from scaffolder.addons.remove import remove_addon
        from scaffolder.schema.exceptions import ScaffoldError

        try:
            remove_addon(addon, dry_run=dry_run)
        except ScaffoldError as exc:
            from scaffolder.cli.ui import error

            error(str(exc))
            raise typer.Exit(1) from exc


@app.command("doctor")
def cmd_doctor(
    thorough: Annotated[
        bool,
        typer.Option(
            "--thorough", help="Run full Python block integrity checks (slower)"
        ),
    ] = False,
) -> None:
    """Check that the current project matches zenit's expectations."""
    from pathlib import Path

    from scaffolder.cli.ui import DIM, RESET, error, success
    from scaffolder.core.lockfile import read_lockfile

    project_dir = Path.cwd()
    lockfile = read_lockfile(project_dir)

    if lockfile is None:
        error(
            "No .zenit.toml found. 'zenit doctor' only works in projects scaffolded by zenit."
        )
        raise typer.Exit(1)

    print(f"\n  Checking project '{project_dir.name}'…")
    if thorough:
        print(f"  {DIM}Thorough mode — parsing Python files with libcst.{RESET}")

    results = run_doctor(project_dir, thorough=thorough)

    if not results:
        print("\n  No checks registered yet.\n")
        return

    has_errors = print_results(results)

    print()
    if has_errors:
        error("Project has issues that may prevent zenit commands from working.")
        raise typer.Exit(1)
    else:
        success("Project looks healthy.")
    print()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
