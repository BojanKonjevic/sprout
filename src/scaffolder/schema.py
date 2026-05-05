"""Declarative addon/template contributions – no file I/O here."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class InjectionMode(Enum):
    AFTER_SENTINEL = "after_sentinel"
    APPEND = "append"


@dataclass
class FileContribution:
    dest: str  # relative path, may contain {{pkg_name}}
    source: str | None = None
    content: str | None = None
    template: bool = False


@dataclass
class ComposeService:
    name: str
    image: str | None = None
    build: str | None = None
    ports: list[str] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    env_file: list[str] = field(default_factory=list)
    command: str | None = None
    depends_on: list[str] = field(default_factory=list)
    develop_watch: list[dict] = field(default_factory=list)


@dataclass
class EnvVar:
    key: str
    default: str
    comment: str = ""


@dataclass
class Injection:
    point: str
    content: str
    addon_id: str = ""


@dataclass
class AddonConfig:
    id: str
    description: str
    requires: list[str] = field(default_factory=list)
    files: list[FileContribution] = field(default_factory=list)
    compose_services: list[ComposeService] = field(default_factory=list)
    compose_volumes: list[str] = field(default_factory=list)
    env_vars: list[EnvVar] = field(default_factory=list)
    deps: list[str] = field(default_factory=list)
    dev_deps: list[str] = field(default_factory=list)
    just_recipes: list[str] = field(default_factory=list)
    injections: list[Injection] = field(default_factory=list)


@dataclass
class ExtensionPoint:
    file: str
    sentinel: str
    mode: InjectionMode = InjectionMode.AFTER_SENTINEL


@dataclass
class TemplateConfig:
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
