import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Context:
    name: str
    pkg_name: str
    template: str
    addons: list[str]
    scaffolder_root: Path
    project_dir: Path
    dry_run: bool = False

    def has(self, addon: str) -> bool:
        """Convenience — lets apply.py and templates do: if ctx.has('docker')"""
        return addon in self.addons

    # ── Filesystem abstraction (real I/O) ──────────────────────────────

    def write_file(self, path: str, content: str) -> None:
        """Write content to a file relative to project_dir."""
        if self.dry_run:
            self._record_write(path, content)
            return
        dest = self.project_dir / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)

    def create_dir(self, path: str) -> None:
        """Create a directory (and parents) relative to project_dir."""
        if self.dry_run:
            self._record_dir(path)
            return
        (self.project_dir / path).mkdir(parents=True, exist_ok=True)

    def copy_file(self, src: Path, dest_relative: str) -> None:
        """Copy a file from src to dest_relative (under project_dir)."""
        if self.dry_run:
            self._record_copy(dest_relative)
            return
        dest = self.project_dir / dest_relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dest)
        # Ensure the copy is user-writable regardless of source permissions
        dest.chmod(dest.stat().st_mode | 0o600)

    def append_to_file(self, path: str, content: str) -> None:
        """Append content to an existing file. Dry-run records the action."""
        if self.dry_run:
            self._record_append(path, content)
            return
        file_path = self.project_dir / path
        with open(file_path, "a") as f:
            f.write(content)

    def record_modification(self, path: str, description: str) -> None:
        """Record a file modification that cannot be captured by write/append.
        In real runs this is a no‑op; dry‑run stores the note."""
        if self.dry_run:
            self._record_action("modify", path, description)

    def execute_command(self, cmd: list[str]) -> None:
        """Execute a subprocess command (e.g. direnv allow). Dry‑run skips it."""
        if self.dry_run:
            return
        import subprocess

        subprocess.run(cmd, check=True, capture_output=True)

    # ── Recording hooks (overridden in DryRunContext) ─────────────────

    def _record_write(self, path: str, content: str = ""):
        pass

    def _record_dir(self, path: str):
        pass

    def _record_copy(self, path: str):
        pass

    def _record_append(self, path: str, content: str):
        pass

    def _record_action(self, action: str, path: str, description: str):
        pass
