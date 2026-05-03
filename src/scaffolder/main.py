import importlib.util
import os
import sys
from collections.abc import Callable
from pathlib import Path

from scaffolder.context import Context
from scaffolder.dryrun import run_dry
from scaffolder.generate import generate_all
from scaffolder.git import init_and_commit
from scaffolder.nix import lock_flake, warm_devshell
from scaffolder.prompt import TEMPLATES, prompt_addons, prompt_template
from scaffolder.rollback import scaffold_or_rollback
from scaffolder.ui import confirm, error, info, step, success
from scaffolder.validate import check_preflight, validate_name

USAGE = """\
Usage:
  sprout <project-name> [--dry-run]
  sprout --list-templates
  sprout --list-addons
"""


def _load_apply(path: Path) -> Callable[[Context], None]:
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


def _parse_args() -> tuple[str | None, bool, bool, bool]:
    """Returns (project_name, dry_run, list_templates, list_addons)."""
    argv = sys.argv[1:]
    dry_run = "--dry-run" in argv
    list_templates = "--list-templates" in argv
    list_addons = "--list-addons" in argv

    positional = [a for a in argv if not a.startswith("--")]
    name = positional[0] if positional else None

    return name, dry_run, list_templates, list_addons


def _cmd_list_templates() -> None:
    from scaffolder.ui import CYAN, DIM, RESET

    print()
    for name, desc in TEMPLATES:
        print(f"  {CYAN}{name:<12}{RESET}  {DIM}{desc}{RESET}")
    print()


def _cmd_list_addons(scaffolder_root: Path) -> None:
    from scaffolder.ui import CYAN, DIM, RESET

    addons = _load_addon_registry(scaffolder_root)
    print()
    for addon_id, desc in addons:
        print(f"  {CYAN}{addon_id:<20}{RESET}  {DIM}{desc}{RESET}")
    print()


def main() -> None:
    name, dry_run, list_templates, list_addons = _parse_args()

    scaffolder_root = Path(os.environ.get("SCAFFOLDER_ROOT", Path(__file__).parent.parent.parent))

    if list_templates:
        _cmd_list_templates()
        return

    if list_addons:
        _cmd_list_addons(scaffolder_root)
        return

    if not name:
        print(USAGE)
        sys.exit(1)

    pkg_name = name.replace("-", "_")

    validate_name(name, pkg_name)

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

    if not confirm(ctx):
        print("\n  \033[0;33mAborted.\033[0m\n")
        sys.exit(0)

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
        warm_devshell()
        init_and_commit(project_dir)

    print()
    success(f"Project '{name}' ready!  ({template}{' + ' + ', '.join(addons) if addons else ''})")
    print()
    print(f"  cd {name}")

    if template == "fastapi":
        print()
        info("When you're ready to add auth:")
        print("    1. Define User + RefreshToken in models/")
        print(f"    2. Add src/{pkg_name}/core/dependencies.py  (get_current_user)")
        print(f"    3. Add src/{pkg_name}/api/routes/auth.py")
        print(f"    4. Register it in src/{pkg_name}/api/router.py")
        print("    5. Activate the client fixture in tests/conftest.py")
        print("    6. just migrate 'add users' && just upgrade")

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
