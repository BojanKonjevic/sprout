"""Declarative config for the redis addon."""

from pathlib import Path

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
