from pathlib import Path

from scaffolder.schema import AddonConfig, ComposeService, FileContribution

_HERE = Path(__file__).parent.absolute()

config = AddonConfig(
    id="celery",
    description="Celery worker + beat scheduler, backed by Redis",
    requires=["redis"],
    files=[
        FileContribution(
            dest="src/{{pkg_name}}/tasks/__init__.py",
            content="",
        ),
        FileContribution(
            dest="src/{{pkg_name}}/tasks/celery_app.py",
            source=str(_HERE / "files" / "tasks" / "celery_app.py.j2"),
            template=True,
        ),
        FileContribution(
            dest="src/{{pkg_name}}/tasks/example_tasks.py",
            source=str(_HERE / "files" / "tasks" / "example_tasks.py.j2"),
            template=True,
        ),
    ],
    compose_services=[
        ComposeService(
            name="celery-worker",
            build=".",
            command="celery -A {{pkg_name}}.tasks.celery_app worker --loglevel=info",
            env_file=[".env"],
            environment={"REDIS_URL": "redis://redis:6379/0"},
            depends_on=["redis"],
            develop_watch=[{"action": "sync", "path": "./src", "target": "/app/src"}],
        ),
        ComposeService(
            name="celery-beat",
            build=".",
            command="celery -A {{pkg_name}}.tasks.celery_app beat --loglevel=info",
            env_file=[".env"],
            environment={"REDIS_URL": "redis://redis:6379/0"},
            depends_on=["redis"],
            develop_watch=[{"action": "sync", "path": "./src", "target": "/app/src"}],
        ),
    ],
    deps=["celery[redis]>=5", "flower"],
    dev_deps=["pytest-celery"],
    just_recipes=[
        "# start celery worker and beat scheduler\ncelery-up:\n    docker compose up -d celery-worker celery-beat",
        "# stop celery worker and beat scheduler\ncelery-down:\n    docker compose stop celery-worker celery-beat",
        "# open flower monitoring UI on port 5555\ncelery-flower:\n    docker compose run --rm celery-worker celery -A (( pkg_name )).tasks.celery_app flower --port=5555",
        "# tail celery worker logs\ncelery-logs:\n    docker compose logs -f celery-worker",
    ],
)
