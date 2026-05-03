import subprocess
from pathlib import Path

from scaffolder.ui import spinner


def lock_flake() -> None:
    with spinner("Locking Nix flake inputs"):
        subprocess.run(
            ["nix", "flake", "lock"],
            check=True,
            capture_output=True,
        )


def warm_devshell() -> None:
    with spinner("Building dev shell"):
        subprocess.run(
            ["nix", "develop", "--command", "true"],
            check=True,
            capture_output=True,
        )
