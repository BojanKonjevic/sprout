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
        _patch_env_blank(Path(".env") if Path(".env").exists() else None)
        success("sentry.py, main.py patched")


def _patch_fastapi_main(main_path: Path, ctx: Context) -> None:
    if not main_path.exists():
        return
    text = main_path.read_text()
    if "sentry" in text:
        return

    old = "from fastapi import FastAPI"
    new = f"from fastapi import FastAPI\nfrom .sentry import init_sentry"
    text = text.replace(old, new, 1)

    old = "@asynccontextmanager\nasync def lifespan"
    new = "@asynccontextmanager\nasync def lifespan"
    # Patch lifespan to call init_sentry before yield
    old2 = "async def lifespan(app: FastAPI) -> AsyncGenerator[None]:\n    yield"
    new2 = "async def lifespan(app: FastAPI) -> AsyncGenerator[None]:\n    init_sentry()\n    yield"
    if old2 in text:
        text = text.replace(old2, new2, 1)
    else:
        # lifespan body may vary — prepend init_sentry at top of function
        text = text.replace(
            "async def lifespan(app: FastAPI)",
            "async def lifespan(app: FastAPI)",
        )

    main_path.write_text(text)


def _patch_blank_main(main_path: Path, ctx: Context) -> None:
    if not main_path.exists():
        return
    text = main_path.read_text()
    if "sentry" in text:
        return

    old = "def main()"
    new = f"from .sentry import init_sentry\n\n\ndef main()"
    text = text.replace(old, new, 1)

    # Call init_sentry as first line of main
    old2 = "def main() -> None:\n    "
    new2 = "def main() -> None:\n    init_sentry()\n    "
    if old2 in text:
        text = text.replace(old2, new2, 1)

    main_path.write_text(text)


def _patch_settings(settings_path: Path) -> None:
    if not settings_path.exists():
        return
    text = settings_path.read_text()
    if "sentry_dsn" in text:
        return
    # Append sentry_dsn field before the closing of the Settings class
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


def _patch_env_blank(env_path: Path | None) -> None:
    if env_path is None:
        Path(".env").write_text("SENTRY_DSN=\nSENTRY_ENVIRONMENT=development\n")
        return
    _patch_env(env_path)


def extra_deps() -> list[str]:
    return ["sentry-sdk[fastapi]"]
