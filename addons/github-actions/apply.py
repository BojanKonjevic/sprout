"""GitHub Actions addon — CI workflow for lint, type-check, and test."""

from pathlib import Path

from scaffolder.context import Context
from scaffolder.render import make_env
from scaffolder.ui import success

_HERE = Path(__file__).parent


def apply(ctx: Context) -> None:
    workflows_dir = Path(".github") / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    env = make_env(_HERE / "files")

    Path(workflows_dir / "ci.yml").write_text(
        env.get_template("ci.yml.j2").render(
            name=ctx.name,
            pkg_name=ctx.pkg_name,
            template=ctx.template,
            has_redis=ctx.has("redis"),
            has_postgres=ctx.template == "fastapi",
        )
    )

    success(".github/workflows/ci.yml")
