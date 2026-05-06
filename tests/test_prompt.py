"""Tests for scaffolder.prompt fallback functions.

The TUI path requires a real terminal and is not tested here.
The fallback functions (``_fallback_template``, ``_fallback_addons``) run
whenever stdin is not a tty — e.g. in CI — and are plain input-parsing logic
that can be fully exercised by patching ``builtins.input``.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from scaffolder.prompt import _fallback_addons, _fallback_template

# ── _fallback_template ────────────────────────────────────────────────────────


def test_fallback_template_select_by_number_1():
    with patch("builtins.input", return_value="1"):
        assert _fallback_template() == "blank"


def test_fallback_template_select_by_number_2():
    with patch("builtins.input", return_value="2"):
        assert _fallback_template() == "fastapi"


def test_fallback_template_select_by_name_blank():
    with patch("builtins.input", return_value="blank"):
        assert _fallback_template() == "blank"


def test_fallback_template_select_by_name_fastapi():
    with patch("builtins.input", return_value="fastapi"):
        assert _fallback_template() == "fastapi"


def test_fallback_template_case_insensitive():
    with patch("builtins.input", return_value="BLANK"):
        assert _fallback_template() == "blank"


def test_fallback_template_retries_on_invalid_then_accepts():
    with patch("builtins.input", side_effect=["99", "1"]):
        assert _fallback_template() == "blank"


def test_fallback_template_retries_multiple_times():
    with patch("builtins.input", side_effect=["x", "y", "z", "2"]):
        assert _fallback_template() == "fastapi"


def test_fallback_template_eof_raises_system_exit():
    with patch("builtins.input", side_effect=EOFError):
        with pytest.raises(SystemExit) as exc_info:
            _fallback_template()
        assert exc_info.value.code == 0


def test_fallback_template_keyboard_interrupt_raises_system_exit():
    with patch("builtins.input", side_effect=KeyboardInterrupt):
        with pytest.raises(SystemExit) as exc_info:
            _fallback_template()
        assert exc_info.value.code == 0


# ── _fallback_addons helpers ──────────────────────────────────────────────────


def _items(*names: str) -> list[tuple[str, str]]:
    return [(n, f"{n} description") for n in names]


def _requires(*pairs: tuple[str, list[str]]) -> dict[str, list[str]]:
    return dict(pairs)


# ── _fallback_addons — empty / skip ──────────────────────────────────────────


def test_fallback_addons_empty_input_returns_only_locked():
    items = _items("docker", "redis", "celery")
    with patch("builtins.input", return_value=""):
        result = _fallback_addons(items, _requires(), always_locked_names={"docker"})
    assert result == ["docker"]


def test_fallback_addons_empty_input_no_locked_returns_empty():
    items = _items("docker", "redis")
    with patch("builtins.input", return_value=""):
        result = _fallback_addons(items, _requires(), always_locked_names=set())
    assert result == []


def test_fallback_addons_no_items_returns_locked_immediately():
    # When items is empty the function returns without prompting.
    result = _fallback_addons([], _requires(), always_locked_names={"docker"})
    assert result == ["docker"]


# ── _fallback_addons — selection by number ────────────────────────────────────


def test_fallback_addons_select_first():
    items = _items("docker", "redis", "celery")
    with patch("builtins.input", return_value="1"):
        result = _fallback_addons(items, _requires(), always_locked_names=set())
    assert "docker" in result


def test_fallback_addons_select_second():
    items = _items("docker", "redis", "celery")
    with patch("builtins.input", return_value="2"):
        result = _fallback_addons(items, _requires(), always_locked_names=set())
    assert "redis" in result


def test_fallback_addons_select_multiple():
    items = _items("docker", "redis", "sentry")
    with patch("builtins.input", return_value="1 3"):
        result = _fallback_addons(items, _requires(), always_locked_names=set())
    assert "docker" in result
    assert "sentry" in result
    assert "redis" not in result


def test_fallback_addons_always_locked_included_even_if_not_typed():
    items = _items("docker", "redis", "celery")
    with patch("builtins.input", return_value="2"):
        result = _fallback_addons(items, _requires(), always_locked_names={"docker"})
    assert "docker" in result
    assert "redis" in result


def test_fallback_addons_locked_not_duplicated():
    items = _items("docker", "redis")
    # Explicitly select docker (1) even though it is already locked.
    with patch("builtins.input", return_value="1"):
        result = _fallback_addons(items, _requires(), always_locked_names={"docker"})
    assert result.count("docker") == 1


# ── _fallback_addons — auto-selection of required addons ─────────────────────


def test_fallback_addons_auto_selects_required():
    items = _items("docker", "redis", "celery")
    requires = _requires(("celery", ["redis"]))
    with patch("builtins.input", return_value="3"):  # select celery
        result = _fallback_addons(items, requires, always_locked_names=set())
    assert "celery" in result
    assert "redis" in result  # auto-selected


def test_fallback_addons_auto_selects_only_direct_requirements():
    # _fallback_addons resolves one level deep only — it does not recurse.
    # Selecting celery pulls in redis (celery requires redis), but docker is
    # NOT pulled in even though redis requires docker, because the auto-select
    # loop runs only over the originally selected addon.
    items = _items("docker", "redis", "celery")
    requires = _requires(("celery", ["redis"]), ("redis", ["docker"]))
    with patch("builtins.input", return_value="3"):
        result = _fallback_addons(items, requires, always_locked_names=set())
    assert "celery" in result
    assert "redis" in result
    assert "docker" not in result


def test_fallback_addons_no_auto_select_when_no_requirement():
    items = _items("docker", "redis", "sentry")
    requires = _requires(("celery", ["redis"]))
    with patch("builtins.input", return_value="3"):  # sentry, no requirements
        result = _fallback_addons(items, requires, always_locked_names=set())
    assert "sentry" in result
    assert "redis" not in result
    assert "docker" not in result


# ── _fallback_addons — validation ─────────────────────────────────────────────


def test_fallback_addons_retries_on_out_of_range():
    items = _items("docker", "redis")
    with patch("builtins.input", side_effect=["5", "1"]):
        result = _fallback_addons(items, _requires(), always_locked_names=set())
    assert "docker" in result


def test_fallback_addons_retries_on_non_numeric():
    items = _items("docker", "redis")
    with patch("builtins.input", side_effect=["abc", "2"]):
        result = _fallback_addons(items, _requires(), always_locked_names=set())
    assert "redis" in result


def test_fallback_addons_retries_on_zero_index():
    items = _items("docker", "redis")
    with patch("builtins.input", side_effect=["0", "1"]):
        result = _fallback_addons(items, _requires(), always_locked_names=set())
    assert "docker" in result


def test_fallback_addons_retries_on_mixed_valid_invalid():
    # "1 abc" — the whole line is rejected, not partially accepted.
    items = _items("docker", "redis", "sentry")
    with patch("builtins.input", side_effect=["1 abc", "2"]):
        result = _fallback_addons(items, _requires(), always_locked_names=set())
    assert "redis" in result
    assert "docker" not in result


# ── _fallback_addons — EOF / interrupt ────────────────────────────────────────


def test_fallback_addons_eof_raises_system_exit():
    items = _items("docker", "redis")
    with patch("builtins.input", side_effect=EOFError):
        with pytest.raises(SystemExit) as exc_info:
            _fallback_addons(items, _requires(), always_locked_names=set())
        assert exc_info.value.code == 0


def test_fallback_addons_keyboard_interrupt_raises_system_exit():
    items = _items("docker", "redis")
    with patch("builtins.input", side_effect=KeyboardInterrupt):
        with pytest.raises(SystemExit) as exc_info:
            _fallback_addons(items, _requires(), always_locked_names=set())
        assert exc_info.value.code == 0
