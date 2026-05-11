"""Project scaffold pipeline — called by the CLI layer."""

import secrets
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import typer

from scaffolder._paths import get_scaffolder_root
from scaffolder.config import load_config
from scaffolder.context import Context
from scaffolder.generate import generate_all
from scaffolder.git import init_and_commit
from scaffolder.prompt import prompt_addons, prompt_template
from scaffolder.rollback import scaffold_or_rollback
from scaffolder.ui import confirm, info, print_commands_from_just, success


def _load_apply(path: Path) -> Callable[[Context], None]:
    """Import and return the ``apply()`` function from an ``apply.py`` file."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("apply", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.apply  # type: ignore[no-any-return]


def scaffold_project(name: str, dry_run: bool = False) -> None:
    """Core scaffold pipeline — called by the main CLI command."""

    scaffolder_root = get_scaffolder_root()
    pkg_name = name.replace("-", "_")

    from scaffolder.validate import (
        check_preflight,
        validate_addon_deps,
        validate_name,
    )

    validate_name(name, pkg_name)

    if not dry_run:
        check_preflight()

    cfg = load_config()

    template = prompt_template(default=cfg.default_template)

    from scaffolder.addons._registry import get_available_addons

    available = get_available_addons()
    addons = prompt_addons(available, template, default_addons=cfg.default_addons)
    validate_addon_deps(addons, available, template=template)

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

        from scaffolder.apply import apply_contributions
        from scaffolder.collect import collect_all
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
        init_and_commit(project_dir)

        from scaffolder.lockfile import write_lockfile

        write_lockfile(project_dir, template, addons)

    print()
    addon_suffix = (" + " + ", ".join(addons)) if addons else ""
    success(f"Project '{name}' ready!  ({template}{addon_suffix})")
    print()
    print(f"  cd {name}")

    print_commands_from_just(project_dir)

    if sys.platform == "win32":
        print()
        info("Your environment is managed by uv — no activation needed.")
        info("Every 'just' command runs through 'uv run' and syncs automatically.")
    elif not shutil.which("direnv"):
        print()
        info("direnv not detected — run 'uv sync' once to set up your environment,")
        info("or install direnv and run 'direnv allow' for auto‑activation on cd.")

    if "github-actions" in addons:
        print()
        info("GitHub Actions CI is set up at .github/workflows/ci.yml")
        print(
            "    Push to GitHub and it will lint, type‑check, and test automatically."
        )
