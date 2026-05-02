import importlib.util
import os
import sys
from pathlib import Path
from typing import Callable

from scaffolder.context import Context
from scaffolder.dryrun import run_dry
from scaffolder.generate import generate_all
from scaffolder.git import init_and_commit
from scaffolder.nix import lock_flake
from scaffolder.rollback import scaffold_or_rollback
from scaffolder.prompt import prompt_template, prompt_addons
from scaffolder.ui import error, info, step, success
from scaffolder.validate import validate_name, check_preflight


def _load_apply(path: Path) -> Callable:
    spec = importlib.util.spec_from_file_location("apply", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.apply  # type: ignore[no-any-return]


def _load_addon_registry(scaffolder_root: Path) -> list[tuple[str, str]]:
    registry_path = scaffolder_root / "addons" / "_registry.py"
    spec = importlib.util.spec_from_file_location("_registry", registry_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.ADDONS  # type: ignore[no-any-return]


def _parse_args() -> tuple[str, bool]:
    """Returns (project_name, dry_run)."""
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry_run = "--dry-run" in sys.argv[1:]

    if not args:
        error("Usage: new-python-project <project-name> [--dry-run]")
        sys.exit(1)

    return args[0], dry_run


def main() -> None:
    name, dry_run = _parse_args()
    pkg_name = name.replace("-", "_")
    scaffolder_root = Path(
        os.environ.get("SCAFFOLDER_ROOT", Path(__file__).parent.parent.parent)
    )

    validate_name(name, pkg_name)

    # Skip heavy tool checks in dry-run — the point is to preview without
    # requiring the full environment to be set up.
    if not dry_run:
        check_preflight()

    template = prompt_template()
    available_addons = _load_addon_registry(scaffolder_root)
    addons = prompt_addons(available_addons)

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

    addon_label = f"  addons: {', '.join(addons)}" if addons else "  no addons"
    step(f"Creating '{name}'  (template: {template})\n{addon_label}")

    project_dir = ctx.project_dir
    project_dir.mkdir()
    os.chdir(project_dir)

    with scaffold_or_rollback(project_dir):
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
        lock_flake()
        init_and_commit(project_dir)

    print()
    success(
        f"Project '{name}' ready!  ({template}{' + ' + ', '.join(addons) if addons else ''})"
    )
    print()
    print(f"  cd {name}")

    if template == "fastapi":
        print()
        info("When you're ready to add auth:")
        print(f"    1. Define User + RefreshToken in models.py")
        print(f"    2. Add src/{pkg_name}/dependencies.py  (get_current_user)")
        print(f"    3. Add src/{pkg_name}/routes/auth.py")
        print(f"    4. Activate the client fixture in tests/conftest.py")
        print(f"    5. just migrate 'add users' && just upgrade")

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
        print(
            "    Push to GitHub and it will lint, type-check, and test automatically."
        )
