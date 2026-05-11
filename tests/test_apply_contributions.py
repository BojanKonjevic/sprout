"""Tests for scaffolder.assembler.apply_contributions.

This is the most complex function in the codebase and was previously untested.
It writes files, applies sentinel-based injections, merges compose services,
and patches .env / .env.example.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from conftest import SCAFFOLDER_ROOT

from scaffolder.apply import (
    _apply_to_file,
    _merge_compose_volumes,
    _merge_env_vars,
    apply_contributions,
)
from scaffolder.context import Context
from scaffolder.schema import (
    AddonConfig,
    AddonHooks,
    ComposeService,
    Contributions,
    EnvVar,
    ExtensionPoint,
    FileContribution,
    Injection,
    InjectionMode,
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


def _no_extension_points() -> dict[str, ExtensionPoint]:
    return {}


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


# ── injections ────────────────────────────────────────────────────────────────


def test_injection_after_sentinel(tmp_path):
    ctx = _ctx(tmp_path)
    target = ctx.project_dir / "main.py"
    target.write_text("def main():\n    # [sentinel]\n    pass\n")

    extension_points = {
        "startup": ExtensionPoint(
            file="main.py",
            sentinel="    # [sentinel]",
            mode=InjectionMode.AFTER_SENTINEL,
        )
    }
    contributions = Contributions(
        injections=[Injection(point="startup", content="    do_something()")]
    )
    apply_contributions(ctx, contributions, extension_points, _render_vars(ctx))

    text = target.read_text()
    assert "    # [sentinel]\n    do_something()" in text


def test_injection_append_mode(tmp_path):
    ctx = _ctx(tmp_path)
    target = ctx.project_dir / "settings.py"
    target.write_text("class Settings:\n    # [sentinel]\n    x: int = 1\n")

    extension_points = {
        "fields": ExtensionPoint(
            file="settings.py",
            sentinel="    # [sentinel]",
            mode=InjectionMode.APPEND,
        )
    }
    contributions = Contributions(
        injections=[Injection(point="fields", content="    y: str = 'hello'")]
    )
    apply_contributions(ctx, contributions, extension_points, _render_vars(ctx))

    text = target.read_text()
    # In APPEND mode the content is appended at the end of the file
    assert "    y: str = 'hello'" in text


def test_injection_skipped_when_sentinel_missing(tmp_path):
    ctx = _ctx(tmp_path)
    target = ctx.project_dir / "main.py"
    target.write_text("def main(): pass\n")

    extension_points = {
        "startup": ExtensionPoint(
            file="main.py",
            sentinel="    # [missing-sentinel]",
        )
    }
    contributions = Contributions(
        injections=[Injection(point="startup", content="    injected()")]
    )
    apply_contributions(ctx, contributions, extension_points, _render_vars(ctx))

    assert "injected" not in target.read_text()


def test_injection_skipped_when_file_missing(tmp_path):
    ctx = _ctx(tmp_path)
    extension_points = {
        "startup": ExtensionPoint(file="nonexistent.py", sentinel="# sentinel")
    }
    contributions = Contributions(
        injections=[Injection(point="startup", content="injected()")]
    )
    # Should not raise; missing file is silently skipped
    apply_contributions(ctx, contributions, extension_points, _render_vars(ctx))


def test_injection_skipped_when_extension_point_not_registered(tmp_path):
    ctx = _ctx(tmp_path)
    target = ctx.project_dir / "main.py"
    target.write_text("# [sentinel]\n")

    contributions = Contributions(
        injections=[Injection(point="unknown_point", content="injected()")]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))

    assert "injected" not in target.read_text()


def test_multiple_injections_same_point_all_applied(tmp_path):
    ctx = _ctx(tmp_path)
    target = ctx.project_dir / "lifecycle.py"
    target.write_text("# startup:\n    # [sentinel]\n")

    extension_points = {
        "startup": ExtensionPoint(
            file="lifecycle.py",
            sentinel="    # [sentinel]",
            mode=InjectionMode.AFTER_SENTINEL,
        )
    }
    contributions = Contributions(
        injections=[
            Injection(point="startup", content="    init_a()"),
            Injection(point="startup", content="    init_b()"),
        ]
    )
    apply_contributions(ctx, contributions, extension_points, _render_vars(ctx))

    text = target.read_text()
    assert "init_a()" in text
    assert "init_b()" in text


def test_injection_pkg_name_in_file_path(tmp_path):
    ctx = _ctx(tmp_path)
    (ctx.project_dir / "src" / "myapp").mkdir(parents=True)
    target = ctx.project_dir / "src" / "myapp" / "lifecycle.py"
    target.write_text("    # [sentinel]\n")

    extension_points = {
        "startup": ExtensionPoint(
            file="src/{{pkg_name}}/lifecycle.py",
            sentinel="    # [sentinel]",
            mode=InjectionMode.AFTER_SENTINEL,
        )
    }
    contributions = Contributions(
        injections=[Injection(point="startup", content="    go()")]
    )
    apply_contributions(ctx, contributions, extension_points, _render_vars(ctx))

    assert "go()" in target.read_text()


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


# ── env var merging ───────────────────────────────────────────────────────────


def test_env_var_appended_after_sentinel(tmp_path):
    ctx = _ctx(tmp_path)
    env_path = ctx.project_dir / ".env"
    env_path.write_text("DEBUG=false\n# [zenit: env_vars]\n")

    contributions = Contributions(
        env_vars=[EnvVar(key="REDIS_URL", default="redis://localhost:6379/0")]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))

    text = env_path.read_text()
    assert "REDIS_URL=redis://localhost:6379/0" in text


def test_env_var_with_comment(tmp_path):
    ctx = _ctx(tmp_path)
    env_path = ctx.project_dir / ".env"
    env_path.write_text("# [zenit: env_vars]\n")

    contributions = Contributions(
        env_vars=[EnvVar(key="SENTRY_DSN", default="", comment="Get from sentry.io")]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))

    text = env_path.read_text()
    assert "SENTRY_DSN=" in text
    assert "# Get from sentry.io" in text


def test_env_var_not_duplicated_if_already_present(tmp_path):
    ctx = _ctx(tmp_path)
    env_path = ctx.project_dir / ".env"
    env_path.write_text("REDIS_URL=redis://localhost:6379/0\n# [zenit: env_vars]\n")

    contributions = Contributions(
        env_vars=[EnvVar(key="REDIS_URL", default="redis://localhost:6379/0")]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))

    text = env_path.read_text()
    assert text.count("REDIS_URL=") == 1


def test_env_skipped_when_sentinel_missing(tmp_path):
    ctx = _ctx(tmp_path)
    env_path = ctx.project_dir / ".env"
    env_path.write_text("DEBUG=false\n")

    contributions = Contributions(
        env_vars=[EnvVar(key="REDIS_URL", default="redis://localhost:6379/0")]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))

    assert "REDIS_URL" not in env_path.read_text()


def test_env_example_also_patched(tmp_path):
    ctx = _ctx(tmp_path)
    for fname in (".env", ".env.example"):
        (ctx.project_dir / fname).write_text("# [zenit: env_vars]\n")

    contributions = Contributions(
        env_vars=[EnvVar(key="REDIS_URL", default="redis://localhost:6379/0")]
    )
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))

    assert "REDIS_URL=" in (ctx.project_dir / ".env").read_text()
    assert "REDIS_URL=" in (ctx.project_dir / ".env.example").read_text()


def test_env_skipped_when_no_env_files(tmp_path):
    ctx = _ctx(tmp_path)
    contributions = Contributions(
        env_vars=[EnvVar(key="REDIS_URL", default="redis://localhost:6379/0")]
    )
    # Should not raise even though .env doesn't exist
    apply_contributions(ctx, contributions, {}, _render_vars(ctx))


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


# ── _apply_to_file unit tests ─────────────────────────────────────────────────


def test_apply_to_file_after_sentinel(tmp_path):
    f = tmp_path / "target.py"
    f.write_text("before\n    # sentinel\nafter\n")
    ep = ExtensionPoint(
        file="target.py", sentinel="    # sentinel", mode=InjectionMode.AFTER_SENTINEL
    )
    _apply_to_file(f, ep, ["    injected()"])
    text = f.read_text()
    assert "    # sentinel\n    injected()\nafter" in text


def test_apply_to_file_append(tmp_path):
    f = tmp_path / "target.py"
    f.write_text("line1\n    # sentinel\nline3\n")
    ep = ExtensionPoint(
        file="target.py", sentinel="    # sentinel", mode=InjectionMode.APPEND
    )
    _apply_to_file(f, ep, ["appended line"])
    text = f.read_text()
    assert text.endswith("appended line\n")


def test_apply_to_file_noop_when_file_missing(tmp_path):
    f = tmp_path / "nonexistent.py"
    ep = ExtensionPoint(file="nonexistent.py", sentinel="# sentinel")
    # Should not raise
    _apply_to_file(f, ep, ["something"])


def test_apply_to_file_noop_when_sentinel_absent(tmp_path):
    f = tmp_path / "target.py"
    f.write_text("no sentinel here\n")
    ep = ExtensionPoint(
        file="target.py", sentinel="# MISSING", mode=InjectionMode.AFTER_SENTINEL
    )
    _apply_to_file(f, ep, ["injected"])
    assert "injected" not in f.read_text()


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
