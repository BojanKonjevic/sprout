from pathlib import Path

from scaffolder.lockfile import ZenitLockfile
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


def can_apply(project_dir: Path, lockfile: ZenitLockfile) -> str | None:
    # Don't overwrite an existing CI workflow.
    ci_file = project_dir / ".github" / "workflows" / "ci.yml"
    if ci_file.exists():
        return "ci.yml already exists at .github/workflows/ci.yml. Remove it first if you want to regenerate it."

    return None
