"""Redis addon — connection helper, compose service, settings patch."""

import shutil
from pathlib import Path

import jinja2

from scaffolder.context import Context
from scaffolder.ui import success

_HERE = Path(__file__).parent


def apply(ctx: Context) -> None:
    files = _HERE / "files"

    pkg_dir = Path("src") / ctx.pkg_name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(files / "redis.py", pkg_dir / "redis.py")

    if ctx.template == "fastapi":
        _patch_settings(Path("src") / ctx.pkg_name / "settings.py")

    if ctx.has("docker") and Path("compose.yml").exists():
        _append_redis_service(Path("compose.yml"))
        success("redis.py, compose.yml (redis service appended)")
    else:
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(files)),
            keep_trailing_newline=True,
            variable_start_string="((",
            variable_end_string="))",
            block_start_string="[%",
            block_end_string="%]",
        )
        Path("compose.redis.yml").write_text(
            env.get_template("compose.redis.yml.j2").render(name=ctx.name)
        )
        success("redis.py, compose.redis.yml")


def _patch_settings(settings_path: Path) -> None:
    if not settings_path.exists():
        return
    text = settings_path.read_text()
    if "redis_url" in text:
        return
    old = '    database_url: str = "postgresql+asyncpg:///'
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
    compose_path.write_text(existing.rstrip() + "\n" + redis_block)


# ---------------------------------------------------------------------------
# Contributions to generated config files
# ---------------------------------------------------------------------------


def extra_deps() -> list[str]:
    return ["redis>=5", "hiredis"]


def extra_dev_deps() -> list[str]:
    return ["fakeredis[aioredis]"]


def extra_nix_packages() -> list[str]:
    return ["redis"]


def extra_just_recipes() -> str:
    return """\
redis-up:
    docker compose -f compose.redis.yml up -d
redis-down:
    docker compose -f compose.redis.yml down
redis-cli:
    redis-cli"""
