import shutil
from pathlib import Path

import jinja2

from scaffolder.context import Context
from scaffolder.postgres import create_databases
from scaffolder.ui import step, success


def _render(src: Path, dest: Path, ctx: Context) -> None:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(src.parent)),
        keep_trailing_newline=True,
    )
    dest.write_text(
        env.get_template(src.name).render(
            name=ctx.name,
            pkg_name=ctx.pkg_name,
        )
    )


def apply(ctx: Context) -> None:
    step("Applying fastapi template")
    files = ctx.scaffolder_root / "templates" / "fastapi" / "files"

    create_databases(ctx.name)

    (Path("src") / ctx.pkg_name / "routes").mkdir(parents=True)
    Path("tests").mkdir()
    Path("alembic/versions").mkdir(parents=True)

    (Path("src") / ctx.pkg_name / "__init__.py").write_text(
        f'"""{ctx.name}"""\n\n__version__ = "0.1.0"\n'
    )
    (Path("src") / ctx.pkg_name / "routes" / "__init__.py").touch()

    # Verbatim copies — no substitution needed
    verbatim = [
        (files / "main.py", Path("src") / ctx.pkg_name / "main.py"),
        (files / "database.py", Path("src") / ctx.pkg_name / "database.py"),
        (files / "security.py", Path("src") / ctx.pkg_name / "security.py"),
        (files / "models.py", Path("src") / ctx.pkg_name / "models.py"),
        (files / "alembic" / "script.py.mako", Path("alembic") / "script.py.mako"),
        (files / "tests" / "test_main.py", Path("tests") / "test_main.py"),
        (files / ".env.example", Path(".env.example")),
    ]
    for src_file, dest in verbatim:
        shutil.copy(src_file, dest)

    # Rendered templates — need name/pkg_name substitution
    _render(files / "settings.py.j2", Path("src") / ctx.pkg_name / "settings.py", ctx)
    _render(files / "alembic.ini.j2", Path("alembic.ini"), ctx)
    _render(files / "alembic" / "env.py.j2", Path("alembic") / "env.py", ctx)
    _render(files / "tests" / "conftest.py.j2", Path("tests") / "conftest.py", ctx)
    _render(files / ".env.j2", Path(".env"), ctx)

    success("src/, tests/, alembic/")
