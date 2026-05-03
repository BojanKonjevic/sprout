import shutil
import stat
from pathlib import Path

import jinja2

from scaffolder.context import Context
from scaffolder.ui import step, success


def _copy(src: Path, dest: Path) -> None:
    """Copy a file and ensure it is user-writable regardless of source permissions."""
    shutil.copy(src, dest)
    dest.chmod(dest.stat().st_mode | stat.S_IWRITE | stat.S_IREAD)


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
    step("Applying blank template")
    files = ctx.scaffolder_root / "templates" / "blank" / "files"

    (Path("src") / ctx.pkg_name).mkdir(parents=True)
    Path("tests").mkdir()

    (Path("src") / ctx.pkg_name / "__init__.py").write_text(
        f'"""{ctx.name}"""\n\n__version__ = "0.1.0"\n'
    )

    _render(files / "main.py.j2", Path("src") / ctx.pkg_name / "main.py", ctx)
    _copy(files / "__main__.py", Path("src") / ctx.pkg_name / "__main__.py")
    _render(files / "tests" / "test_main.py.j2", Path("tests") / "test_main.py", ctx)

    success("src/, tests/")
