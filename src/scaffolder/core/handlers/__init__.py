# src/scaffolder/core/handlers/__init__.py
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from scaffolder.schema.models import ManifestBlock
from scaffolder.core.handlers.python_handler import PythonHandler
from scaffolder.core.handlers.env_handler import EnvHandler
from scaffolder.core.handlers.yaml_handler import YamlHandler
from scaffolder.core.handlers.toml_handler import TomlHandler
from scaffolder.core.handlers.justfile_handler import JustfileHandler


class FileHandler(ABC):
    """Base class for all file-type handlers."""

    @abstractmethod
    def can_handle(self, path: Path) -> bool: ...

    @abstractmethod
    def apply(
        self,
        file: Path,
        content: str,
        locator_name: str,
        locator_args: dict[str, object],
    ) -> tuple[str, int, int]: ...

    @abstractmethod
    def remove(self, file: Path, block: ManifestBlock) -> None: ...


class HandlerDispatcher:
    """Routes apply/remove calls to the correct FileHandler."""

    def __init__(self) -> None:

        self._handlers: list[FileHandler] = [
            PythonHandler(),
            EnvHandler(),
            YamlHandler(),
            TomlHandler(),
            JustfileHandler(),
        ]

    def _get(self, path: Path) -> FileHandler:
        for handler in self._handlers:
            if handler.can_handle(path):
                return handler
        raise ValueError(f"No handler found for file: {path}")

    def apply(
        self,
        file: Path,
        content: str,
        locator_name: str,
        locator_args: dict[str, object],
    ) -> tuple[str, int, int]:
        return self._get(file).apply(file, content, locator_name, locator_args)

    def remove(self, file: Path, block: ManifestBlock) -> None:
        self._get(file).remove(file, block)
