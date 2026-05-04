"""Celery addon — task queue backed by Redis, written into tasks/ subpackage."""

from __future__ import annotations

from pathlib import Path

import jinja2

from scaffolder.context import Context
from scaffolder.ui import success

_HERE = Path(__file__).parent


def apply(ctx: Context) -> None:
    # Create tasks/ subpackage
    tasks_dir = Path("src") / ctx.pkg_name / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "__init__.py").touch()

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_HERE / "files" / "tasks")),
        keep_trailing_newline=True,
        variable_start_string="((",
        variable_end_string="))",
        block_start_string="[%",
        block_end_string="%]",
    )

    render_vars = dict(name=ctx.name, pkg_name=ctx.pkg_name)

    (tasks_dir / "celery_app.py").write_text(
        env.get_template("celery_app.py.j2").render(**render_vars)
    )
    (tasks_dir / "example_tasks.py").write_text(
        env.get_template("example_tasks.py.j2").render(**render_vars)
    )

    if ctx.has("docker") and Path("compose.yml").exists():
        _append_worker_service(Path("compose.yml"), ctx)
        success(
            "tasks/celery_app.py, tasks/example_tasks.py, "
            "compose.yml (celery worker + beat appended)"
        )
    else:
        success("tasks/celery_app.py, tasks/example_tasks.py")


def _append_worker_service(compose_path: Path, ctx: Context) -> None:
    existing = compose_path.read_text()
    if "celery" in existing:
        return

    worker_block = f"""\
  celery-worker:
    build: .
    command: celery -A {ctx.pkg_name}.tasks.celery_app worker --loglevel=info
    env_file:
      - .env
    environment:
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - redis
    develop:
      watch:
        - action: sync
          path: ./src
          target: /app/src

  celery-beat:
    build: .
    command: celery -A {ctx.pkg_name}.tasks.celery_app beat --loglevel=info
    env_file:
      - .env
    environment:
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - redis
    develop:
      watch:
        - action: sync
          path: ./src
          target: /app/src
"""

    if "\nvolumes:" in existing:
        updated = existing.replace("\nvolumes:", "\n" + worker_block + "\nvolumes:", 1)
    else:
        updated = existing.rstrip() + "\n\n" + worker_block

    compose_path.write_text(updated)


def extra_deps() -> list[str]:
    return ["celery[redis]>=5", "flower"]


def extra_dev_deps() -> list[str]:
    return ["pytest-celery"]


def extra_just_recipes(ctx: Context) -> str:
    if ctx.has("docker"):
        return """\
celery-up:
    docker compose up -d celery-worker celery-beat
celery-down:
    docker compose stop celery-worker celery-beat
celery-flower:
    docker compose run --rm celery-worker celery -A (( pkg_name )).tasks.celery_app flower --port=5555  # noqa: E501
celery-logs:
    docker compose logs -f celery-worker"""
    return """\
celery-worker:
    celery -A (( pkg_name )).tasks.celery_app worker --loglevel=info
celery-beat:
    celery -A (( pkg_name )).tasks.celery_app beat --loglevel=info
celery-flower:
    celery -A (( pkg_name )).tasks.celery_app flower --port=5555"""
