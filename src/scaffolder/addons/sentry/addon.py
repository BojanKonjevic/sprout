from pathlib import Path

from scaffolder.lockfile import ZenitLockfile
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
            point="main_startup",
            content="    from .integrations.sentry import init_sentry\n    init_sentry()",
        ),
        Injection(
            point="settings_fields",
            content='    sentry_dsn: str = ""\n    sentry_environment: str = "development"',
        ),
    ],
)


def can_apply(project_dir: Path, lockfile: ZenitLockfile) -> str | None:
    pkg_name = project_dir.name.replace("-", "_")
    template = lockfile.template

    # Need a src/ layout.
    if not (project_dir / "src").is_dir():
        return "No src/ directory found — sentry addon expects a src layout."

    # Don't overwrite an existing sentry integration.
    sentry_file = project_dir / "src" / pkg_name / "integrations" / "sentry.py"
    if sentry_file.exists():
        return f"{sentry_file.relative_to(project_dir)} already exists — sentry appears to already be configured."

    # Check that the injection target exists and hasn't already been patched.
    if template == "fastapi":
        lifecycle = project_dir / "src" / pkg_name / "lifecycle.py"
        if not lifecycle.exists():
            return "lifecycle.py not found — has it been moved or deleted?"
        if "init_sentry" in lifecycle.read_text():
            return "init_sentry already present in lifecycle.py — sentry appears to already be configured."
    else:
        main = project_dir / "src" / pkg_name / "main.py"
        if not main.exists():
            return "main.py not found — has it been moved or deleted?"
        if "init_sentry" in main.read_text():
            return "init_sentry already present in main.py — sentry appears to already be configured."

    return None
