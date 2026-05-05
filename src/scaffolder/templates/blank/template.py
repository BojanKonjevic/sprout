from scaffolder.schema import TemplateConfig, ExtensionPoint, InjectionMode

config = TemplateConfig(
    id="blank",
    description="dev tools only (pytest, ruff, mypy)",
    requires_addons=[],
    extension_points={
        "main_startup": ExtensionPoint(
            file="src/{{pkg_name}}/main.py",
            sentinel="    # [jumpstart: main_startup]",
        ),
        "env_vars": ExtensionPoint(
            file=".env",
            sentinel="# [jumpstart: env_vars]",
        ),
    },
)
