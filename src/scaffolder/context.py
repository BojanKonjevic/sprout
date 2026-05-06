import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Context:
    """Runtime state passed through the entire scaffold pipeline."""

    name: str
    pkg_name: str
    template: str
    addons: list[str]
    scaffolder_root: Path
    project_dir: Path
    _dry_run: bool = False

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    def has(self, addon: str) -> bool:
        return addon in self.addons

    # ── Filesystem abstraction ────────────────────────────────────────────────
    # Each method checks dry_run first; DryRunContext overrides the _record_*
    # hooks so the same codepaths exercise the recording logic without I/O.

    def write_file(self, path: str, content: str) -> None:
        if self.dry_run:
            self._record_write(path, content)
            return
        dest = self.project_dir / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)

    def create_dir(self, path: str) -> None:
        if self.dry_run:
            self._record_dir(path)
            return
        (self.project_dir / path).mkdir(parents=True, exist_ok=True)

    def copy_file(self, src: Path, dest_relative: str) -> None:
        if self.dry_run:
            self._record_copy(dest_relative)
            return
        dest = self.project_dir / dest_relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dest)
        dest.chmod(dest.stat().st_mode | 0o600)

    def append_to_file(self, path: str, content: str) -> None:
        if self.dry_run:
            self._record_append(path, content)
            return
        file_path = self.project_dir / path
        with open(file_path, "a") as f:
            f.write(content)

    def record_modification(self, path: str, description: str) -> None:
        if self.dry_run:
            self._record_action("modify", path, description)

    def execute_command(self, cmd: list[str]) -> None:
        if self.dry_run:
            return
        subprocess.run(cmd, check=True, capture_output=True)

    # ── Recording hooks (overridden in DryRunContext) ─────────────────────────

    def _record_write(self, path: str, content: str = "") -> None:
        pass

    def _record_dir(self, path: str) -> None:
        pass

    def _record_copy(self, path: str) -> None:
        pass

    def _record_append(self, path: str, content: str) -> None:
        pass

    def _record_action(self, action: str, path: str, description: str) -> None:
        pass
