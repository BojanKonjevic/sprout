from pathlib import Path

from scaffolder.lockfile import ZenitLockfile
from scaffolder.schema import AddonConfig, FileContribution

_HERE = Path(__file__).parent.absolute()

config = AddonConfig(
    id="docker",
    description="Dockerfile + compose.yml + .dockerignore",
    requires=[],
    files=[
        FileContribution(
            dest="Dockerfile",
            source=str(_HERE / "files" / "Dockerfile.j2"),
            template=True,
        ),
        FileContribution(
            dest="compose.yml",
            source=str(_HERE / "files" / "compose.yml.j2"),
            template=True,
        ),
        FileContribution(
            dest=".dockerignore",
            source=str(_HERE / "files" / ".dockerignore"),
        ),
    ],
    just_recipes=[
        "# build and start all services\ndocker-up:\n    docker compose up --build",
        "# stop all services\ndocker-down:\n    docker compose down",
    ],
)


def can_apply(project_dir: Path, lockfile: ZenitLockfile) -> str | None:
    # Need a src/ layout to know where the package lives.
    if not (project_dir / "src").is_dir():
        return "No src/ directory found — docker addon expects a src layout."

    # Need pyproject.toml to exist for the Dockerfile COPY step to make sense.
    if not (project_dir / "pyproject.toml").exists():
        return "No pyproject.toml found — docker addon requires a pyproject.toml."

    # Don't overwrite an existing Dockerfile.
    if (project_dir / "Dockerfile").exists():
        return (
            "Dockerfile already exists. Remove it first if you want to regenerate it."
        )

    # Don't overwrite an existing compose.yml.
    if (project_dir / "compose.yml").exists():
        return (
            "compose.yml already exists. Remove it first if you want to regenerate it."
        )

    return None
