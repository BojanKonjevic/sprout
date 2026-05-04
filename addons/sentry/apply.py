from __future__ import annotations

from pathlib import Path

from scaffolder.context import Context
from scaffolder.render import make_env
from scaffolder.ui import success, warn

_HERE = Path(__file__).parent


def apply(ctx: Context) -> None:
    env = make_env(_HERE / "files")
    render_vars = dict(name=ctx.name, pkg_name=ctx.pkg_name, template=ctx.template)

    integrations_rel = f"src/{ctx.pkg_name}/integrations"
    ctx.create_dir(integrations_rel)
    ctx.write_file(f"{integrations_rel}/__init__.py", "")
    ctx.write_file(
        f"{integrations_rel}/sentry.py",
        env.get_template("sentry.py.j2").render(**render_vars),
    )

    if ctx.template == "fastapi":
        _patch_fastapi_lifecycle(ctx)
        _patch_settings(ctx)
        _patch_env(ctx, ".env")
        _patch_env(ctx, ".env.example")
        success("integrations/sentry.py, lifecycle.py patched, settings.py patched, .env updated")
    else:
        _patch_blank_main(ctx)
        if not ctx.dry_run and Path(".env").exists():
            _patch_env(ctx, ".env")
        else:
            ctx.write_file(".env", "SENTRY_DSN=\nSENTRY_ENVIRONMENT=development\n")
        success("integrations/sentry.py, main.py patched")


def _patch_fastapi_lifecycle(ctx: Context) -> None:
    lifecycle_rel = f"src/{ctx.pkg_name}/lifecycle.py"
    if ctx.dry_run:
        ctx.record_modification(lifecycle_rel, "add init_sentry() call")
        return
    lifecycle_path = Path(lifecycle_rel)
    if not lifecycle_path.exists():
        return
    text = lifecycle_path.read_text()
    if "sentry" in text:
        return
    IMPORT_ANCHOR = "from .db.session import engine"
    YIELD_ANCHOR = "    yield\n    await engine.dispose()"
    if IMPORT_ANCHOR not in text or YIELD_ANCHOR not in text:
        warn(
            "sentry: could not patch lifecycle.py — expected anchors not found. "
            "Add 'from .integrations.sentry import init_sentry' and call "
            "init_sentry() before yield manually."
        )
        return
    text = text.replace(
        IMPORT_ANCHOR,
        f"{IMPORT_ANCHOR}\nfrom .integrations.sentry import init_sentry",
        1,
    )
    text = text.replace(
        YIELD_ANCHOR,
        "    init_sentry()\n    yield\n    await engine.dispose()",
        1,
    )
    lifecycle_path.write_text(text)


def _patch_blank_main(ctx: Context) -> None:
    main_rel = f"src/{ctx.pkg_name}/main.py"
    if ctx.dry_run:
        ctx.record_modification(main_rel, "add sentry init")
        return
    main_path = Path(main_rel)
    if not main_path.exists():
        return
    text = main_path.read_text()
    if "sentry" in text:
        return
    text = text.replace(
        "def main()",
        "from .integrations.sentry import init_sentry\n\n\ndef main()",
        1,
    )
    text = text.replace(
        "def main() -> None:\n    ",
        "def main() -> None:\n    init_sentry()\n    ",
        1,
    )
    main_path.write_text(text)


def _patch_settings(ctx: Context) -> None:
    settings_rel = f"src/{ctx.pkg_name}/settings.py"
    if ctx.dry_run:
        ctx.record_modification(settings_rel, "add sentry_dsn and sentry_environment settings")
        return
    settings_path = Path(settings_rel)
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


def _patch_env(ctx: Context, env_path_str: str) -> None:
    if ctx.dry_run:
        ctx.record_modification(env_path_str, "add SENTRY_DSN and SENTRY_ENVIRONMENT")
        return
    env_path = Path(env_path_str)
    if not env_path.exists():
        return
    text = env_path.read_text()
    if "SENTRY_DSN" in text:
        return
    text = text.rstrip() + "\nSENTRY_DSN=\nSENTRY_ENVIRONMENT=development\n"
    env_path.write_text(text)


def extra_deps() -> list[str]:
    return ["sentry-sdk[fastapi]"]


def extra_just_recipes(ctx: Context) -> str:
    return """\
sentry-test:
    python -c "from (( pkg_name )).integrations.sentry import init_sentry; import os; init_sentry(); print('Sentry DSN:', os.environ.get('SENTRY_DSN') or 'not set')" # noqa: E501
sentry-check:
    python -c "import sentry_sdk; print('sentry-sdk', sentry_sdk.VERSION)"
"""
