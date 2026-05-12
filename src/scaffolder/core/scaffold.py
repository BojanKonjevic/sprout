"""Project scaffold pipeline — called by the CLI layer."""

import secrets
import shutil
import sys
from pathlib import Path

import typer

from scaffolder.addons._registry import get_available_addons
from scaffolder.cli.prompt import prompt_addons, prompt_template
from scaffolder.cli.ui import confirm, info, print_commands_from_just, success
from scaffolder.config.config import load_config
from scaffolder.core._apply_loader import load_apply
from scaffolder.core._paths import get_scaffolder_root
from scaffolder.core.apply import apply_contributions
from scaffolder.core.collect import collect_all
from scaffolder.core.context import Context
from scaffolder.core.dryrun import run_dry
from scaffolder.core.generate import generate_all
from scaffolder.core.git import init
from scaffolder.core.lockfile import write_lockfile
from scaffolder.core.rollback import scaffold_or_rollback
from scaffolder.core.validate import (
    check_preflight,
    validate_addon_deps,
    validate_name,
)
from scaffolder.templates._load_config import load_template_config


def scaffold_project(name: str, dry_run: bool = False) -> None:
    """Core scaffold pipeline — called by the main CLI command."""

    scaffolder_root = get_scaffolder_root()
    pkg_name = name.replace("-", "_")

    validate_name(name, pkg_name)

    if not dry_run:
        check_preflight()

    cfg = load_config()

    template = prompt_template(default=cfg.default_template)

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
        run_dry(ctx)
        return

    if not confirm(ctx):
        print("\n  \033[0;33mAborted.\033[0m\n")
        raise typer.Exit(0)

    project_dir = ctx.project_dir
    with scaffold_or_rollback(project_dir):
        project_dir.mkdir()

        load_apply(scaffolder_root / "templates" / "_common" / "apply.py")(ctx)

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
        init(project_dir)

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
