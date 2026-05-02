import shutil
import subprocess

from scaffolder.context import Context
from scaffolder.ui import step, success


def apply(ctx: Context) -> None:
    step("Copying common files")
    common = ctx.scaffolder_root / "templates" / "_common"

    shutil.copy(common / "gitignore", ".gitignore")
    shutil.copy(common / "pre-commit-config.yaml", ".pre-commit-config.yaml")
    shutil.copy(common / "envrc", ".envrc")

    subprocess.run(["direnv", "allow"], check=True, capture_output=True)
    success(".gitignore, .pre-commit-config.yaml, .envrc")
