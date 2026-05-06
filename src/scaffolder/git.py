import subprocess
from pathlib import Path

from scaffolder.ui import spinner


def init_and_commit(project_dir: Path) -> None:
    """Initialise a git repository and create the first commit."""
    with spinner("Initialising git repository"):

        def run(*cmd: str) -> None:
            subprocess.run(list(cmd), cwd=project_dir, check=True, capture_output=True)

        run("git", "init")
        run("git", "add", ".")
        run("git", "commit", "-m", "init: scaffold from jumpstart")
