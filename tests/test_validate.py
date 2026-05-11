"""Tests for scaffolder.validate — name validation and addon dependency checks."""

import pytest
from click.exceptions import Exit as ClickExit

from scaffolder.schema import AddonConfig
from scaffolder.validate import validate_addon_deps, validate_name
from conftest import ExitAssertion


def _assert_exits(fn, *args, **kwargs) -> None:
    """Assert that calling ``fn(*args, **kwargs)`` raises ``typer.Exit(1)``."""
    with ExitAssertion():
        fn(*args, **kwargs)


def test_validate_name_accepts_simple_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    validate_name("my-project", "my_project")


def test_validate_name_accepts_underscores(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    validate_name("my_project", "my_project")


def test_validate_name_accepts_alphanumeric(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    validate_name("project123", "project123")


def test_validate_name_rejects_existing_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "myproject").mkdir()
    _assert_exits(validate_name, "myproject", "myproject")


def test_validate_name_rejects_leading_digit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _assert_exits(validate_name, "1project", "1project")


def test_validate_name_rejects_hyphen_start(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _assert_exits(validate_name, "-project", "_project")


def test_validate_name_rejects_special_characters(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _assert_exits(validate_name, "my project", "my project")


def test_validate_name_rejects_stdlib_module(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _assert_exits(validate_name, "json", "json")


def test_validate_name_rejects_stdlib_module_os(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _assert_exits(validate_name, "os", "os")


def test_validate_name_rejects_empty_string(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _assert_exits(validate_name, "", "")


# ── validate_addon_deps ───────────────────────────────────────────────────────


def _make_addon(id: str, requires: list[str]) -> AddonConfig:
    return AddonConfig(id=id, description="", requires=requires)


def test_validate_addon_deps_passes_when_all_satisfied():
    available = [
        _make_addon("redis", []),
        _make_addon("celery", ["redis"]),
    ]
    validate_addon_deps(["redis", "celery"], available)


def test_validate_addon_deps_passes_with_no_addons():
    available = [_make_addon("redis", []), _make_addon("celery", ["redis"])]
    validate_addon_deps([], available)


def test_validate_addon_deps_passes_with_no_requirements():
    available = [_make_addon("docker", []), _make_addon("github-actions", [])]
    validate_addon_deps(["docker", "github-actions"], available)


def test_validate_addon_deps_fails_when_requirement_missing():
    available = [
        _make_addon("redis", []),
        _make_addon("celery", ["redis"]),
    ]
    _assert_exits(validate_addon_deps, ["celery"], available)


def test_validate_addon_deps_fails_for_transitive_missing():
    available = [
        _make_addon("redis", []),
        _make_addon("celery", ["redis"]),
        _make_addon("docker", []),
    ]
    _assert_exits(validate_addon_deps, ["docker", "celery"], available)


def test_validate_addon_deps_passes_single_addon_no_requires():
    available = [_make_addon("sentry", [])]
    validate_addon_deps(["sentry"], available)
