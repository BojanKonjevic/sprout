"""Docker addon — adds Dockerfile, compose.yml, .dockerignore."""

import shutil
from pathlib import Path

from scaffolder.context import Context
from scaffolder.ui import success

_HERE = Path(__file__).parent


def apply(ctx: Context) -> None:
    files = _HERE / "files"
    shutil.copy(files / "Dockerfile", Path("Dockerfile"))
    shutil.copy(files / ".dockerignore", Path(".dockerignore"))

    compose = (files / "compose.yml").read_text()
    Path("compose.yml").write_text(compose.replace("{{name}}", ctx.name))

    success("Dockerfile, compose.yml, .dockerignore")


# ---------------------------------------------------------------------------
# Contributions to generated config files
# ---------------------------------------------------------------------------


def extra_nix_packages() -> list[str]:
    return ["docker", "docker-compose"]


def extra_just_recipes() -> str:
    # Use (( name )) — these strings are rendered through Jinja before
    # being inserted into the justfile, so they must use the same
    # delimiters as everything else. {{name}} would pass through raw.
    return """\
docker-build:
    docker build -t (( name )) .
docker-run:
    docker run --rm -p 8000:8000 (( name ))
docker-up:
    docker compose up --build
docker-down:
    docker compose down"""
