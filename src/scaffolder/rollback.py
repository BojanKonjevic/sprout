import os
import shutil
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from scaffolder.ui import error, warn


@contextmanager
def scaffold_or_rollback(project_dir: Path) -> Generator[None]:
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
    print(f"\n[DEBUG] _cleanup called")
    print(f"[DEBUG] project_dir = {project_dir}")
    print(f"[DEBUG] project_dir.exists() = {project_dir.exists()}")
    print(f"[DEBUG] cwd = {os.getcwd()}")

    if project_dir.exists():
        try:
            os.chdir(project_dir.parent)
            print(f"[DEBUG] chdir to {project_dir.parent} — ok")
        except Exception as e:
            print(f"[DEBUG] chdir failed: {e}")

        try:
            shutil.rmtree(project_dir)
            print(f"[DEBUG] rmtree succeeded")
        except Exception as e:
            print(f"[DEBUG] rmtree failed: {e}")

        print(f"[DEBUG] project_dir.exists() after rmtree = {project_dir.exists()}")
    else:
        print(f"[DEBUG] project_dir does not exist, nothing to clean")
