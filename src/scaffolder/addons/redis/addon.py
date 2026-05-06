"""Declarative config for the redis addon."""

from pathlib import Path

from scaffolder.lockfile import ZenitLockfile
from scaffolder.schema import (
    AddonConfig,
    ComposeService,
    EnvVar,
    FileContribution,
    Injection,
)

_HERE = Path(__file__).parent.absolute()

config = AddonConfig(
    id="redis",
    description="Redis service + connection helper + compose service",
    requires=[],
    files=[
        FileContribution(
            dest="src/{{pkg_name}}/integrations/__init__.py",
            content="",
        ),
        FileContribution(
            dest="src/{{pkg_name}}/integrations/redis.py",
            source=str(_HERE / "files" / "redis.py"),
        ),
    ],
    compose_services=[
        ComposeService(
            name="redis",
            image="redis:7-alpine",
            ports=["6379:6379"],
            volumes=["redis-data:/data"],
            command="redis-server --appendonly yes",
            healthcheck={
                "test": ["CMD", "redis-cli", "ping"],
                "interval": "1s",
                "timeout": "3s",
                "retries": 5,
            },
        )
    ],
    compose_volumes=["redis-data"],
    env_vars=[
        EnvVar(key="REDIS_URL", default="redis://localhost:6379/0"),
    ],
    deps=["redis>=5", "hiredis"],
    dev_deps=["fakeredis[aioredis]"],
    just_recipes=[
        "# start redis\nredis-up:\n    docker compose up -d redis",
        "# stop redis\nredis-down:\n    docker compose stop redis",
        "# open redis-cli\nredis-cli:\n    redis-cli",
    ],
    injections=[
        Injection(
            point="settings_fields",
            content='    redis_url: str = "redis://localhost:6379/0"',
        ),
    ],
)


def can_apply(project_dir: Path, lockfile: ZenitLockfile) -> str | None:
    pkg_name = project_dir.name.replace("-", "_")

    # Need a src/ layout.
    if not (project_dir / "src").is_dir():
        return "No src/ directory found — redis addon expects a src layout."

    # Don't overwrite an existing redis integration.
    redis_file = project_dir / "src" / pkg_name / "integrations" / "redis.py"
    if redis_file.exists():
        return f"{redis_file.relative_to(project_dir)} already exists — redis appears to already be configured."

    return None
