from scaffolder.schema import TemplateConfig, ExtensionPoint, InjectionMode

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
)
