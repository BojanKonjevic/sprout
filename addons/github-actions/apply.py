"""GitHub Actions addon — CI workflow for lint, type-check, and test."""

from pathlib import Path

import jinja2

from scaffolder.context import Context
from scaffolder.ui import success

_HERE = Path(__file__).parent


def apply(ctx: Context) -> None:
    files = _HERE / "files"

    workflows_dir = Path(".github") / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(files)),
        keep_trailing_newline=True,
    )

    Path(workflows_dir / "ci.yml").write_text(
        env.get_template("ci.yml.j2").render(
            name=ctx.name,
            pkg_name=ctx.pkg_name,
            template=ctx.template,
            has_redis="redis" in ctx.addons,
            has_postgres=ctx.template == "fastapi",
        )
    )

    success(".github/workflows/ci.yml")
