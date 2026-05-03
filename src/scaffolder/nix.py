import subprocess

from scaffolder.ui import spinner, warn


def lock_flake() -> None:
    with spinner("Locking Nix flake inputs"):
        subprocess.run(
            ["nix", "flake", "lock"],
            check=True,
            capture_output=True,
        )


def warm_devshell() -> None:
    with spinner("Pre-building dev shell  (speeds up first cd)"):
        result = subprocess.run(
            ["direnv", "exec", ".", "true"],
            capture_output=True,
        )
    if result.returncode != 0:
        warn("Dev shell pre-build failed — first 'cd' will build it instead.")
        warn(result.stderr.decode(errors="replace").strip())
