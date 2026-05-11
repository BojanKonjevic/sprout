"""Functional integration tests — scaffolded projects must be runnable.

These tests scaffold real projects and then execute commands inside them,
verifying that the generated output is not just syntactically present but
actually works.  They are slower than the structural tests in test_integration.py
and are marked with @pytest.mark.slow.

Run with:   uv run pytest tests/test_functional.py -v
Skip with:  uv run pytest -m "not slow"
"""

from __future__ import annotations

import os
import secrets
import subprocess
from pathlib import Path

import pytest
from conftest import SCAFFOLDER_ROOT

from scaffolder._apply_loader import load_apply
from scaffolder.addons._registry import get_available_addons
from scaffolder.apply import apply_contributions
from scaffolder.collect import collect_all
from scaffolder.context import Context
from scaffolder.generate import generate_all
from scaffolder.git import init_and_commit
from scaffolder.templates._load_config import load_template_config

pytestmark = pytest.mark.slow


# ── scaffold helper (duplicated from test_integration.py to keep modules independent) ──


def _scaffold(tmp_path: Path, name: str, template: str, addons: list[str]) -> Path:
    project_dir = tmp_path / name
    project_dir.mkdir(parents=True)
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
    selected_addon_configs = [cfg for cfg in available if cfg.id in addons]

    secret_key = secrets.token_hex(32) if template == "fastapi" else None

    render_vars: dict[str, object] = {
        "name": name,
        "pkg_name": pkg_name,
        "template": template,
        "secret_key": secret_key or "change-me",
        "has_postgres": template == "fastapi",
        "has_redis": "redis" in addons,
    }

    contributions = collect_all(template_config, selected_addon_configs)
    apply_contributions(
        ctx, contributions, template_config.extension_points, render_vars
    )
    generate_all(ctx, template_config, contributions)
    init_and_commit(project_dir)

    return project_dir


def _uv(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    """Run a uv command in the given directory and return the result."""
    env = os.environ.copy()
    # Propagate NixOS settings if present
    return subprocess.run(
        ["uv", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


# ── blank template ────────────────────────────────────────────────────────────


class TestBlankFunctional:
    def test_uv_sync_succeeds(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapp", "blank", [])
        result = _uv("sync", "--quiet", cwd=project_dir)
        assert result.returncode == 0, f"uv sync failed:\n{result.stderr}"

    def test_pytest_passes(self, tmp_path):
        """The generated blank project's test suite must pass out of the box."""
        project_dir = _scaffold(tmp_path, "myapp", "blank", [])
        _uv("sync", "--quiet", cwd=project_dir)
        result = _uv("run", "pytest", "-v", cwd=project_dir)
        assert result.returncode == 0, (
            f"pytest failed in scaffolded blank project:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    def test_pytest_output_contains_test_name(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapp", "blank", [])
        _uv("sync", "--quiet", cwd=project_dir)
        result = _uv("run", "pytest", "-v", cwd=project_dir)
        assert "test_main" in result.stdout

    def test_ruff_check_passes(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapp", "blank", [])
        _uv("sync", "--quiet", cwd=project_dir)
        result = _uv("run", "ruff", "check", ".", cwd=project_dir)
        assert result.returncode == 0, (
            f"ruff check failed in scaffolded blank project:\n{result.stdout}\n{result.stderr}"
        )

    def test_ruff_format_check_passes(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapp", "blank", [])
        _uv("sync", "--quiet", cwd=project_dir)
        result = _uv("run", "ruff", "format", "--check", ".", cwd=project_dir)
        assert result.returncode == 0, (
            f"ruff format --check failed:\n{result.stdout}\n{result.stderr}"
        )

    def test_hyphenated_name_pytest_passes(self, tmp_path):
        """Hyphenated project names convert to underscore pkg — tests must still work."""
        project_dir = _scaffold(tmp_path, "my-cool-app", "blank", [])
        _uv("sync", "--quiet", cwd=project_dir)
        result = _uv("run", "pytest", "-v", cwd=project_dir)
        assert result.returncode == 0, (
            f"pytest failed for hyphenated project name:\n{result.stdout}\n{result.stderr}"
        )

    def test_main_module_is_runnable(self, tmp_path):
        """python -m myapp must run without errors (it just prints)."""
        project_dir = _scaffold(tmp_path, "myapp", "blank", [])
        _uv("sync", "--quiet", cwd=project_dir)
        result = _uv("run", "python", "-m", "myapp", cwd=project_dir)
        assert result.returncode == 0, (
            f"python -m myapp failed:\n{result.stdout}\n{result.stderr}"
        )
        assert "Hello from myapp" in result.stdout


# ── blank + docker ────────────────────────────────────────────────────────────


class TestBlankDockerFunctional:
    def test_uv_sync_succeeds(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapp", "blank", ["docker"])
        result = _uv("sync", "--quiet", cwd=project_dir)
        assert result.returncode == 0, f"uv sync failed:\n{result.stderr}"

    def test_pytest_passes(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapp", "blank", ["docker"])
        _uv("sync", "--quiet", cwd=project_dir)
        result = _uv("run", "pytest", "-v", cwd=project_dir)
        assert result.returncode == 0, (
            f"pytest failed in blank+docker project:\n{result.stdout}\n{result.stderr}"
        )

    def test_ruff_passes(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapp", "blank", ["docker"])
        _uv("sync", "--quiet", cwd=project_dir)
        result = _uv("run", "ruff", "check", ".", cwd=project_dir)
        assert result.returncode == 0, f"ruff failed:\n{result.stdout}"


# ── template rendering correctness ────────────────────────────────────────────


class TestRenderedContentCorrectness:
    """Verify that Jinja2 variables are fully resolved in generated files.

    These don't require uv/pytest to be installed — they just inspect content.
    """

    def test_no_unrendered_jinja_in_blank_main(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapp", "blank", [])
        main = (project_dir / "src" / "myapp" / "main.py").read_text()
        assert "((" not in main
        assert "))" not in main

    def test_no_unrendered_jinja_in_blank_test(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapp", "blank", [])
        test = (project_dir / "tests" / "test_main.py").read_text()
        assert "((" not in test
        assert "))" not in test

    def test_no_unrendered_jinja_in_pyproject(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapp", "blank", [])
        pyproject = (project_dir / "pyproject.toml").read_text()
        assert "((" not in pyproject
        assert "))" not in pyproject

    def test_no_unrendered_jinja_in_justfile(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapp", "blank", [])
        justfile = (project_dir / "justfile").read_text()
        assert "((" not in justfile
        assert "))" not in justfile

    def test_no_unrendered_jinja_in_fastapi_main(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapi", "fastapi", ["docker"])
        main = (project_dir / "src" / "myapi" / "main.py").read_text()
        assert "((" not in main

    def test_no_unrendered_jinja_in_fastapi_settings(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapi", "fastapi", ["docker"])
        settings = (project_dir / "src" / "myapi" / "settings.py").read_text()
        assert "((" not in settings

    def test_no_unrendered_jinja_in_alembic_ini(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapi", "fastapi", ["docker"])
        alembic_ini = (project_dir / "alembic.ini").read_text()
        assert "((" not in alembic_ini

    def test_no_unrendered_jinja_in_env_file(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapi", "fastapi", ["docker"])
        env = (project_dir / ".env").read_text()
        assert "((" not in env

    def test_no_unrendered_jinja_in_github_actions_ci(self, tmp_path):
        project_dir = _scaffold(
            tmp_path, "myapi", "fastapi", ["docker", "redis", "github-actions"]
        )
        ci = (project_dir / ".github" / "workflows" / "ci.yml").read_text()
        assert "((" not in ci

    def test_no_unrendered_jinja_in_celery_app(self, tmp_path):
        project_dir = _scaffold(
            tmp_path, "myapi", "fastapi", ["docker", "redis", "celery"]
        )
        celery_app = (
            project_dir / "src" / "myapi" / "tasks" / "celery_app.py"
        ).read_text()
        assert "((" not in celery_app

    def test_no_unrendered_block_tags_in_blank(self, tmp_path):
        """[% %] tags must not appear in any generated file."""
        project_dir = _scaffold(tmp_path, "myapp", "blank", [])
        for f in project_dir.rglob("*"):
            if f.is_file() and f.suffix in (
                ".py",
                ".toml",
                ".yml",
                ".yaml",
                ".cfg",
                ".ini",
                ".txt",
            ):
                text = f.read_text(errors="replace")
                assert "[% " not in text and " %]" not in text, (
                    f"Unrendered block tag found in {f.relative_to(project_dir)}"
                )

    def test_no_unrendered_block_tags_in_fastapi(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapi", "fastapi", ["docker"])
        for f in project_dir.rglob("*"):
            if f.is_file() and f.suffix in (".py", ".toml", ".yml", ".yaml", ".cfg"):
                text = f.read_text(errors="replace")
                assert "[% " not in text and " %]" not in text, (
                    f"Unrendered block tag found in {f.relative_to(project_dir)}"
                )

    def test_project_name_correctly_substituted_in_all_files(self, tmp_path):
        """Every occurrence of '(( name ))' should be replaced with the project name."""
        project_dir = _scaffold(tmp_path, "uniquename", "blank", [])
        for f in project_dir.rglob("*"):
            if f.is_file():
                text = f.read_text(errors="replace")
                assert "(( name ))" not in text, (
                    f"Unrendered (( name )) found in {f.relative_to(project_dir)}"
                )

    def test_pkg_name_placeholder_fully_resolved_in_file_contents(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapp", "blank", [])
        for f in project_dir.rglob("*.py"):
            text = f.read_text(errors="replace")
            assert "(( pkg_name ))" not in text, (
                f"Unrendered (( pkg_name )) in {f.relative_to(project_dir)}"
            )


# ── mypy type checking ────────────────────────────────────────────────────────


class TestMypyFunctional:
    def test_mypy_passes_on_blank(self, tmp_path):
        project_dir = _scaffold(tmp_path, "myapp", "blank", [])
        _uv("sync", "--quiet", cwd=project_dir)
        result = _uv("run", "mypy", "src/", cwd=project_dir)
        assert result.returncode == 0, (
            f"mypy failed on blank project:\n{result.stdout}\n{result.stderr}"
        )
