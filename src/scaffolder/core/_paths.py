"""Centralised location for the scaffolder package root."""

import os
from pathlib import Path


def get_scaffolder_root() -> Path:
    """Return the filesystem root of the scaffolder package.

    The environment variable ``SCAFFOLDER_ROOT`` takes priority.  When unset
    (the common case), the parent directory of *this module* is used.
    """
    return Path(os.environ.get("SCAFFOLDER_ROOT", Path(__file__).parent.parent))
