from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Context:
    name: str
    pkg_name: str
    template: str
    addons: list[str]
    scaffolder_root: Path
    project_dir: Path

    def has(self, addon: str) -> bool:
        """Convenience — lets apply.py and templates do: if ctx.has('docker')"""
        return addon in self.addons
