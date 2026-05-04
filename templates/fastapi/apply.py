import shutil
import stat
from pathlib import Path

import jinja2

from scaffolder.context import Context
from scaffolder.ui import step, success, error
from scaffolder.exceptions import ScaffoldError


def _copy(src: Path, dest: Path) -> None:
    """Copy a file and ensure it is user-writable regardless of source permissions."""
    shutil.copy(src, dest)
    dest.chmod(dest.stat().st_mode | stat.S_IWRITE | stat.S_IREAD)


def _render(src: Path, dest: Path, ctx: Context) -> None:
    """Render a Jinja2 template with (( )) delimiters."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(src.parent)),
        keep_trailing_newline=True,
        variable_start_string="((",
        variable_end_string="))",
        block_start_string="[%",
        block_end_string="%]",
    )
    dest.write_text(
        env.get_template(src.name).render(
            name=ctx.name,
            pkg_name=ctx.pkg_name,
        )
    )


def apply(ctx: Context) -> None:
    if "docker" not in ctx.addons:
        raise ScaffoldError(
            "The fastapi template requires the docker addon. Please re-run and select docker."
        )

    step("Applying fastapi template")
    files = ctx.scaffolder_root / "templates" / "fastapi" / "files"
    pkg = Path("src") / ctx.pkg_name

    # ── Directory structure ──────────────────────────────────────────────────
    for d in [
        pkg / "api" / "routes",
        pkg / "core",
        pkg / "db",
        pkg / "models",
        pkg / "schemas",
    ]:
        d.mkdir(parents=True)

    (Path("tests") / "fixtures").mkdir(parents=True)
    (Path("tests") / "unit").mkdir(parents=True)
    (Path("tests") / "integration").mkdir(parents=True)
    (Path("alembic") / "versions").mkdir(parents=True)

    # ── Package __init__.py files ─────────────────────────────────────────────
    (pkg / "__init__.py").write_text(f'"""{ctx.name}"""\n\n__version__ = "0.1.0"\n')
    for subpkg in ["api", "api/routes", "core", "db", "models", "schemas"]:
        (pkg / subpkg / "__init__.py").touch()

    (pkg / "models" / "__init__.py").write_text(
        "# Import all models here so Alembic can discover them.\n"
        "# Example:\n"
        "#   from .user import User\n"
    )

    # ── Verbatim copies ───────────────────────────────────────────────────────
    verbatim = [
        # Top-level
        (files / "lifecycle.py", pkg / "lifecycle.py"),
        (files / "exceptions.py", pkg / "exceptions.py"),
        # api/
        (files / "api" / "router.py", pkg / "api" / "router.py"),
        (files / "api" / "routes" / "health.py", pkg / "api" / "routes" / "health.py"),
        # core/
        (files / "core" / "security.py", pkg / "core" / "security.py"),
        # db/
        (files / "db" / "base.py", pkg / "db" / "base.py"),
        (files / "db" / "session.py", pkg / "db" / "session.py"),
        # models/
        (files / "models" / "mixins.py", pkg / "models" / "mixins.py"),
        # schemas/
        (files / "schemas" / "common.py", pkg / "schemas" / "common.py"),
        # alembic
        (files / "alembic" / "script.py.mako", Path("alembic") / "script.py.mako"),
        # tests
        (
            files / "tests" / "test_health.py",
            Path("tests") / "integration" / "test_health.py",
        ),
        # env
        (files / ".env.example", Path(".env.example")),
    ]
    for src_file, dest in verbatim:
        _copy(src_file, dest)

    # ── Rendered templates ────────────────────────────────────────────────────
    _render(files / "main.py.j2", pkg / "main.py", ctx)
    _render(files / "settings.py.j2", pkg / "settings.py", ctx)
    _render(files / "alembic.ini.j2", Path("alembic.ini"), ctx)
    _render(files / "alembic" / "env.py.j2", Path("alembic") / "env.py", ctx)
    _render(files / "tests" / "conftest.py.j2", Path("tests") / "conftest.py", ctx)
    _render(files / ".env.j2", Path(".env"), ctx)

    success("src/, tests/, alembic/")
