import shutil
import sys

from scaffolder.context import Context
from scaffolder.ui import step, success, warn


def apply(ctx: Context) -> None:
    step("Copying common files")
    common = ctx.scaffolder_root / "templates" / "_common"

    ctx.copy_file(common / "gitignore", ".gitignore")
    ctx.copy_file(common / "gitattributes", ".gitattributes")
    ctx.copy_file(common / "pre-commit-config.yaml", ".pre-commit-config.yaml")

    if sys.platform != "win32":
        ctx.copy_file(common / "envrc", ".envrc")
        if shutil.which("direnv"):
            ctx.execute_command(["direnv", "allow"])
        else:
            warn(
                "direnv not found — .envrc copied but not activated. "
                "Run 'direnv allow' after installing direnv, or just use 'just <cmd>' directly."
            )

    success(
        ".gitignore, .gitattributes, .pre-commit-config.yaml"
        + (", .envrc" if sys.platform != "win32" else "")
    )
