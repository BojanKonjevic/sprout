from pathlib import Path

import jinja2

from scaffolder.context import Context
from scaffolder.ui import step, success


def _make_env(templates_dir: Path) -> jinja2.Environment:
    # Use (( )) for variables, [% %] for blocks — avoids conflicts with:
    #   - Nix's  ${...}  interpolation
    #   - just's {{...}} template syntax
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        keep_trailing_newline=True,
        variable_start_string="((",
        variable_end_string="))",
        block_start_string="[%",
        block_end_string="%]",
    )


def generate_all(ctx: Context) -> None:
    step("Generating config files")
    env = _make_env(ctx.scaffolder_root / "generate")
    vars = {"name": ctx.name, "pkg_name": ctx.pkg_name, "template": ctx.template}

    for template_name, dest in [
        ("pyproject.toml.j2", Path("pyproject.toml")),
        ("justfile.j2", Path("justfile")),
        ("flake.nix.j2", Path("flake.nix")),
    ]:
        dest.write_text(env.get_template(template_name).render(**vars))
        success(str(dest))
