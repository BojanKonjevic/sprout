"""Tests for scaffolder.add — adding addons to existing projects."""

from __future__ import annotations

import os
import re
import secrets
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from scaffolder._apply_loader import load_apply
from scaffolder.add import add_addon, add_addon_interactive
from scaffolder.addons._registry import get_available_addons
from scaffolder.apply import apply_contributions
from scaffolder.collect import collect_all
from scaffolder.context import Context
from scaffolder.generate import generate_all
from scaffolder.git import init_and_commit
from scaffolder.lockfile import write_lockfile
from scaffolder.prompt._single import prompt_single_addon
from scaffolder.remove import remove_addon
from scaffolder.templates._load_config import load_template_config

SCAFFOLDER_ROOT = Path(__file__).parent.parent / "src" / "scaffolder"


@contextmanager
def suppress_stdin():
    try:
        with open(os.devnull) as devnull:
            old_stdin = os.dup(0)
            try:
                os.dup2(devnull.fileno(), 0)
                yield
            finally:
                os.dup2(old_stdin, 0)
                os.close(old_stdin)
    except OSError:
        yield


def _scaffold(tmp_path: Path, name: str, template: str, addons: list[str]) -> Path:
    project_dir = tmp_path / name
    project_dir.mkdir()
    pkg_name = name.replace("-", "_")

    ctx = Context(
        name=name,
        pkg_name=pkg_name,
        template=template,
        addons=addons,
        scaffolder_root=SCAFFOLDER_ROOT,
        project_dir=project_dir,
    )

    load_apply(SCAFFOLDER_ROOT / "templates" / "_common" / "apply.py")(ctx)

    available = get_available_addons()
    template_config = load_template_config(SCAFFOLDER_ROOT, template)
    selected = [c for c in available if c.id in addons]
    render_vars: dict[str, object] = {
        "name": name,
        "pkg_name": pkg_name,
        "template": template,
        "secret_key": secrets.token_hex(32) if template == "fastapi" else "change-me",
        "has_postgres": template == "fastapi",
        "has_redis": "redis" in addons,
    }

    contributions = collect_all(template_config, selected)
    apply_contributions(
        ctx, contributions, template_config.extension_points, render_vars
    )
    generate_all(ctx, template_config, contributions)

    init_and_commit(project_dir)
    write_lockfile(project_dir, template, addons)
    return project_dir


# ── pyproject.toml multiline format ───────────────────────────────────────────


class TestPyprojectFormatPreservation:
    """After a remove+add cycle, deps must remain one-per-line."""

    def _dep_lines(self, project_dir: Path) -> list[str]:
        """Return lines inside the [project] dependencies = [...] block."""

        text = (project_dir / "pyproject.toml").read_text()
        marker = "dependencies = ["
        idx = text.index(marker)
        # Find the closing ] at the start of a line (not ] inside dep strings like uvicorn[standard])
        m = re.search(r"^\]", text[idx:], re.MULTILINE)
        assert m is not None
        end = idx + m.start()
        inside = text[idx:end]
        return [
            line.strip() for line in inside.splitlines() if line.strip().startswith('"')
        ]

    def test_remove_leaves_deps_multiline(self, tmp_path, monkeypatch):

        project_dir = _scaffold(tmp_path, "myapp", "blank", ["docker", "redis"])
        monkeypatch.chdir(project_dir)

        with suppress_stdin():
            remove_addon("redis", project_dir=project_dir)

        dep_lines = self._dep_lines(project_dir)
        assert len(dep_lines) >= 1, "Expected at least one dep line"
        # Each line should hold exactly one dep string
        for line in dep_lines:
            assert line.count('"') == 2, f"Multiple deps on one line: {line!r}"

    def test_remove_then_add_deps_still_multiline(self, tmp_path, monkeypatch):

        project_dir = _scaffold(tmp_path, "myapp", "blank", ["docker", "redis"])
        monkeypatch.chdir(project_dir)

        with suppress_stdin():
            remove_addon("redis", project_dir=project_dir)
        with suppress_stdin():
            add_addon("redis")

        dep_lines = self._dep_lines(project_dir)
        assert any("redis" in line for line in dep_lines), (
            "redis dep missing after re-add"
        )
        for line in dep_lines:
            assert line.count('"') == 2, (
                f"Multiple deps collapsed onto one line: {line!r}"
            )

    def test_readded_dep_is_present_and_on_its_own_line(self, tmp_path, monkeypatch):

        project_dir = _scaffold(tmp_path, "myapp", "blank", ["docker", "redis"])
        monkeypatch.chdir(project_dir)

        with suppress_stdin():
            remove_addon("redis", project_dir=project_dir)
        with suppress_stdin():
            add_addon("redis")

        lines = (project_dir / "pyproject.toml").read_text().splitlines()
        redis_lines = [line.strip() for line in lines if '"redis>=5"' in line]
        assert len(redis_lines) == 1, (
            f"Expected exactly one 'redis>=5' line, got: {redis_lines}"
        )

    def test_dev_deps_also_stay_multiline_after_remove_add(self, tmp_path, monkeypatch):
        """Dev deps array should also be multiline after a remove+add cycle."""

        project_dir = _scaffold(tmp_path, "myapp", "blank", ["docker", "redis"])
        monkeypatch.chdir(project_dir)

        with suppress_stdin():
            remove_addon("redis", project_dir=project_dir)
        with suppress_stdin():
            add_addon("redis")

        text = (project_dir / "pyproject.toml").read_text()
        dev_block_start = text.index("[dependency-groups]")
        dev_block = text[dev_block_start : text.index("]", dev_block_start)]
        dev_lines = [
            line.strip()
            for line in dev_block.splitlines()
            if line.strip().startswith('"')
        ]
        for line in dev_lines:
            assert line.count('"') == 2, f"Multiple dev deps on one line: {line!r}"

    def test_full_fastapi_remove_add_cycle(self, tmp_path, monkeypatch):
        """Celery remove+add on a full fastapi project preserves multiline deps."""

        project_dir = _scaffold(
            tmp_path,
            "myapi",
            "fastapi",
            ["docker", "redis", "celery", "sentry", "github-actions"],
        )
        monkeypatch.chdir(project_dir)

        with suppress_stdin():
            remove_addon("celery", project_dir=project_dir)
        with suppress_stdin():
            add_addon("celery")

        dep_lines = self._dep_lines(project_dir)
        assert any("celery" in line for line in dep_lines), (
            "celery missing after re-add"
        )
        for line in dep_lines:
            assert line.count('"') == 2, f"Deps collapsed to one line: {line!r}"


# ── "Already installed" message deduplication ────────────────────────────────


class TestAlreadyInstalledMessage:
    """The 'Already installed' header must appear exactly once in add output."""

    def test_prompt_single_addon_does_not_print_already_installed(self, capsys):
        """prompt_single_addon is a selection widget; the caller owns the header."""

        items = [
            ("docker", "Docker description", []),
            ("redis", "Redis description", []),
        ]

        # Run in non-tty fallback mode; stub input to cancel immediately
        with (
            patch("scaffolder.prompt._keys.tty_available", return_value=False),
            patch("builtins.input", return_value=""),
        ):
            prompt_single_addon(items)

        out = capsys.readouterr().out
        assert "Already installed" not in out, (
            "prompt_single_addon must not print 'Already installed' — "
            "that's _add_interactive's responsibility"
        )

    def test_add_interactive_prints_already_installed_once(
        self, tmp_path, monkeypatch, capsys
    ):
        project_dir = _scaffold(tmp_path, "myapp", "blank", ["docker"])
        monkeypatch.chdir(project_dir)

        # Non-tty fallback: input="" → no addon selected → returns cleanly
        with (
            patch("scaffolder.prompt._keys.tty_available", return_value=False),
            patch("builtins.input", return_value=""),
        ):
            add_addon_interactive()

        out = capsys.readouterr().out
        assert out.count("Already installed") == 1, (
            f"Expected 'Already installed' exactly once, got:\n{out}"
        )
