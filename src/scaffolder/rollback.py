import os
import shutil
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from scaffolder.ui import error, warn


@contextmanager
def scaffold_or_rollback(project_dir: Path) -> Generator[None]:
    """Context manager that removes *project_dir* if the scaffold fails.

    On ``KeyboardInterrupt`` the directory is cleaned up and the interrupt is
    re-raised.  On any other exception the directory is cleaned up and the
    process exits with code 1.
    """
    try:
        yield
    except KeyboardInterrupt:
        _cleanup(project_dir)
        warn("Interrupted — removed partial directory.")
        raise
    except (Exception, SystemExit) as exc:
        _cleanup(project_dir)
        if not isinstance(exc, SystemExit):
            error(f"Scaffold failed: {exc}")
        warn("Rolled back — no directory was left behind.")
        raise SystemExit(1) from exc


def _cleanup(project_dir: Path) -> None:
    if project_dir.exists():
        os.chdir(project_dir.parent)
        shutil.rmtree(project_dir, ignore_errors=True)
