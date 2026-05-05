from pathlib import Path
from scaffolder.schema import AddonConfig, FileContribution

_HERE = Path(__file__).parent.absolute()

config = AddonConfig(
    id="github-actions",
    description="CI workflow (lint, type-check, test on push/PR)",
    requires=[],
    files=[
        FileContribution(
            dest=".github/workflows/ci.yml",
            source=str(_HERE / "files" / "ci.yml.j2"),
            template=True,
        ),
    ],
)
