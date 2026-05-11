"""Add‑on pipeline — apply a single addon to an existing project."""

import sys
from pathlib import Path

import typer

from scaffolder.context import Context
from scaffolder.rollback import addon_or_rollback
from scaffolder.schema import AddonConfig
from scaffolder.ui import (
    BOLD,
    CYAN,
    DIM,
    GREEN,
    RESET,
    YELLOW,
    info,
    success,
    warn,
)


def add_addon(addon_id: str, dry_run: bool = False) -> None:
    """Apply a single addon to an existing zenit project."""
    import os

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
        raise typer.Exit(1) from exc

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
            raise typer.Exit(0) from None
        if raw not in ("", "y", "yes"):
            print(f"\n  {YELLOW}Aborted.{RESET}\n")
            raise typer.Exit(0)
    else:
        warn("Non‑interactive mode — proceeding automatically.")

    with addon_or_rollback(project_dir, addon_id):
        from scaffolder.apply import apply_contributions
        from scaffolder.collect import collect_addon_only
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

        contributions = collect_addon_only(selected_addon_configs)

        apply_contributions(
            ctx,
            contributions,
            template_config.extension_points,
            render_vars,
        )

        from scaffolder.deps import inject_deps

        try:
            added_deps, added_dev_deps = inject_deps(
                project_dir,
                contributions.deps,
                contributions.dev_deps,
            )
        except FileNotFoundError as exc:
            warn(str(exc))
            added_deps, added_dev_deps = [], []

        from scaffolder.justfile import inject_just_recipes
        from scaffolder.render import make_env

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

        new_addons = lockfile.addons + [addon_id]
        write_lockfile(project_dir, template, new_addons)

    # ── output ────────────────────────────────────────────────────────────
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
    available: list[AddonConfig],
    template: str,
) -> None:
    """Print what `zenit add` would do without writing anything."""
    from scaffolder.apply import apply_contributions
    from scaffolder.collect import collect_addon_only
    from scaffolder.dryrun import DryRunContext
    from scaffolder.generate import _recipe_name
    from scaffolder.render import make_env
    from scaffolder.templates._load_config import load_template_config
    from scaffolder.ui import BOLD, DIM, GREEN, MAGENTA, RESET, dry_dep, dry_header

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
    contributions = collect_addon_only(selected_addon_configs)

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
