from scaffolder.context import Context
from scaffolder.render import make_env
from scaffolder.ui import step, success


def apply(ctx: Context) -> None:
    step("Applying blank template")
    files = ctx.scaffolder_root / "templates" / "blank" / "files"
    pkg_rel = f"src/{ctx.pkg_name}"

    ctx.create_dir(pkg_rel)
    ctx.create_dir("tests")

    ctx.write_file(f"{pkg_rel}/__init__.py", f'"""{ctx.name}"""\n\n__version__ = "0.1.0"\n')

    env = make_env(files)
    ctx.write_file(
        f"{pkg_rel}/main.py",
        env.get_template("main.py.j2").render(name=ctx.name, pkg_name=ctx.pkg_name),
    )

    ctx.copy_file(files / "__main__.py", f"{pkg_rel}/__main__.py")

    ctx.write_file(
        "tests/test_main.py",
        env.get_template("tests/test_main.py.j2").render(name=ctx.name, pkg_name=ctx.pkg_name),
    )

    success("src/, tests/")
