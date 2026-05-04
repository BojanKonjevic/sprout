from scaffolder.context import Context
from scaffolder.ui import step, success


def apply(ctx: Context) -> None:
    step("Copying common files")
    common = ctx.scaffolder_root / "templates" / "_common"

    ctx.copy_file(common / "gitignore", ".gitignore")
    ctx.copy_file(common / "pre-commit-config.yaml", ".pre-commit-config.yaml")
    ctx.copy_file(common / "envrc", ".envrc")

    ctx.execute_command(["direnv", "allow"])
    success(".gitignore, .pre-commit-config.yaml, .envrc")
