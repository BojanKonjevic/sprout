import importlib.util
from pathlib import Path
from typing import Any

import jinja2

from scaffolder.context import Context
from scaffolder.ui import step, success


# ---------------------------------------------------------------------------
# Jinja env
# ---------------------------------------------------------------------------


def _make_env(templates_dir: Path) -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        keep_trailing_newline=True,
        variable_start_string="((",
        variable_end_string="))",
        block_start_string="[%",
        block_end_string="%]",
    )


def _make_string_env() -> jinja2.Environment:
    """Env for rendering addon recipe strings (no file loader needed)."""
    return jinja2.Environment(
        keep_trailing_newline=True,
        variable_start_string="((",
        variable_end_string="))",
        block_start_string="[%",
        block_end_string="%]",
    )


# ---------------------------------------------------------------------------
# Addon contribution collection
# ---------------------------------------------------------------------------


def _load_addon_module(addon_apply: Path) -> Any:
    spec = importlib.util.spec_from_file_location("addon_apply", addon_apply)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _collect(ctx: Context) -> dict[str, Any]:
    """Walk selected addons and merge their contributions."""
    deps: list[str] = []
    dev_deps: list[str] = []
    just_recipes: list[str] = []
    nix_packages: list[str] = []

    string_env = _make_string_env()
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
        if hasattr(mod, "extra_just_recipes_ctx"):
            raw = mod.extra_just_recipes_ctx(ctx)
            rendered = string_env.from_string(raw).render(**render_vars)
            just_recipes.append(rendered)
        elif hasattr(mod, "extra_just_recipes"):
            raw = mod.extra_just_recipes()
            rendered = string_env.from_string(raw).render(**render_vars)
            just_recipes.append(rendered)

    return {
        "extra_deps": deps,
        "extra_dev_deps": dev_deps,
        "extra_just_recipes": just_recipes,
        "extra_nix_packages": nix_packages,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_all(ctx: Context) -> None:
    step("Generating config files")
    env = _make_env(ctx.scaffolder_root / "generate")
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
