import importlib.util
import os
import sys
from pathlib import Path
from typing import Callable

from scaffolder.context import Context
from scaffolder.generate import generate_all
from scaffolder.git import init_and_commit
from scaffolder.nix import lock_flake
from scaffolder.rollback import scaffold_or_rollback
from scaffolder.prompt import prompt_template
from scaffolder.ui import error, info, step, success
from scaffolder.validate import validate_name, check_preflight


def _load_apply(path: Path) -> Callable:
    spec = importlib.util.spec_from_file_location("apply", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.apply  # type: ignore[no-any-return]


def main() -> None:
    if len(sys.argv) < 2:
        error("Usage: new-python-project <project-name>")
        sys.exit(1)

    name = sys.argv[1]
    pkg_name = name.replace("-", "_")
    scaffolder_root = Path(
        os.environ.get("SCAFFOLDER_ROOT", Path(__file__).parent.parent.parent)
    )

    # All checks before we touch the filesystem
    validate_name(name, pkg_name)
    check_preflight()

    template = prompt_template()

    step(f"Creating '{name}'  (template: {template})")

    project_dir = Path.cwd() / name
    project_dir.mkdir()
    os.chdir(project_dir)

    ctx = Context(
        name=name,
        pkg_name=pkg_name,
        template=template,
        scaffolder_root=scaffolder_root,
        project_dir=project_dir,
    )

    with scaffold_or_rollback(project_dir):
        _load_apply(scaffolder_root / "templates" / "_common" / "apply.py")(ctx)
        _load_apply(scaffolder_root / "templates" / template / "apply.py")(ctx)
        generate_all(ctx)
        lock_flake()
        init_and_commit(project_dir)

    print()
    success(f"Project '{name}' created!  (template: {template})")
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
