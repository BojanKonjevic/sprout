import subprocess
from pathlib import Path

from scaffolder.ui import spinner


def init_and_commit(project_dir: Path) -> None:
    """Initialise a git repository and create the first commit."""
    with spinner("Initialising git repository"):

        def run(*cmd: str) -> None:
            subprocess.run(list(cmd), cwd=project_dir, check=True, capture_output=True)

        run("git", "init")

        # Set a temporary identity if none is configured globally.
        # git init picks up global user.name/email, but CI lacks it.
        try:
            run("git", "config", "user.email")
        except subprocess.CalledProcessError:
            run("git", "config", "user.email", "zenit@localhost")
            run("git", "config", "user.name", "zenit")

        run("git", "add", ".")
        run("git", "commit", "-m", "init: scaffold from zenit")
