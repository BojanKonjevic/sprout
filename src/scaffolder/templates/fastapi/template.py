from pathlib import Path

from scaffolder.schema import EnvVar, ExtensionPoint, FileContribution, TemplateConfig

_HERE = Path(__file__).parent.absolute()

config = TemplateConfig(
    id="fastapi",
    description="FastAPI + SQLAlchemy + Alembic + asyncpg",
    requires_addons=["docker"],
    extension_points={
        "settings_fields": ExtensionPoint(
            file="src/{{pkg_name}}/settings.py",
            sentinel="    # [jumpstart: settings_fields]",
        ),
        "lifespan_startup": ExtensionPoint(
            file="src/{{pkg_name}}/lifecycle.py",
            sentinel="    # [jumpstart: lifespan_startup]",
        ),
        "lifespan_shutdown": ExtensionPoint(
            file="src/{{pkg_name}}/lifecycle.py",
            sentinel="    # [jumpstart: lifespan_shutdown]",
        ),
        "env_vars": ExtensionPoint(
            file=".env",
            sentinel="# [jumpstart: env_vars]",
        ),
    },
    dirs=[
        "src/{{pkg_name}}/api/routes",
        "src/{{pkg_name}}/core",
        "src/{{pkg_name}}/db",
        "src/{{pkg_name}}/models",
        "src/{{pkg_name}}/schemas",
        "tests/fixtures",
        "tests/unit",
        "tests/integration",
        "alembic/versions",
        "scripts",
    ],
    files=[
        FileContribution(
            dest="src/{{pkg_name}}/__init__.py",
            content='"""(( name ))"""\n\n__version__ = "0.1.0"\n',
            template=True,
        ),
        FileContribution(dest="src/{{pkg_name}}/api/__init__.py", content=""),
        FileContribution(dest="src/{{pkg_name}}/api/routes/__init__.py", content=""),
        FileContribution(dest="src/{{pkg_name}}/core/__init__.py", content=""),
        FileContribution(dest="src/{{pkg_name}}/db/__init__.py", content=""),
        FileContribution(dest="src/{{pkg_name}}/schemas/__init__.py", content=""),
        FileContribution(
            dest="src/{{pkg_name}}/models/__init__.py",
            content="# Import all models here so Alembic can discover them.\n"
            "# Example:\n"
            "#   from .user import User\n",
        ),
        FileContribution(
            dest="src/{{pkg_name}}/main.py",
            source=str(_HERE / "files" / "main.py.j2"),
            template=True,
        ),
        FileContribution(
            dest="src/{{pkg_name}}/lifecycle.py",
            source=str(_HERE / "files" / "lifecycle.py"),
        ),
        FileContribution(
            dest="src/{{pkg_name}}/exceptions.py",
            source=str(_HERE / "files" / "exceptions.py"),
        ),
        FileContribution(
            dest="src/{{pkg_name}}/api/router.py",
            source=str(_HERE / "files" / "api" / "router.py"),
        ),
        FileContribution(
            dest="src/{{pkg_name}}/api/routes/health.py",
            source=str(_HERE / "files" / "api" / "routes" / "health.py"),
        ),
        FileContribution(
            dest="src/{{pkg_name}}/core/security.py",
            source=str(_HERE / "files" / "core" / "security.py"),
        ),
        FileContribution(
            dest="src/{{pkg_name}}/db/base.py",
            source=str(_HERE / "files" / "db" / "base.py"),
        ),
        FileContribution(
            dest="src/{{pkg_name}}/db/session.py",
            source=str(_HERE / "files" / "db" / "session.py"),
        ),
        FileContribution(
            dest="src/{{pkg_name}}/models/mixins.py",
            source=str(_HERE / "files" / "models" / "mixins.py"),
        ),
        FileContribution(
            dest="src/{{pkg_name}}/schemas/common.py",
            source=str(_HERE / "files" / "schemas" / "common.py"),
        ),
        FileContribution(
            dest="src/{{pkg_name}}/settings.py",
            source=str(_HERE / "files" / "settings.py.j2"),
            template=True,
        ),
        FileContribution(
            dest=".env",
            source=str(_HERE / "files" / ".env.j2"),
            template=True,
        ),
        FileContribution(
            dest=".env.example",
            source=str(_HERE / "files" / ".env.example"),
        ),
        FileContribution(
            dest="alembic.ini",
            source=str(_HERE / "files" / "alembic.ini.j2"),
            template=True,
        ),
        FileContribution(
            dest="alembic/env.py",
            source=str(_HERE / "files" / "alembic" / "env.py.j2"),
            template=True,
        ),
        FileContribution(
            dest="alembic/script.py.mako",
            source=str(_HERE / "files" / "alembic" / "script.py.mako"),
        ),
        FileContribution(
            dest="tests/conftest.py",
            source=str(_HERE / "files" / "tests" / "conftest.py.j2"),
            template=True,
        ),
        FileContribution(
            dest="tests/integration/test_health.py",
            source=str(_HERE / "files" / "tests" / "test_health.py"),
        ),
        FileContribution(
            dest="scripts/wait_db.py",
            source=str(_HERE / "files" / "scripts" / "wait_db.py"),
        ),
    ],
    deps=[
        "fastapi",
        "uvicorn[standard]",
        "sqlalchemy[asyncio]",
        "alembic",
        "asyncpg",
        "pydantic-settings",
        "passlib[bcrypt]",
        "python-jose[cryptography]",
        "email-validator",
        "python-multipart",
        "python-dotenv",
    ],
    dev_deps=[],
    just_recipes=[
        "# start dev server with auto-reload\nrun:\n    uv run uvicorn (( pkg_name )).main:app --reload",
        '# generate a new alembic migration\nmigrate msg="":\n    uv run alembic revision --autogenerate -m "{{msg}}"',
        "# apply all pending migrations\nupgrade: wait-db\n    uv run alembic upgrade head",
        "# roll back one migration\ndowngrade:\n    uv run alembic downgrade -1",
        "# wait until postgres is ready\nwait-db:\n    uv run python scripts/wait_db.py",
        "# start db container, create databases, run migrations\ndb-create:\n    docker compose up -d db\n    just wait-db\n    docker compose exec db createdb -U postgres (( name ))\n    docker compose exec db createdb -U postgres (( name ))_test\n    just upgrade",
        "# drop and recreate both databases\ndb-reset:\n    docker compose exec db dropdb -U postgres --if-exists (( name ))\n    docker compose exec db dropdb -U postgres --if-exists (( name ))_test\n    just db-create",
    ],
    env_vars=[
        EnvVar(
            key="DATABASE_URL",
            default="postgresql+asyncpg://postgres:postgres@localhost:5432/(( name ))",
        ),
        EnvVar(key="DEBUG", default="false"),
        EnvVar(key="SECRET_KEY", default="change-me-in-production"),
    ],
)
