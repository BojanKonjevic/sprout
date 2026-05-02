import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from scaffolder.ui import error, warn


@contextmanager
def scaffold_or_rollback(project_dir: Path) -> Generator[None, None, None]:
    """Run scaffold steps; delete project_dir entirely if anything raises.

    Usage:
        with scaffold_or_rollback(project_dir):
            ... all scaffold steps ...
    """
    try:
        yield
    except KeyboardInterrupt:
        _cleanup(project_dir)
        warn("Interrupted — removed partial directory.")
        raise
    except Exception as exc:
        _cleanup(project_dir)
        error(f"Scaffold failed: {exc}")
        warn("Rolled back — no directory was left behind.")
        raise SystemExit(1) from exc


def _cleanup(project_dir: Path) -> None:
    if project_dir.exists():
        shutil.rmtree(project_dir, ignore_errors=True)
