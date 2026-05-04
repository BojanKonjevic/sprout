from __future__ import annotations

from pathlib import Path

from scaffolder.context import Context
from scaffolder.render import make_env
from scaffolder.ui import success, warn

_HERE = Path(__file__).parent


def apply(ctx: Context) -> None:
    files = _HERE / "files"

    integrations_rel = f"src/{ctx.pkg_name}/integrations"
    ctx.create_dir(integrations_rel)
    ctx.write_file(f"{integrations_rel}/__init__.py", "")

    ctx.copy_file(files / "redis.py", f"{integrations_rel}/redis.py")

    if ctx.template == "fastapi":
        _patch_settings(ctx)

    if ctx.has("docker"):
        if ctx.dry_run:
            ctx.record_modification("compose.yml", "append redis service")
        else:
            if Path("compose.yml").exists():
                _append_redis_service(Path("compose.yml"))
            else:
                warn("compose.yml not found — redis service append skipped.")
        success("integrations/redis.py, compose.yml (redis service appended)")
    else:
        env = make_env(files)
        ctx.write_file(
            "compose.redis.yml",
            env.get_template("compose.redis.yml.j2").render(name=ctx.name),
        )
        success("integrations/redis.py, compose.redis.yml")


def _patch_settings(ctx: Context) -> None:
    settings_rel = f"src/{ctx.pkg_name}/settings.py"
    if ctx.dry_run:
        ctx.record_modification(settings_rel, "add redis_url setting")
        return
    settings_path = Path(settings_rel)
    if not settings_path.exists():
        return
    text = settings_path.read_text()
    if "redis_url" in text:
        return
    old = '    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/'
    new = '    redis_url: str = "redis://localhost:6379/0"\n' + old
    if old in text:
        text = text.replace(old, new, 1)
    else:
        text = text.rstrip() + '\n    redis_url: str = "redis://localhost:6379/0"\n'
    settings_path.write_text(text)


def _append_redis_service(compose_path: Path) -> None:
    existing = compose_path.read_text()
    if "redis:" in existing:
        return
    redis_block = """\

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes

volumes:
  redis-data:
"""
    with open(compose_path, "a") as f:
        f.write(redis_block)


def extra_deps() -> list[str]:
    return ["redis>=5", "hiredis"]


def extra_dev_deps() -> list[str]:
    return ["fakeredis[aioredis]"]


def extra_nix_packages() -> list[str]:
    return ["redis"]


def extra_just_recipes(ctx: Context) -> str:
    if ctx.has("docker"):
        return """\
redis-up:
    docker compose up -d redis
redis-down:
    docker compose stop redis
redis-cli:
    redis-cli"""
    return """\
redis-up:
    docker compose -f compose.redis.yml up -d
redis-down:
    docker compose -f compose.redis.yml down
redis-cli:
    redis-cli"""
