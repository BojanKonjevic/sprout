from pathlib import Path

from scaffolder.context import Context
from scaffolder.render import make_env
from scaffolder.ui import success

_HERE = Path(__file__).parent


def apply(ctx: Context) -> None:
    wf_dir = ".github/workflows"
    ctx.create_dir(wf_dir)

    env = make_env(_HERE / "files")
    content = env.get_template("ci.yml.j2").render(
        name=ctx.name,
        pkg_name=ctx.pkg_name,
        template=ctx.template,
        has_redis=ctx.has("redis"),
        has_postgres=ctx.template == "fastapi",
    )
    ctx.write_file(f"{wf_dir}/ci.yml", content)

    success(".github/workflows/ci.yml")
