"""Sentry addon — error tracking and performance monitoring."""

from __future__ import annotations

from pathlib import Path

import jinja2

from scaffolder.context import Context
from scaffolder.ui import success

_HERE = Path(__file__).parent


def apply(ctx: Context) -> None:
    files = _HERE / "files"

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(files)),
        keep_trailing_newline=True,
        variable_start_string="((",
        variable_end_string="))",
        block_start_string="[%",
        block_end_string="%]",
    )

    render_vars = dict(name=ctx.name, pkg_name=ctx.pkg_name, template=ctx.template)

    pkg_dir = Path("src") / ctx.pkg_name
    pkg_dir.mkdir(parents=True, exist_ok=True)

    (pkg_dir / "sentry.py").write_text(
        env.get_template("sentry.py.j2").render(**render_vars)
    )

    if ctx.template == "fastapi":
        _patch_fastapi_main(Path("src") / ctx.pkg_name / "main.py", ctx)
        _patch_settings(Path("src") / ctx.pkg_name / "settings.py")
        _patch_env(Path(".env"))
        _patch_env(Path(".env.example"))
        success("sentry.py, main.py patched, settings.py patched, .env updated")
    else:
        _patch_blank_main(Path("src") / ctx.pkg_name / "main.py", ctx)
        _patch_env(Path(".env")) if Path(".env").exists() else Path(".env").write_text(
            "SENTRY_DSN=\nSENTRY_ENVIRONMENT=development\n"
        )
        success("sentry.py, main.py patched")


def _patch_fastapi_main(main_path: Path, ctx: Context) -> None:
    if not main_path.exists():
        return
    text = main_path.read_text()
    if "sentry" in text:
        return

    text = text.replace(
        "from fastapi import FastAPI",
        "from fastapi import FastAPI\nfrom .sentry import init_sentry",
        1,
    )
    text = text.replace(
        "async def lifespan(app: FastAPI) -> AsyncGenerator[None]:\n    yield",
        "async def lifespan(app: FastAPI) -> AsyncGenerator[None]:\n    init_sentry()\n    yield",
        1,
    )
    main_path.write_text(text)


def _patch_blank_main(main_path: Path, ctx: Context) -> None:
    if not main_path.exists():
        return
    text = main_path.read_text()
    if "sentry" in text:
        return

    text = text.replace(
        "def main()",
        "from .sentry import init_sentry\n\n\ndef main()",
        1,
    )
    text = text.replace(
        "def main() -> None:\n    ",
        "def main() -> None:\n    init_sentry()\n    ",
        1,
    )
    main_path.write_text(text)


def _patch_settings(settings_path: Path) -> None:
    if not settings_path.exists():
        return
    text = settings_path.read_text()
    if "sentry_dsn" in text:
        return
    old = "    access_token_expire_minutes: int = 30\n    refresh_token_expire_days: int = 30"
    new = (
        "    access_token_expire_minutes: int = 30\n"
        "    refresh_token_expire_days: int = 30\n"
        '    sentry_dsn: str = ""\n'
        '    sentry_environment: str = "development"'
    )
    if old in text:
        text = text.replace(old, new, 1)
    else:
        text = (
            text.rstrip()
            + '\n    sentry_dsn: str = ""\n    sentry_environment: str = "development"\n'
        )
    settings_path.write_text(text)


def _patch_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    text = env_path.read_text()
    if "SENTRY_DSN" in text:
        return
    text = text.rstrip() + "\nSENTRY_DSN=\nSENTRY_ENVIRONMENT=development\n"
    env_path.write_text(text)


def extra_deps() -> list[str]:
    return ["sentry-sdk[fastapi]"]


def extra_just_recipes() -> str:
    return """\
sentry-test:
    python -c "from (( pkg_name )).sentry import init_sentry; import os; os.environ['SENTRY_DSN'] = os.environ.get('SENTRY_DSN', ''); init_sentry(); print('Sentry DSN:', os.environ.get('SENTRY_DSN') or 'not set')"
sentry-check:
    python -c "import sentry_sdk; print(sentry_sdk.VERSION)"
"""
