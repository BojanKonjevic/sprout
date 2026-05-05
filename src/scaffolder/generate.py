"""Generate pyproject.toml and justfile from template + addon contributions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from scaffolder.render import make_env
from scaffolder.ui import step, success

if TYPE_CHECKING:
    from scaffolder.context import Context
    from scaffolder.schema import Contributions, TemplateConfig


def generate_all(
    ctx: Context,
    template_cfg: TemplateConfig,
    contributions: Contributions,
) -> None:
    step("Generating config files")
    env = make_env(ctx.scaffolder_root / "generate")
    string_env = make_env()

    render_vars = {
        "name": ctx.name,
        "pkg_name": ctx.pkg_name,
        "template": ctx.template,
        "addons": ctx.addons,
    }

    rendered_template_recipes = []
    for raw in template_cfg.just_recipes:
        rendered_template_recipes.append(string_env.from_string(raw).render(**render_vars))

    rendered_addon_recipes = []
    for raw in contributions.just_recipes:
        rendered_addon_recipes.append(string_env.from_string(raw).render(**render_vars))

    vars = {
        "name": ctx.name,
        "pkg_name": ctx.pkg_name,
        "template": ctx.template,
        "addons": ctx.addons,
        "deps": template_cfg.deps + contributions.deps,
        "dev_deps": template_cfg.dev_deps + contributions.dev_deps,
        "template_just_recipes": rendered_template_recipes,
        "extra_just_recipes": rendered_addon_recipes,
    }

    for template_name, dest_rel in [
        ("pyproject.toml.j2", "pyproject.toml"),
        ("justfile.j2", "justfile"),
    ]:
        content = env.get_template(template_name).render(**vars)
        ctx.write_file(dest_rel, content)
        if not ctx.dry_run:
            success(dest_rel)
