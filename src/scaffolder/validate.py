# src/scaffolder/validate.py
import re
import shutil
import subprocess
import sys
from pathlib import Path

import typer

from scaffolder.ui import error, info


def validate_name(name: str, pkg_name: str) -> None:
    if Path(name).exists():
        error(f"Directory '{name}' already exists.")
        raise typer.Exit(1)

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", name):
        error(f"Invalid project name '{name}'.")
        info("Must start with a letter; only letters, numbers, hyphens, and underscores allowed.")
        raise typer.Exit(1)

    if pkg_name in sys.stdlib_module_names:
        error(f"'{pkg_name}' shadows a Python stdlib module.")
        info(f"Suggestion: '{name}-app'  or  'my-{name}'")
        raise typer.Exit(1)


def check_preflight() -> None:
    failures: list[str] = []
    failures += _check_uv()
    failures += _check_git()

    if failures:
        print()
        for msg in failures:
            error(msg)
        print()
        raise typer.Exit(1)


def _check_uv() -> list[str]:
    if shutil.which("uv") is None:
        return [
            "'uv' is not installed or not in PATH.\n"
            "     Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
        ]
    try:
        out = subprocess.run(
            ["uv", "--version"], capture_output=True, text=True, check=True
        ).stdout.strip()
        parts = out.split()
        if len(parts) >= 2:
            major, minor, *_ = (int(x) for x in parts[1].split("."))
            if (major, minor) < (0, 4):
                return [f"uv {parts[1]} is too old (need >= 0.4).\n     Upgrade: uv self update"]
    except subprocess.CalledProcessError, ValueError:
        pass
    return []


def _check_git() -> list[str]:
    if shutil.which("git") is None:
        return [
            "'git' is not installed or not in PATH.\n     Install: https://git-scm.com/downloads\n"
        ]
    return []


def validate_addon_deps(addons: list[str], available: list[tuple[str, str, list[str]]]) -> None:
    requires_map = {aid: reqs for aid, _, reqs in available}
    for addon in addons:
        for req in requires_map.get(addon, []):
            if req not in addons:
                error(f"Addon '{addon}' requires '{req}', but it wasn't selected.")
                raise typer.Exit(1)
