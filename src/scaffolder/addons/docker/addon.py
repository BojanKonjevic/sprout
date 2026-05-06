from pathlib import Path

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
