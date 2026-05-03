import subprocess

from scaffolder.ui import spinner


def lock_flake() -> None:
    with spinner("Locking Nix flake inputs"):
        subprocess.run(["nix", "flake", "lock"], check=True, capture_output=True)
