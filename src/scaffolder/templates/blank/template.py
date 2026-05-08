from pathlib import Path

from scaffolder.schema import ExtensionPoint, FileContribution, TemplateConfig

_HERE = Path(__file__).parent.absolute()

config = TemplateConfig(
    id="blank",
    description="dev tools only (pytest, ruff, mypy)",
    requires_addons=[],
    extension_points={
        "main_startup": ExtensionPoint(
            file="src/{{pkg_name}}/main.py",
            sentinel="    # [zenit: main_startup]",
        ),
        "env_vars": ExtensionPoint(
            file=".env",
            sentinel="# [zenit: env_vars]",
        ),
    },
    dirs=[
        "src/{{pkg_name}}",
        "tests",
    ],
    files=[
        FileContribution(
            dest="src/{{pkg_name}}/__init__.py",
            content='"""(( name ))"""\n\n__version__ = "0.1.0"\n',
            template=True,  # uses (( name ))
        ),
        FileContribution(
            dest="src/{{pkg_name}}/main.py",
            source=str(_HERE / "files" / "main.py.j2"),
            template=True,
        ),
        FileContribution(
            dest="src/{{pkg_name}}/__main__.py",
            source=str(_HERE / "files" / "__main__.py"),
        ),
        FileContribution(
            dest="tests/test_main.py",
            source=str(_HERE / "files" / "tests" / "test_main.py.j2"),
            template=True,
        ),
        FileContribution(
            dest=".env",
            content="# [zenit: env_vars]\n",
        ),
    ],
    deps=["python-dotenv"],
    dev_deps=[],
    just_recipes=[
        "# run the app\nrun:\n    uv run python -m (( pkg_name ))",
    ],
)
