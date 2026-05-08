#!/usr/bin/env python3
"""zenit — scaffold Python projects from a template with optional addons."""

from importlib.metadata import version as get_version
from typing import Annotated

import typer

from scaffolder.add import add_addon
from scaffolder.config import config_path, load_config
from scaffolder.doctor import print_results, run_doctor
from scaffolder.scaffold import scaffold_project

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
    from scaffolder.prompt._render import TEMPLATES
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
        _add_interactive(dry_run=dry_run)
    else:
        # Direct mode — add the specified addon
        add_addon(addon, dry_run=dry_run)


def _add_interactive(dry_run: bool = False) -> None:
    """Interactive TUI for adding a single addon to an existing project."""
    from pathlib import Path

    from scaffolder.addons._registry import get_available_addons
    from scaffolder.lockfile import read_lockfile
    from scaffolder.prompt import prompt_single_addon
    from scaffolder.ui import error, info

    project_dir = Path.cwd()
    lockfile = read_lockfile(project_dir)

    if lockfile is None:
        error(
            "No .zenit.toml found. 'zenit add' only works in projects scaffolded by zenit."
        )
        raise typer.Exit(1)

    if not lockfile.template:
        error(".zenit.toml exists but has no template field — it may be corrupt.")
        raise typer.Exit(1)

    available = get_available_addons()

    already_installed = set(lockfile.addons)
    if already_installed:
        from scaffolder.ui import DIM, RESET

        print(
            f"\n  {DIM}Already installed: {', '.join(sorted(already_installed))}{RESET}"
        )

    items = []
    unavailable_indices = set()

    for addon in available:
        if addon.id in already_installed:
            continue

        deps_met = all(req in lockfile.addons for req in addon.requires)
        items.append((addon.id, addon.description, addon.requires))

        if not deps_met:
            unavailable_indices.add(len(items) - 1)

    if not items:
        info("All available addons are already installed.")
        print()
        return

    selected = prompt_single_addon(
        items,
        unavailable_indices=unavailable_indices,
        already_installed=sorted(already_installed) if already_installed else None,
    )

    if not selected:
        info("No addon selected.")
        print()
        return

    add_addon(selected, dry_run=dry_run)


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
        _remove_interactive(dry_run=dry_run)
    else:
        from scaffolder.exceptions import ScaffoldError
        from scaffolder.remove import remove_addon

        try:
            remove_addon(addon, dry_run=dry_run)
        except ScaffoldError as exc:
            from scaffolder.ui import error

            error(str(exc))
            raise typer.Exit(1) from exc


def _remove_interactive(dry_run: bool = False) -> None:
    """Interactive TUI for removing a single addon from an existing project."""
    import os
    from pathlib import Path

    from scaffolder.addons._registry import get_available_addons
    from scaffolder.lockfile import read_lockfile
    from scaffolder.prompt import prompt_single_addon
    from scaffolder.remove import remove_addon
    from scaffolder.ui import error, info

    project_dir = Path.cwd()
    lockfile = read_lockfile(project_dir)

    if lockfile is None:
        error(
            "No .zenit.toml found. 'zenit remove' only works in projects scaffolded by zenit."
        )
        raise typer.Exit(1)

    if not lockfile.template:
        error(".zenit.toml exists but has no template field — it may be corrupt.")
        raise typer.Exit(1)

    if not lockfile.addons:
        info("No addons are installed — nothing to remove.")
        print()
        return

    available = get_available_addons()

    # Addons that other *installed* addons depend on.
    requires_map_reverse: dict[str, list[str]] = {}
    for cfg in available:
        for req in cfg.requires:
            requires_map_reverse.setdefault(req, []).append(cfg.id)

    # Addons the template mandates — they cannot be removed.
    scaffolder_root = Path(os.environ.get("SCAFFOLDER_ROOT", Path(__file__).parent))
    template_required: set[str] = set()
    try:
        from scaffolder.templates._load_config import load_template_config

        template_config = load_template_config(scaffolder_root, lockfile.template)
        template_required = set(template_config.requires_addons)
    except Exception:
        pass

    items: list[tuple[str, str, list[str]]] = []
    unavailable_indices: set[int] = set()

    for addon_id in lockfile.addons:
        addon_cfg = next((c for c in available if c.id == addon_id), None)
        if addon_cfg is None:
            continue
        desc: str = addon_cfg.description

        # Collect the reasons this addon is blocked from removal.
        blocking: list[str] = []

        # Other installed addons that require this one.
        blocking.extend(
            dep
            for dep in requires_map_reverse.get(addon_id, [])
            if dep in lockfile.addons
        )

        # Template mandates it.
        if addon_id in template_required:
            blocking.append(f"required by {lockfile.template} template")

        items.append((addon_id, desc, blocking))
        if blocking:
            unavailable_indices.add(len(items) - 1)

    selected = prompt_single_addon(
        items,
        unavailable_indices=unavailable_indices,
        already_installed=None,
    )

    if not selected:
        info("No addon selected.")
        print()
        return

    from scaffolder.exceptions import ScaffoldError

    try:
        remove_addon(selected, dry_run=dry_run)
    except ScaffoldError as exc:
        from scaffolder.ui import error

        error(str(exc))
        raise typer.Exit(1) from exc


@app.command("doctor")
def cmd_doctor() -> None:
    """Check that the current project matches zenit's expectations."""
    from pathlib import Path

    from scaffolder.lockfile import read_lockfile
    from scaffolder.ui import error, success

    project_dir = Path.cwd()
    lockfile = read_lockfile(project_dir)

    if lockfile is None:
        error(
            "No .zenit.toml found. 'zenit doctor' only works in projects scaffolded by zenit."
        )
        raise typer.Exit(1)

    print(f"\n  Checking project '{project_dir.name}'…")

    results = run_doctor(project_dir)

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
