"""zenit project lockfile — .zenit.toml

Written into the project root at scaffold time. Read by `zenit add` to know
what template and addons are already present, and what version of zenit
created the project.

Format
------
    [project]
    template = "fastapi"
    addons = ["docker", "redis"]
    zenit_version = "1.0.1"
    schema_version = 2

All fields are optional when reading — the lockfile may be absent (project
was not scaffolded by zenit, or was scaffolded before lockfiles existed).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from importlib.metadata import version as get_version
from pathlib import Path

import tomli_w

LOCKFILE_NAME = ".zenit.toml"
SCHEMA_VERSION = 2


@dataclass
class ZenitLockfile:
    template: str = ""
    addons: list[str] = field(default_factory=list)
    zenit_version: str = ""
    schema_version: int = 0


def write_lockfile(project_dir: Path, template: str, addons: list[str]) -> None:
    """Write .zenit.toml into *project_dir*."""

    try:
        zenit_version = get_version("zenit")
    except Exception:
        zenit_version = "dev"

    data = {
        "project": {
            "template": template,
            "addons": list(addons),
            "zenit_version": zenit_version,
            "schema_version": SCHEMA_VERSION,
        }
    }
    path = project_dir / LOCKFILE_NAME
    path.write_text(tomli_w.dumps(data), encoding="utf-8")


def read_lockfile(project_dir: Path) -> ZenitLockfile | None:
    """Read .zenit.toml from *project_dir*.

    Returns None if the file does not exist or cannot be parsed — callers
    must handle the absent-lockfile case gracefully.
    """
    path = project_dir / LOCKFILE_NAME
    if not path.exists():
        return None

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return None

    project = data.get("project", {})
    if not isinstance(project, dict):
        return None

    template = project.get("template", "")
    addons = project.get("addons", [])
    zenit_version = project.get("zenit_version", "")
    schema_version = project.get("schema_version", 0)

    if not isinstance(template, str):
        template = ""
    if not isinstance(addons, list):
        addons = []
    addons = [a for a in addons if isinstance(a, str)]
    if not isinstance(zenit_version, str):
        zenit_version = ""
    if not isinstance(schema_version, int):
        schema_version = 0

    return ZenitLockfile(
        template=template,
        addons=addons,
        zenit_version=zenit_version,
        schema_version=schema_version,
    )
