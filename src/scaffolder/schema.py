"""Declarative addon/template contributions – no file I/O here."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class InjectionMode(Enum):
    AFTER_SENTINEL = "after_sentinel"
    APPEND = "append"  # append to end of file


@dataclass
class FileContribution:
    """A file to create or copy into the project."""

    dest: str  # relative path, may contain {{pkg_name}}
    source: str | None = None  # path to source file (relative to addon/template files/ dir)
    content: str | None = None  # inline content (for empty __init__.py etc.)
    template: bool = False  # render through Jinja2 if True


@dataclass
class ComposeService:
    """Declaration of a docker compose service."""

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
    """An environment variable to add to .env files."""

    key: str
    default: str
    comment: str = ""


@dataclass
class Injection:
    """Content to inject at a named extension point."""

    point: str  # matches an ExtensionPoint defined by the template
    content: str  # the text to insert
    addon_id: str = ""  # filled in automatically by the assembler


@dataclass
class AddonConfig:
    """Complete declaration of an addon."""

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
    """A place in a generated file where addons can inject content."""

    file: str  # relative path in the generated project
    sentinel: str  # exact comment string to replace/insert after
    mode: InjectionMode = InjectionMode.AFTER_SENTINEL


@dataclass
class TemplateConfig:
    """Declaration of a template's extension points and requirements."""

    id: str
    description: str
    requires_addons: list[str] = field(default_factory=list)
    extension_points: dict[str, ExtensionPoint] = field(default_factory=dict)


@dataclass
class Contributions:
    """Bag of everything collected from addons (and optionally the template)."""

    files: list[FileContribution] = field(default_factory=list)
    compose_services: list[ComposeService] = field(default_factory=list)
    compose_volumes: list[str] = field(default_factory=list)
    env_vars: list[EnvVar] = field(default_factory=list)
    deps: list[str] = field(default_factory=list)
    dev_deps: list[str] = field(default_factory=list)
    just_recipes: list[str] = field(default_factory=list)
    injections: list[Injection] = field(default_factory=list)
    _addon_configs: list[AddonConfig] = field(default_factory=list)
