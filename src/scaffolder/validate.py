import re
import sys
import shutil
import subprocess
from pathlib import Path

from scaffolder.ui import error, info, warn

STDLIB_RESERVED = {
    "test",
    "sys",
    "os",
    "io",
    "re",
    "json",
    "math",
    "time",
    "datetime",
    "collections",
    "itertools",
    "functools",
    "pathlib",
    "typing",
    "abc",
    "ast",
    "copy",
    "csv",
    "enum",
    "http",
    "logging",
    "operator",
    "random",
    "socket",
    "string",
    "struct",
    "threading",
    "types",
    "unittest",
    "urllib",
    "uuid",
    "warnings",
    "xml",
    "email",
    "html",
    "queue",
    "array",
    "bisect",
    "calendar",
    "cmath",
    "contextlib",
    "contextvars",
    "dataclasses",
    "decimal",
    "difflib",
    "dis",
    "filecmp",
    "fnmatch",
    "fractions",
    "gc",
    "getopt",
    "getpass",
    "gettext",
    "glob",
    "graphlib",
    "hashlib",
    "heapq",
    "hmac",
    "inspect",
    "ipaddress",
    "keyword",
    "locale",
    "marshal",
    "mimetypes",
    "mmap",
    "numbers",
    "pickle",
    "pprint",
    "profile",
    "pstats",
    "readline",
    "runpy",
    "select",
    "selectors",
    "shelve",
    "shlex",
    "shutil",
    "signal",
    "site",
    "smtplib",
    "sqlite3",
    "stat",
    "statistics",
    "subprocess",
    "symbol",
    "symtable",
    "sysconfig",
    "tabnanny",
    "tarfile",
    "tempfile",
    "textwrap",
    "token",
    "tokenize",
    "tomllib",
    "trace",
    "traceback",
    "tracemalloc",
    "tty",
    "unicodedata",
    "venv",
    "weakref",
    "webbrowser",
    "zipapp",
    "zipfile",
    "zipimport",
    "zlib",
    "zoneinfo",
}


# ---------------------------------------------------------------------------
# Name validation
# ---------------------------------------------------------------------------


def validate_name(name: str, pkg_name: str) -> None:
    if Path(name).exists():
        error(f"Directory '{name}' already exists.")
        sys.exit(1)

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", name):
        error(f"Invalid project name '{name}'.")
        info(
            "Must start with a letter; only letters, numbers, hyphens, and underscores allowed."
        )
        sys.exit(1)

    if pkg_name in STDLIB_RESERVED:
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
    failures += _check_nix()
    failures += _check_direnv()

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

    # Require uv >= 0.4 — older versions use a different venv layout
    try:
        out = subprocess.run(
            ["uv", "--version"], capture_output=True, text=True, check=True
        ).stdout.strip()
        # "uv 0.4.18" or "uv 0.5.0"
        parts = out.split()
        if len(parts) >= 2:
            major, minor, *_ = (int(x) for x in parts[1].split("."))
            if (major, minor) < (0, 4):
                return [
                    f"uv {parts[1]} is too old (need >= 0.4).\n"
                    "     Upgrade: uv self update"
                ]
    except (subprocess.CalledProcessError, ValueError):
        pass  # version parse failed — not worth blocking on

    return []


def _check_git() -> list[str]:
    if shutil.which("git") is None:
        return [
            "'git' is not installed or not in PATH.\n"
            "     Install: https://git-scm.com/downloads\n"
            "     Or via nix: nix-env -iA nixpkgs.git"
        ]
    return []


def _check_nix() -> list[str]:
    if shutil.which("nix") is None:
        return [
            "'nix' is not installed.\n"
            "     Install: https://nixos.org/download  (multi-user recommended)\n"
            "     Quick:   curl -L https://nixos.org/nix/install | sh"
        ]

    # Check that flakes are enabled — nix flake lock will fail silently otherwise
    try:
        result = subprocess.run(
            ["nix", "config", "show", "experimental-features"],
            capture_output=True,
            text=True,
        )
        features = result.stdout
        if "flakes" not in features or "nix-command" not in features:
            return [
                "Nix flakes are not enabled.\n"
                "     Add to ~/.config/nix/nix.conf:\n"
                "       experimental-features = nix-command flakes"
            ]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass  # if the config subcommand itself fails, move on

    return []


def _check_direnv() -> list[str]:
    if shutil.which("direnv") is None:
        return [
            "'direnv' is not installed.\n"
            "     Install: https://direnv.net/docs/installation.html\n"
            "     Or via nix: nix-env -iA nixpkgs.direnv\n"
            "     Don't forget to hook it into your shell."
        ]
    return []


# ---------------------------------------------------------------------------
# Kept for backwards compat — now a thin wrapper around check_preflight
# ---------------------------------------------------------------------------


def check_uv_installed() -> None:
    """Deprecated: call check_preflight() instead."""
    warn("check_uv_installed() is deprecated — use check_preflight()")
    check_preflight()
