"""Tests for scaffolder.assembler.apply_contributions.

This is the most complex function in the codebase and was previously untested.
It writes files, applies handler-based injections, merges compose services,
and patches .env / .env.example.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from conftest import SCAFFOLDER_ROOT

from scaffolder.core.apply import (
    _merge_compose_volumes,
    _merge_env_vars,
    apply_contributions,
)
from scaffolder.core.context import Context
from scaffolder.schema.models import (
    AddonConfig,
    AddonHooks,
    ComposeService,
    Contributions,
    EnvVar,
    FileContribution,
)

# ── helpers ───────────────────────────────────────────────────────────────────


def _ctx(tmp_path: Path, name: str = "myapp") -> Context:
    project_dir = tmp_path / name
    project_dir.mkdir()
    return Context(
        name=name,
        pkg_name=name.replace("-", "_"),
        template="blank",
        addons=[],
        scaffolder_root=SCAFFOLDER_ROOT,
        project_dir=project_dir,
    )


def _render_vars(ctx: Context, **extra: object) -> dict[str, object]:
    return {
        "name": ctx.name,
        "pkg_name": ctx.pkg_name,
        "template": ctx.template,
        "secret_key": "test-secret",
        "has_postgres": False,
        "has_redis": False,
        **extra,
    }


def _empty_contributions() -> Contributions:
    return Contributions()


# ── file writing ──────────────────────────────────────────────────────────────


def test_inline_content_file_is_written(tmp_path):
    ctx = _ctx(tmp_path)
    contributions = Contributions(
        files=[FileContribution(dest="hello.txt", content="hello world\n")]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))
    assert (ctx.project_dir / "hello.txt").read_text() == "hello world\n"


def test_inline_template_file_is_rendered(tmp_path):
    ctx = _ctx(tmp_path)
    contributions = Contributions(
        files=[
            FileContribution(
                dest="out.txt",
                content="project=(( name ))\npkg=(( pkg_name ))",
                template=True,
            )
        ]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))
    text = (ctx.project_dir / "out.txt").read_text()
    assert "project=myapp" in text
    assert "pkg=myapp" in text


def test_pkg_name_placeholder_in_dest_is_expanded(tmp_path):
    ctx = _ctx(tmp_path)
    contributions = Contributions(
        files=[FileContribution(dest="src/{{pkg_name}}/mod.py", content="")]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))
    assert (ctx.project_dir / "src" / "myapp" / "mod.py").exists()


def test_hyphenated_name_pkg_placeholder(tmp_path):
    ctx = _ctx(tmp_path, name="my-app")
    contributions = Contributions(
        files=[FileContribution(dest="src/{{pkg_name}}/__init__.py", content="")]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))
    assert (ctx.project_dir / "src" / "my_app" / "__init__.py").exists()


def test_source_file_is_copied(tmp_path):
    ctx = _ctx(tmp_path)
    source = tmp_path / "source.txt"
    source.write_text("copied content")
    contributions = Contributions(
        files=[FileContribution(dest="out.txt", source=str(source))]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))
    assert (ctx.project_dir / "out.txt").read_text() == "copied content"


def test_source_template_file_is_rendered(tmp_path):
    ctx = _ctx(tmp_path)
    source = tmp_path / "tmpl.txt.j2"
    source.write_text("hello (( name ))!")
    contributions = Contributions(
        files=[FileContribution(dest="out.txt", source=str(source), template=True)]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))
    assert (ctx.project_dir / "out.txt").read_text() == "hello myapp!"


def test_dir_creation(tmp_path):
    ctx = _ctx(tmp_path)
    contributions = Contributions(dirs=["src/{{pkg_name}}/sub", "tests"])
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))
    assert (ctx.project_dir / "src" / "myapp" / "sub").is_dir()
    assert (ctx.project_dir / "tests").is_dir()


def test_source_path_must_be_absolute(tmp_path):
    ctx = _ctx(tmp_path)
    contributions = Contributions(
        files=[FileContribution(dest="out.txt", source="relative/path.txt")]
    )
    with pytest.raises(ValueError, match="absolute"):
        apply_contributions(ctx, contributions, {}, _render_vars(ctx))


# ── compose merging ───────────────────────────────────────────────────────────


def test_compose_service_is_merged(tmp_path):
    ctx = _ctx(tmp_path)
    compose_path = ctx.project_dir / "compose.yml"
    compose_path.write_text("services:\n  app:\n    image: myapp\n")

    contributions = Contributions(
        compose_services=[
            ComposeService(name="redis", image="redis:7-alpine", ports=["6379:6379"])
        ]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))

    data = yaml.safe_load(compose_path.read_text())
    assert "redis" in data["services"]
    assert data["services"]["redis"]["image"] == "redis:7-alpine"
    assert data["services"]["redis"]["ports"] == ["6379:6379"]


def test_compose_service_not_overwritten_if_already_exists(tmp_path):
    ctx = _ctx(tmp_path)
    compose_path = ctx.project_dir / "compose.yml"
    compose_path.write_text("services:\n  redis:\n    image: redis:6\n")

    contributions = Contributions(
        compose_services=[ComposeService(name="redis", image="redis:7-alpine")]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))

    data = yaml.safe_load(compose_path.read_text())
    # Original should be preserved
    assert data["services"]["redis"]["image"] == "redis:6"


def test_compose_volume_is_merged(tmp_path):
    ctx = _ctx(tmp_path)
    compose_path = ctx.project_dir / "compose.yml"
    compose_path.write_text("services:\n  app:\n    image: x\n")

    contributions = Contributions(
        compose_services=[ComposeService(name="redis", image="redis:7-alpine")],
        compose_volumes=["redis-data"],
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))

    data = yaml.safe_load(compose_path.read_text())
    assert "redis-data" in data.get("volumes", {})


def test_compose_skipped_when_no_compose_yml(tmp_path):
    ctx = _ctx(tmp_path)
    contributions = Contributions(
        compose_services=[ComposeService(name="redis", image="redis:7-alpine")]
    )
    # Should not raise even though compose.yml doesn't exist
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))


def test_compose_service_pkg_name_in_command(tmp_path):
    ctx = _ctx(tmp_path)
    compose_path = ctx.project_dir / "compose.yml"
    compose_path.write_text("services:\n  app:\n    image: x\n")

    contributions = Contributions(
        compose_services=[
            ComposeService(
                name="worker",
                build=".",
                command="celery -A {{pkg_name}}.tasks worker",
            )
        ]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))

    data = yaml.safe_load(compose_path.read_text())
    assert "myapp.tasks" in data["services"]["worker"]["command"]
    assert "{{pkg_name}}" not in data["services"]["worker"]["command"]


def test_compose_service_pkg_name_in_environment(tmp_path):
    ctx = _ctx(tmp_path)
    compose_path = ctx.project_dir / "compose.yml"
    compose_path.write_text("services:\n  app:\n    image: x\n")

    contributions = Contributions(
        compose_services=[
            ComposeService(
                name="worker",
                build=".",
                environment={"APP_MODULE": "{{pkg_name}}.main:app"},
            )
        ]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))

    data = yaml.safe_load(compose_path.read_text())
    assert data["services"]["worker"]["environment"]["APP_MODULE"] == "myapp.main:app"


def test_multiple_compose_services_merged(tmp_path):
    ctx = _ctx(tmp_path)
    compose_path = ctx.project_dir / "compose.yml"
    compose_path.write_text("services:\n  app:\n    image: x\n")

    contributions = Contributions(
        compose_services=[
            ComposeService(name="redis", image="redis:7-alpine"),
            ComposeService(name="worker", build="."),
        ]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))

    data = yaml.safe_load(compose_path.read_text())
    assert "redis" in data["services"]
    assert "worker" in data["services"]


# ── post_apply hook ───────────────────────────────────────────────────────────


def test_post_apply_hook_is_called(tmp_path):
    ctx = _ctx(tmp_path)
    calls: list[str] = []

    def my_post_apply(c: Context) -> None:
        calls.append("called")

    hooks = AddonHooks(post_apply=my_post_apply)
    addon = AddonConfig(id="fake", description="")
    addon._module = hooks

    contributions = Contributions(_addon_configs=[addon])
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))

    assert calls == ["called"]


def test_post_apply_hook_not_required(tmp_path):
    ctx = _ctx(tmp_path)

    hooks = AddonHooks()  # all fields are None by default
    addon = AddonConfig(id="fake", description="")
    addon._module = hooks

    contributions = Contributions(_addon_configs=[addon])
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))
    # Should not raise


# ── _merge_env_vars unit tests ────────────────────────────────────────────────


def test_merge_env_vars_multiple_keys(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("X=1\n# [zenit: env_vars]\n")
    _merge_env_vars(
        env_path,
        [
            EnvVar(key="A", default="1"),
            EnvVar(key="B", default="2"),
        ],
    )
    text = env_path.read_text()
    assert "A=1" in text
    assert "B=2" in text


# ── _merge_compose_volumes unit tests ────────────────────────────────────────


def test_merge_compose_volumes_idempotent(tmp_path):
    compose_path = tmp_path / "compose.yml"
    compose_path.write_text("services: {}\nvolumes:\n  existing-vol:\n")
    _merge_compose_volumes(compose_path.parent, ["existing-vol", "new-vol"])
    data = yaml.safe_load(compose_path.read_text())
    assert "existing-vol" in data["volumes"]
    assert "new-vol" in data["volumes"]
    # existing-vol should appear exactly once
    assert list(data["volumes"].keys()).count("existing-vol") == 1
