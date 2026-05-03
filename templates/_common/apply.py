import shutil
import stat
import subprocess
from pathlib import Path

from scaffolder.context import Context
from scaffolder.ui import step, success


def _copy(src: Path, dest: Path) -> None:
    """Copy a file and ensure it is user-writable regardless of source permissions."""
    shutil.copy(src, dest)
    dest.chmod(dest.stat().st_mode | stat.S_IWRITE | stat.S_IREAD)


def apply(ctx: Context) -> None:
    step("Copying common files")
    common = ctx.scaffolder_root / "templates" / "_common"

    _copy(common / "gitignore", Path(".gitignore"))
    _copy(common / "pre-commit-config.yaml", Path(".pre-commit-config.yaml"))
    _copy(common / "envrc", Path(".envrc"))

    subprocess.run(["direnv", "allow"], check=True, capture_output=True)
    success(".gitignore, .pre-commit-config.yaml, .envrc")
