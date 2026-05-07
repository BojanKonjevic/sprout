#!/usr/bin/env python3
"""zenit — scaffold Python projects from a template with optional addons."""

import sys
from importlib.metadata import version as get_version
from typing import Annotated

import typer

from scaffolder.add import add_addon
from scaffolder.config import config_path, load_config
from scaffolder.scaffold import scaffold_project

app = typer.Typer(
    name="zenit",
    add_completion=False,
    pretty_exceptions_enable=False,
    invoke_without_command=True,
)


@app.callback()
def main_callback(
    version: Annotated[
        bool,
        typer.Option("--version", help="Show the version and exit"),
    ] = False,
) -> None:
    if version:
        print(get_version("zenit"))
        raise typer.Exit()


@app.command("list-templates")
def cmd_list_templates() -> None:
    """Show available project templates."""
    from scaffolder.prompt import TEMPLATES
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
        req_suffix = (
            f"  {DIM}requires: {', '.join(cfg.requires)}{RESET}" if cfg.requires else ""
        )
        print(f"  {CYAN}{cfg.id:<20}{RESET}  {DIM}{cfg.description}{RESET}{req_suffix}")
    print()


@app.command("config")
def cmd_config() -> None:
    """Show the config file path and current settings."""
    from scaffolder.ui import BOLD, CYAN, DIM, GREEN, RESET

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
    addon: Annotated[str, typer.Argument(help="Addon to add to the current project")],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview without writing anything")
    ] = False,
) -> None:
    """Add an addon to an existing zenit project in the current directory."""
    add_addon(addon, dry_run=dry_run)


def main() -> None:
    if len(sys.argv) == 1 or (
        len(sys.argv) > 1
        and sys.argv[1]
        not in {
            "list-templates",
            "list-addons",
            "config",
            "add",
            "--version",
            "--help",
        }
        and not sys.argv[1].startswith("-")
    ):
        import argparse

        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("name", nargs="?", default=None)
        parser.add_argument("--dry-run", action="store_true")
        args, _ = parser.parse_known_args()

        if args.name is not None:
            scaffold_project(args.name, dry_run=args.dry_run)
        else:
            app()
    else:
        app()


if __name__ == "__main__":
    main()
