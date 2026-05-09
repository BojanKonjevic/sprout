"""Declarative addon/template contribution types — no file I/O here."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class InjectionMode(Enum):
    AFTER_SENTINEL = "after_sentinel"
    APPEND = "append"


@dataclass
class FileContribution:
    """A single file to be written into the project directory."""

    dest: str  # relative path; may contain ``{{pkg_name}}``
    source: str | None = None
    content: str | None = None
    template: bool = False


@dataclass
class ComposeService:
    """A Docker Compose service block contributed by a template or addon."""

    name: str
    image: str | None = None
    build: str | None = None
    ports: list[str] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    env_file: list[str] = field(default_factory=list)
    command: str | None = None
    depends_on: list[str] | dict[str, dict[str, str]] = field(default_factory=list)
    develop_watch: list[dict[str, object]] = field(default_factory=list)
    healthcheck: dict[str, object] | None = None


@dataclass
class EnvVar:
    """A key/value pair to be appended to ``.env`` and ``.env.example``."""

    key: str
    default: str
    comment: str = ""


@dataclass
class Injection:
    """A snippet of code to be inserted at a named extension point."""

    point: str
    content: str
    addon_id: str = ""


@dataclass
class AddonConfig:
    """All contributions made by a single addon."""

    id: str
    description: str
    requires: list[str] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)  # empty = all templates allowed
    files: list[FileContribution] = field(default_factory=list)
    compose_services: list[ComposeService] = field(default_factory=list)
    compose_volumes: list[str] = field(default_factory=list)
    env_vars: list[EnvVar] = field(default_factory=list)
    deps: list[str] = field(default_factory=list)
    dev_deps: list[str] = field(default_factory=list)
    just_recipes: list[str] = field(default_factory=list)
    injections: list[Injection] = field(default_factory=list)
    _module: object = field(default=None, repr=False, compare=False)


@dataclass
class ExtensionPoint:
    """A named location inside a generated file where addons can inject code."""

    file: str
    sentinel: str
    mode: InjectionMode = InjectionMode.AFTER_SENTINEL


@dataclass
class TemplateConfig:
    """All contributions made by a template (blank, fastapi, …)."""

    id: str
    description: str
    requires_addons: list[str] = field(default_factory=list)
    extension_points: dict[str, ExtensionPoint] = field(default_factory=dict)
    dirs: list[str] = field(default_factory=list)
    files: list[FileContribution] = field(default_factory=list)
    compose_services: list[ComposeService] = field(default_factory=list)
    compose_volumes: list[str] = field(default_factory=list)
    env_vars: list[EnvVar] = field(default_factory=list)
    deps: list[str] = field(default_factory=list)
    dev_deps: list[str] = field(default_factory=list)
    just_recipes: list[str] = field(default_factory=list)
    injections: list[Injection] = field(default_factory=list)


@dataclass
class Contributions:
    """Merged contributions from all selected addons (and the template)."""

    files: list[FileContribution] = field(default_factory=list)
    dirs: list[str] = field(default_factory=list)
    compose_services: list[ComposeService] = field(default_factory=list)
    compose_volumes: list[str] = field(default_factory=list)
    env_vars: list[EnvVar] = field(default_factory=list)
    deps: list[str] = field(default_factory=list)
    dev_deps: list[str] = field(default_factory=list)
    just_recipes: list[str] = field(default_factory=list)
    injections: list[Injection] = field(default_factory=list)
    _addon_configs: list[AddonConfig] = field(default_factory=list)
