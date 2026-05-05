import secrets

from scaffolder.context import Context
from scaffolder.exceptions import ScaffoldError
from scaffolder.render import make_env
from scaffolder.ui import step, success


def apply(ctx: Context) -> None:
    if "docker" not in ctx.addons:
        raise ScaffoldError(
            "The fastapi template requires the docker addon. Please re-run and select docker."
        )

    step("Applying fastapi template")
    files = ctx.scaffolder_root / "templates" / "fastapi" / "files"
    pkg_rel = f"src/{ctx.pkg_name}"

    for d in [
        f"{pkg_rel}/api/routes",
        f"{pkg_rel}/core",
        f"{pkg_rel}/db",
        f"{pkg_rel}/models",
        f"{pkg_rel}/schemas",
        "tests/fixtures",
        "tests/unit",
        "tests/integration",
        "alembic/versions",
        "scripts",
    ]:
        ctx.create_dir(d)

    ctx.write_file(f"{pkg_rel}/__init__.py", f'"""{ctx.name}"""\n\n__version__ = "0.1.0"\n')
    for subpkg in ["api", "api/routes", "core", "db", "schemas"]:
        ctx.write_file(f"{pkg_rel}/{subpkg}/__init__.py", "")

    ctx.write_file(
        f"{pkg_rel}/models/__init__.py",
        "# Import all models here so Alembic can discover them.\n"
        "# Example:\n"
        "#   from .user import User\n",
    )

    verbatim = [
        ("lifecycle.py", f"{pkg_rel}/lifecycle.py"),
        ("exceptions.py", f"{pkg_rel}/exceptions.py"),
        ("api/router.py", f"{pkg_rel}/api/router.py"),
        ("api/routes/health.py", f"{pkg_rel}/api/routes/health.py"),
        ("core/security.py", f"{pkg_rel}/core/security.py"),
        ("db/base.py", f"{pkg_rel}/db/base.py"),
        ("db/session.py", f"{pkg_rel}/db/session.py"),
        ("models/mixins.py", f"{pkg_rel}/models/mixins.py"),
        ("schemas/common.py", f"{pkg_rel}/schemas/common.py"),
        ("alembic/script.py.mako", "alembic/script.py.mako"),
        ("tests/test_health.py", "tests/integration/test_health.py"),
        (".env.example", ".env.example"),
        ("scripts/wait_db.py", "scripts/wait_db.py"),
    ]
    for src_name, dest_rel in verbatim:
        ctx.copy_file(files / src_name, dest_rel)

    env = make_env(files)

    def _render(src_name: str, dest_rel: str, **extra_vars: object) -> None:
        content = env.get_template(src_name).render(
            name=ctx.name, pkg_name=ctx.pkg_name, **extra_vars
        )
        ctx.write_file(dest_rel, content)

    _render("main.py.j2", f"{pkg_rel}/main.py")
    _render("settings.py.j2", f"{pkg_rel}/settings.py")
    _render("alembic.ini.j2", "alembic.ini")
    _render("alembic/env.py.j2", "alembic/env.py")
    _render("tests/conftest.py.j2", "tests/conftest.py")

    secret_key = secrets.token_hex(32)
    _render(".env.j2", ".env", secret_key=secret_key)

    success("src/, tests/, alembic/, scripts/")
