import re
import sys
import shutil
from pathlib import Path

from scaffolder.ui import error, info

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


def check_uv_installed() -> None:
    """Make sure 'uv' is available before doing anything else."""
    if shutil.which("uv") is None:
        error("'uv' is not installed or not in PATH.")
        sys.exit(1)
