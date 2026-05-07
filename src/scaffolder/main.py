#!/usr/bin/env python3
"""zenit — scaffold Python projects from a template with optional addons."""

import importlib.util
import os
import re
import secrets
import shutil
import sys
from collections.abc import Callable
from importlib.metadata import version as get_version
from pathlib import Path
from typing import Annotated

import typer

from scaffolder.config import load_config
from scaffolder.context import Context
from scaffolder.generate import generate_all
from scaffolder.git import init_and_commit
from scaffolder.prompt import TEMPLATES, prompt_addons, prompt_template
from scaffolder.render import make_env
from scaffolder.rollback import scaffold_or_rollback
from scaffolder.ui import confirm, info, success, warn

app = typer.Typer(
    name="zenit",
    add_completion=False,
    pretty_exceptions_enable=False,
    invoke_without_command=True,
)


def _load_apply(path: Path) -> Callable[[Context], None]:
    """Import and return the ``apply()`` function from an ``apply.py`` file."""
    spec = importlib.util.spec_from_file_location("apply", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.apply  # type: ignore[no-any-return]


def _strip_zenit_sentinels(project_dir: Path) -> None:
    """Remove all # [zenit: ...] sentinel lines from generated source files."""
    pattern = re.compile(r"^\s*# \[zenit: [^\]]+\]\s*\n", re.MULTILINE)
    for path in project_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        cleaned = pattern.sub("", text)
        if cleaned != text:
            path.write_text(cleaned, encoding="utf-8")


def _scaffold(
    name: str,
    dry_run: bool = False,
) -> None:
    scaffolder_root = Path(os.environ.get("SCAFFOLDER_ROOT", Path(__file__).parent))
    pkg_name = name.replace("-", "_")

    from scaffolder.validate import check_preflight, validate_addon_deps, validate_name

    validate_name(name, pkg_name)

    if not dry_run:
        check_preflight()

    cfg = load_config()

    template = prompt_template(default=cfg.default_template)

    from scaffolder.addons._registry import get_available_addons

    available = get_available_addons()
    addons = prompt_addons(available, template, default_addons=cfg.default_addons)
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

        _load_apply(scaffolder_root / "templates" / "_common" / "apply.py")(ctx)

        from scaffolder.assembler import apply_contributions, collect_all
        from scaffolder.templates._load_config import load_template_config

        template_config = load_template_config(scaffolder_root, template)
        selected_addon_configs = [a for a in available if a.id in addons]

        secret_key = secrets.token_hex(32) if template == "fastapi" else None

        contributions = collect_all(template_config, selected_addon_configs)

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
        _strip_zenit_sentinels(project_dir)
        init_and_commit(project_dir)

        from scaffolder.lockfile import write_lockfile

        write_lockfile(project_dir, template, addons)

    print()
    addon_suffix = (" + " + ", ".join(addons)) if addons else ""
    success(f"Project '{name}' ready!  ({template}{addon_suffix})")
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
        print(
            "    Push to GitHub and it will lint, type-check, and test automatically."
        )


def _add(addon_id: str, dry_run: bool = False) -> None:
    """Apply a single addon to an existing zenit project."""
    from scaffolder.addons._registry import get_available_addons
    from scaffolder.checks import check_can_add
    from scaffolder.exceptions import ScaffoldError
    from scaffolder.lockfile import write_lockfile

    project_dir = Path.cwd()
    available = get_available_addons()

    try:
        lockfile = check_can_add(project_dir, addon_id, available)
    except ScaffoldError as exc:
        from scaffolder.ui import error

        error(str(exc))
        raise typer.Exit(1)

    template = lockfile.template
    pkg_name = project_dir.name.replace("-", "_")
    scaffolder_root = Path(os.environ.get("SCAFFOLDER_ROOT", Path(__file__).parent))

    ctx = Context(
        name=project_dir.name,
        pkg_name=pkg_name,
        template=template,
        addons=lockfile.addons + [addon_id],
        scaffolder_root=scaffolder_root,
        project_dir=project_dir,
    )

    if dry_run:
        _dry_add(ctx, addon_id, available, template)
        return

    from scaffolder.ui import BOLD, CYAN, DIM, RESET, YELLOW

    print(f"\n  {BOLD}Ready to add addon:{RESET}")
    print(f"\n    {'addon':<12}  {BOLD}{addon_id}{RESET}")
    print(f"    {'project':<12}  {DIM}{project_dir}{RESET}")
    print(f"    {'template':<12}  {CYAN}{template}{RESET}")
    print()

    if sys.stdin.isatty():
        try:
            raw = input(f"  Proceed? {DIM}[Y/n]{RESET}  ").strip().lower()
        except EOFError, KeyboardInterrupt:
            print()
            raise typer.Exit(0)
        if raw not in ("", "y", "yes"):
            print(f"\n  {YELLOW}Aborted.{RESET}\n")
            raise typer.Exit(0)
    else:
        warn("Non-interactive mode — proceeding automatically.")

    from scaffolder.assembler import apply_contributions, collect_all
    from scaffolder.templates._load_config import load_template_config

    template_config = load_template_config(scaffolder_root, template)
    selected_addon_configs = [a for a in available if a.id == addon_id]

    render_vars: dict[str, object] = {
        "name": project_dir.name,
        "pkg_name": pkg_name,
        "template": template,
        "secret_key": "",
        "has_postgres": template == "fastapi",
        "has_redis": "redis" in ctx.addons,
    }

    contributions = collect_all(template_config, selected_addon_configs)

    apply_contributions(
        ctx,
        contributions,
        template_config.extension_points,
        render_vars,
    )

    _strip_zenit_sentinels(project_dir)

    # ── deps ──────────────────────────────────────────────────────────────────
    from scaffolder.deps import inject_deps
    from scaffolder.ui import BOLD, DIM, GREEN, RESET, YELLOW  # noqa: F811

    try:
        added_deps, added_dev_deps = inject_deps(
            project_dir,
            contributions.deps,
            contributions.dev_deps,
        )
    except FileNotFoundError as exc:
        warn(str(exc))
        added_deps, added_dev_deps = [], []

    # ── justfile recipes ──────────────────────────────────────────────────────
    from scaffolder.justfile import inject_just_recipes

    recipe_render_vars: dict[str, object] = {
        "name": project_dir.name,
        "pkg_name": pkg_name,
        "template": template,
        "addons": ctx.addons,
    }
    string_env = make_env()
    rendered_recipes = [
        string_env.from_string(r).render(**recipe_render_vars)
        for r in contributions.just_recipes
    ]
    added_recipes = inject_just_recipes(project_dir, rendered_recipes)

    # ── lockfile ──────────────────────────────────────────────────────────────
    new_addons = lockfile.addons + [addon_id]
    write_lockfile(project_dir, template, new_addons)

    # ── output ────────────────────────────────────────────────────────────────
    print()
    success(f"Addon '{addon_id}' added to '{project_dir.name}'.")

    if added_deps or added_dev_deps:
        print()
        print(f"  {BOLD}Dependencies added to pyproject.toml:{RESET}")
        for dep in added_deps:
            print(f"    {GREEN}+{RESET} {dep}")
        for dep in added_dev_deps:
            print(f"    {GREEN}+{RESET} {dep}  {DIM}(dev){RESET}")
        info("Run 'uv sync' to install them.")
    else:
        info("No new dependencies were needed.")

    if added_recipes:
        print()
        print(f"  {BOLD}Just recipes added:{RESET}")
        for name in added_recipes:
            print(f"    {GREEN}+{RESET} {name}")

    print()


def _dry_add(
    ctx: Context,
    addon_id: str,
    available: list,  # type: ignore[type-arg]
    template: str,
) -> None:
    """Print what `zenit add` would do without writing anything."""
    from scaffolder.assembler import apply_contributions, collect_all
    from scaffolder.dryrun import DryRunContext
    from scaffolder.generate import _recipe_name
    from scaffolder.templates._load_config import load_template_config
    from scaffolder.ui import (
        BOLD,
        DIM,
        GREEN,
        MAGENTA,
        RESET,
        dry_dep,
        dry_header,
    )

    scaffolder_root = ctx.scaffolder_root
    dry_ctx = DryRunContext(
        name=ctx.name,
        pkg_name=ctx.pkg_name,
        template=template,
        addons=ctx.addons,
        scaffolder_root=scaffolder_root,
        project_dir=ctx.project_dir,
    )

    template_config = load_template_config(scaffolder_root, template)
    selected_addon_configs = [a for a in available if a.id == addon_id]
    contributions = collect_all(template_config, selected_addon_configs)

    render_vars: dict[str, object] = {
        "name": ctx.name,
        "pkg_name": ctx.pkg_name,
        "template": template,
        "secret_key": "",
        "has_postgres": template == "fastapi",
        "has_redis": "redis" in ctx.addons,
    }

    apply_contributions(
        dry_ctx,
        contributions,
        template_config.extension_points,
        render_vars,
    )

    print(
        f"\n  {BOLD}{MAGENTA}Dry run:{RESET} zenit add {addon_id}"
        f"  {DIM}(nothing will be written){RESET}\n"
    )

    dry_header("Files that would be created or modified")
    for action, path, details in dry_ctx.recorded_files:
        if action in ("create", "copy"):
            print(f"  {GREEN}+{RESET} {path}")
        elif action == "append":
            print(f"  {GREEN}+{RESET} {path}  {DIM}(appended){RESET}")
        elif action == "modify":
            print(f"  {GREEN}△{RESET} {path}  {DIM}{details}{RESET}")

    if contributions.deps or contributions.dev_deps:
        dry_header("Dependencies that would be added to pyproject.toml")
        for dep in contributions.deps:
            dry_dep(dep)
        for dep in contributions.dev_deps:
            dry_dep(dep, "dev")

    if contributions.just_recipes:
        dry_header("Just recipes that would be added")
        recipe_render_vars: dict[str, object] = {
            "name": ctx.name,
            "pkg_name": ctx.pkg_name,
            "template": template,
            "addons": ctx.addons,
        }
        string_env = make_env()
        for recipe in contributions.just_recipes:
            rendered = string_env.from_string(recipe).render(**recipe_render_vars)
            name = _recipe_name(rendered)
            if name:
                dry_dep(name)

    print()


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
    from scaffolder.config import config_path, load_config
    from scaffolder.ui import BOLD, CYAN, DIM, GREEN, RESET

    path = config_path()
    cfg = load_config()

    print(f"\n  {BOLD}Config file:{RESET}  {CYAN}{path}{RESET}")
    if path.exists():
        print(f"  {GREEN}✓{RESET}  {DIM}file exists{RESET}")
    else:
        print(f"  {DIM}file does not exist — using built-in defaults{RESET}")

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
    _add(addon, dry_run=dry_run)


def main() -> None:
    if len(sys.argv) == 1 or (
        len(sys.argv) > 1
        and sys.argv[1]
        not in {"list-templates", "list-addons", "config", "add", "--version", "--help"}
        and not sys.argv[1].startswith("-")
    ):
        import argparse

        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("name", nargs="?", default=None)
        parser.add_argument("--dry-run", action="store_true")
        args, _ = parser.parse_known_args()

        if args.name is not None:
            _scaffold(args.name, dry_run=args.dry_run)
        else:
            app()
    else:
        app()


def _print_commands_from_just(project_dir: Path) -> None:
    import subprocess

    if not shutil.which("just"):
        return
    print()
    subprocess.run(["just", "--list"], cwd=project_dir)
