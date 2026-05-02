"""Docker addon — adds Dockerfile, compose.yml, .dockerignore."""

import shutil
from pathlib import Path

import jinja2

from scaffolder.context import Context
from scaffolder.ui import success

_HERE = Path(__file__).parent


def apply(ctx: Context) -> None:
    files = _HERE / "files"
    shutil.copy(files / "Dockerfile", Path("Dockerfile"))
    shutil.copy(files / ".dockerignore", Path(".dockerignore"))

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(files)),
        keep_trailing_newline=True,
        variable_start_string="((",
        variable_end_string="))",
        block_start_string="[%",
        block_end_string="%]",
    )
    Path("compose.yml").write_text(
        env.get_template("compose.yml.j2").render(
            name=ctx.name,
            pkg_name=ctx.pkg_name,
            template=ctx.template,
        )
    )

    success("Dockerfile, compose.yml, .dockerignore")


def extra_nix_packages() -> list[str]:
    return ["docker", "docker-compose"]


def extra_just_recipes() -> str:
    return """\
docker-build:
    docker build -t (( name )) .
docker-run:
    docker run --rm -p 8000:8000 (( name ))
docker-up:
    docker compose up --build
docker-down:
    docker compose down"""
