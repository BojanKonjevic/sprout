import importlib.util
from pathlib import Path
from typing import Any

from scaffolder.context import Context
from scaffolder.render import make_env
from scaffolder.ui import step, success


def _collect(ctx: Context) -> dict[str, Any]:
    """Walk selected addons and merge their contributions."""
    deps: list[str] = []
    dev_deps: list[str] = []
    just_recipes: list[str] = []
    nix_packages: list[str] = []

    string_env = make_env()
    render_vars = {"name": ctx.name, "pkg_name": ctx.pkg_name, "template": ctx.template}

    for addon_id in ctx.addons:
        addon_apply = ctx.scaffolder_root / "addons" / addon_id / "apply.py"
        if not addon_apply.exists():
            continue
        mod = _load_addon_module(addon_apply)

        if hasattr(mod, "extra_deps"):
            deps.extend(mod.extra_deps())
        if hasattr(mod, "extra_dev_deps"):
            dev_deps.extend(mod.extra_dev_deps())
        if hasattr(mod, "extra_nix_packages"):
            nix_packages.extend(mod.extra_nix_packages())
        if hasattr(mod, "extra_just_recipes"):
            raw = mod.extra_just_recipes(ctx)
            rendered = string_env.from_string(raw).render(**render_vars)
            just_recipes.append(rendered)

    return {
        "extra_deps": deps,
        "extra_dev_deps": dev_deps,
        "extra_just_recipes": just_recipes,
        "extra_nix_packages": nix_packages,
    }


def _load_addon_module(addon_apply: Path) -> Any:
    spec = importlib.util.spec_from_file_location("addon_apply", addon_apply)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def generate_all(ctx: Context) -> None:
    step("Generating config files")
    env = make_env(ctx.scaffolder_root / "generate")
    contributions = _collect(ctx)

    vars: dict[str, Any] = {
        "name": ctx.name,
        "pkg_name": ctx.pkg_name,
        "template": ctx.template,
        "addons": ctx.addons,
        **contributions,
    }

    for template_name, dest in [
        ("pyproject.toml.j2", Path("pyproject.toml")),
        ("justfile.j2", Path("justfile")),
        ("flake.nix.j2", Path("flake.nix")),
    ]:
        dest.write_text(env.get_template(template_name).render(**vars))
        success(str(dest))
