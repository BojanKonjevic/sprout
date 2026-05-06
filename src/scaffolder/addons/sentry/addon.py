from pathlib import Path

from scaffolder.schema import AddonConfig, EnvVar, FileContribution, Injection

_HERE = Path(__file__).parent.absolute()

config = AddonConfig(
    id="sentry",
    description="Sentry error tracking + performance monitoring",
    requires=[],
    files=[
        FileContribution(
            dest="src/{{pkg_name}}/integrations/__init__.py",
            content="",
        ),
        FileContribution(
            dest="src/{{pkg_name}}/integrations/sentry.py",
            source=str(_HERE / "files" / "sentry.py.j2"),
            template=True,
        ),
    ],
    env_vars=[
        EnvVar(key="SENTRY_DSN", default=""),
        EnvVar(key="SENTRY_ENVIRONMENT", default="development"),
    ],
    deps=["sentry-sdk[fastapi]"],
    just_recipes=[
        "# print sentry-sdk version\nsentry-check:\n    uv run python -c \"import sentry_sdk; print('sentry-sdk', sentry_sdk.VERSION)\"",
        "# check whether SENTRY_DSN is set\nsentry-test:\n    uv run python -c \"from (( pkg_name )).integrations.sentry import init_sentry; import os; init_sentry(); print('Sentry DSN:', os.environ.get('SENTRY_DSN') or 'not set')\"",
    ],
    injections=[
        Injection(
            point="lifespan_startup",
            content="    from .integrations.sentry import init_sentry\n    init_sentry()",
        ),
        Injection(
            point="settings_fields",
            content='    sentry_dsn: str = ""\n    sentry_environment: str = "development"',
        ),
    ],
)
