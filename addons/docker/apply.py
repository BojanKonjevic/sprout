from pathlib import Path

from scaffolder.context import Context
from scaffolder.render import make_env
from scaffolder.ui import success

_HERE = Path(__file__).parent


def apply(ctx: Context) -> None:
    files = _HERE / "files"
    env = make_env(files)

    render_vars = dict(name=ctx.name, pkg_name=ctx.pkg_name, template=ctx.template)

    ctx.write_file("Dockerfile", env.get_template("Dockerfile.j2").render(**render_vars))
    ctx.write_file(".dockerignore", (files / ".dockerignore").read_text())
    ctx.write_file("compose.yml", env.get_template("compose.yml.j2").render(**render_vars))

    success("Dockerfile, compose.yml, .dockerignore")


def extra_nix_packages() -> list[str]:
    return ["docker", "docker-compose"]


def extra_just_recipes(ctx: Context) -> str:
    return """\
docker-build:
    docker build -t (( name )) .
docker-run:
    docker run --rm -p 8000:8000 (( name ))
docker-up:
    docker compose up --build
docker-down:
    docker compose down"""
