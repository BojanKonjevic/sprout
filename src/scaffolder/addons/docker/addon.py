from pathlib import Path

from scaffolder.schema import AddonConfig

_HERE = Path(__file__).parent.absolute()

config = AddonConfig(
    id="docker",
    description="Dockerfile + compose.yml + .dockerignore",
    requires=[],
)
