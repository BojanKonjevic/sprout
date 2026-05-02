import subprocess

from scaffolder.ui import step, success


def lock_flake() -> None:
    step("Locking Nix flake inputs...")
    subprocess.run(["nix", "flake", "lock"], check=True)
    success("flake.lock written.")
