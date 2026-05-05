"""Generate pyproject.toml and justfile from template + addon contributions."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from scaffolder.render import make_env
from scaffolder.ui import step, success

if TYPE_CHECKING:
    from scaffolder.context import Context
    from scaffolder.schema import Contributions


def generate_all(ctx: Context, contributions: Contributions) -> None:
    step("Generating config files")
    env = make_env(ctx.scaffolder_root / "generate")

    # Render just recipes that still contain custom delimiters (( pkg_name ))
    string_env = make_env()  # uses default (( )) delimiters
    rendered_recipes = []
    for raw in contributions.just_recipes:
        rendered_recipes.append(
            string_env.from_string(raw).render(
                name=ctx.name,
                pkg_name=ctx.pkg_name,
                template=ctx.template,
                addons=ctx.addons,
            )
        )

    vars: dict = {
        "name": ctx.name,
        "pkg_name": ctx.pkg_name,
        "template": ctx.template,
        "addons": ctx.addons,
        "extra_deps": contributions.deps,
        "extra_dev_deps": contributions.dev_deps,
        "extra_just_recipes": rendered_recipes,
    }

    for template_name, dest_rel in [
        ("pyproject.toml.j2", "pyproject.toml"),
        ("justfile.j2", "justfile"),
    ]:
        content = env.get_template(template_name).render(**vars)
        ctx.write_file(dest_rel, content)
        if not ctx.dry_run:
            success(dest_rel)
