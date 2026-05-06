"""Addon registry — discovers ``addon.py`` files and returns ``AddonConfig`` objects."""

import importlib.util
from pathlib import Path

from scaffolder.schema import AddonConfig

_HERE = Path(__file__).parent.absolute()


def get_available_addons() -> list[AddonConfig]:
    """Return one ``AddonConfig`` for every addon directory found under this package."""
    addons: list[AddonConfig] = []
    for addon_dir in sorted(
        p for p in _HERE.iterdir() if p.is_dir() and not p.name.startswith("_")
    ):
        try:
            spec = importlib.util.spec_from_file_location(
                "addon_config", addon_dir / "addon.py"
            )
            if spec is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            cfg: AddonConfig = mod.config
            cfg._module = mod  # attach module so post_apply can be called later
            addons.append(cfg)
        except (FileNotFoundError, AttributeError):
            continue
    return addons
