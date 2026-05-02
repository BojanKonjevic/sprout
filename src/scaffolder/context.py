from dataclasses import dataclass
from pathlib import Path


@dataclass
class Context:
    name: str
    pkg_name: str
    template: str
    scaffolder_root: Path
    project_dir: Path
