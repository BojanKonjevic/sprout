from __future__ import annotations

from pathlib import Path

from scaffolder.context import Context
from scaffolder.render import make_env
from scaffolder.ui import success, warn

_HERE = Path(__file__).parent


def apply(ctx: Context) -> None:
    tasks_dir_rel = f"src/{ctx.pkg_name}/tasks"
    ctx.create_dir(tasks_dir_rel)
    ctx.write_file(f"{tasks_dir_rel}/__init__.py", "")

    env = make_env(_HERE / "files" / "tasks")
    render_vars = dict(name=ctx.name, pkg_name=ctx.pkg_name)

    ctx.write_file(
        f"{tasks_dir_rel}/celery_app.py",
        env.get_template("celery_app.py.j2").render(**render_vars),
    )
    ctx.write_file(
        f"{tasks_dir_rel}/example_tasks.py",
        env.get_template("example_tasks.py.j2").render(**render_vars),
    )

    if ctx.has("docker"):
        if ctx.dry_run:
            ctx.record_modification("compose.yml", "append celery-worker and celery-beat services")
        else:
            if Path("compose.yml").exists():
                _append_worker_service(Path("compose.yml"), ctx)
            else:
                warn("compose.yml not found — celery services append skipped.")
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
