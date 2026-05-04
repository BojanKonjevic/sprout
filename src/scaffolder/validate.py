import re
import shutil
import subprocess
import sys
from pathlib import Path

from scaffolder.ui import error, info

# ---------------------------------------------------------------------------
# Name validation
# ---------------------------------------------------------------------------


def validate_name(name: str, pkg_name: str) -> None:
    if Path(name).exists():
        error(f"Directory '{name}' already exists.")
        sys.exit(1)

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", name):
        error(f"Invalid project name '{name}'.")
        info("Must start with a letter; only letters, numbers, hyphens, and underscores allowed.")
        sys.exit(1)

    if pkg_name in sys.stdlib_module_names:
        error(f"'{pkg_name}' shadows a Python stdlib module.")
        info(f"Suggestion: '{name}-app'  or  'my-{name}'")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Preflight checks — run before touching the filesystem
# ---------------------------------------------------------------------------


def check_preflight() -> None:
    """Check all required tools are present. Prints all failures at once."""
    failures: list[str] = []

    failures += _check_uv()
    failures += _check_git()

    if failures:
        print()
        for msg in failures:
            error(msg)
        print()
        sys.exit(1)


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
    except (subprocess.CalledProcessError, ValueError):
        pass

    return []


def _check_git() -> list[str]:
    if shutil.which("git") is None:
        return [
            "'git' is not installed or not in PATH.\n     Install: https://git-scm.com/downloads\n"
        ]
    return []


def validate_addon_deps(
    selected: list[str],
    available: list[tuple[str, str, list[str]]],
) -> None:
    """Fail fast if any selected addon is missing a required dependency."""
    requires_map = {addon_id: reqs for addon_id, _, reqs in available}
    errors: list[str] = []

    for addon_id in selected:
        for req in requires_map.get(addon_id, []):
            if req not in selected:
                errors.append(
                    f"Addon '{addon_id}' requires '{req}' — add it or remove '{addon_id}'."
                )

    if errors:
        print()
        for msg in errors:
            error(msg)
        print()
        sys.exit(1)
