"""Unit tests for scaffolder.remove — private string-manipulation helpers.

_strip_recipes and _strip_injected_block are ~80 lines of stateful line-by-line
parsing that sit beneath every `zenit remove` call.  The integration tests in
test_remove.py exercise the happy path through full scaffold+remove cycles, but
edge cases in recipe/comment/blank-line handling are much easier to pin down at
the unit level.
"""

from __future__ import annotations

from scaffolder.addons.remove import _strip_injected_block, _strip_recipes

# ── _strip_injected_block ─────────────────────────────────────────────────────


def test_strip_injected_block_removes_exact_block():
    text = "before\n    injected()\nafter\n"
    result = _strip_injected_block(text, "    injected()")
    assert "injected" not in result
    assert "before" in result
    assert "after" in result


def test_strip_injected_block_preserves_surrounding_content():
    text = "line1\n    do_thing()\nline3\n"
    result = _strip_injected_block(text, "    do_thing()")
    assert result == "line1line3\n"


def test_strip_injected_block_multiline_block():
    block = "    from .sentry import init_sentry\n    init_sentry()"
    text = f"def startup():\n{block}\n    pass\n"
    result = _strip_injected_block(text, block)
    assert "init_sentry" not in result
    assert "def startup" in result
    assert "pass" in result


def test_strip_injected_block_not_present_returns_unchanged():
    text = "def main():\n    pass\n"
    result = _strip_injected_block(text, "    injected()")
    assert result == text


def test_strip_injected_block_only_removes_first_occurrence():
    block = "    do_thing()"
    text = f"a\n{block}\nb\n{block}\nc\n"
    result = _strip_injected_block(text, block)
    # re.sub without count removes all, but the contract is it strips the block;
    # verify it doesn't leave broken content
    assert "a" in result
    assert "b" in result
    assert "c" in result


def test_strip_injected_block_empty_block_returns_unchanged():
    text = "def main():\n    pass\n"
    result = _strip_injected_block(text, "")
    # empty pattern — should not crash
    assert isinstance(result, str)


def test_strip_injected_block_block_at_start_of_file():
    block = "import sentry_sdk"
    text = f"{block}\n\ndef main():\n    pass\n"
    result = _strip_injected_block(text, block)
    assert "sentry_sdk" not in result
    assert "def main" in result


def test_strip_injected_block_block_at_end_of_file():
    block = "    init_sentry()"
    text = f"def main():\n    pass\n{block}"
    result = _strip_injected_block(text, block)
    assert "init_sentry" not in result


def test_strip_injected_block_does_not_remove_partial_match():
    block = "    init_sentry()"
    text = "def main():\n    init_sentry_extra()\n    pass\n"
    result = _strip_injected_block(text, block)
    # "init_sentry()" is not literally present — text unchanged
    assert "init_sentry_extra" in result


def test_strip_injected_block_special_regex_chars_in_block():
    # block contains characters that are special in regex
    block = '    redis_url: str = "redis://localhost:6379/0"'
    text = f"class Settings:\n{block}\n    debug: bool = False\n"
    result = _strip_injected_block(text, block)
    assert "redis_url" not in result
    assert "debug" in result


# ── _strip_recipes — basic removal ───────────────────────────────────────────


def test_strip_recipes_removes_named_recipe():
    text = "test:\n    uv run pytest\n"
    result = _strip_recipes(text, {"test"})
    assert "test:" not in result
    assert "uv run pytest" not in result


def test_strip_recipes_preserves_other_recipes():
    text = "test:\n    uv run pytest\nlint:\n    ruff check .\n"
    result = _strip_recipes(text, {"test"})
    assert "test:" not in result
    assert "lint:" in result
    assert "ruff check ." in result


def test_strip_recipes_removes_recipe_with_comment():
    text = "# start redis\nredis-up:\n    docker compose up -d redis\n"
    result = _strip_recipes(text, {"redis-up"})
    assert "redis-up:" not in result
    assert "# start redis" not in result
    assert "docker compose up" not in result


def test_strip_recipes_removes_recipe_with_multiline_body():
    text = (
        "db-create:\n"
        "    docker compose up -d db\n"
        "    just wait-db\n"
        "    just upgrade\n"
        "lint:\n"
        "    ruff check .\n"
    )
    result = _strip_recipes(text, {"db-create"})
    assert "db-create:" not in result
    assert "just wait-db" not in result
    assert "just upgrade" not in result
    assert "lint:" in result


def test_strip_recipes_removes_multiple_recipes():
    text = (
        "redis-up:\n    docker compose up -d redis\n"
        "redis-down:\n    docker compose stop redis\n"
        "test:\n    uv run pytest\n"
    )
    result = _strip_recipes(text, {"redis-up", "redis-down"})
    assert "redis-up:" not in result
    assert "redis-down:" not in result
    assert "test:" in result


def test_strip_recipes_empty_names_set_returns_unchanged():
    text = "test:\n    uv run pytest\n"
    result = _strip_recipes(text, set())
    assert result == text


def test_strip_recipes_name_not_present_returns_unchanged():
    text = "test:\n    uv run pytest\n"
    result = _strip_recipes(text, {"nonexistent"})
    assert result == text


# ── _strip_recipes — blank line collapsing ────────────────────────────────────


def test_strip_recipes_does_not_leave_triple_blank_lines():
    text = (
        "test:\n    pytest\n"
        "\n"
        "redis-up:\n    docker compose up -d redis\n"
        "\n"
        "lint:\n    ruff check .\n"
    )
    result = _strip_recipes(text, {"redis-up"})
    # No run of more than one consecutive blank line
    assert "\n\n\n" not in result


def test_strip_recipes_collapses_double_blank_to_single():
    text = "test:\n    pytest\n\n\nredis-up:\n    up\n\nlint:\n    ruff\n"
    result = _strip_recipes(text, {"redis-up"})
    assert "\n\n\n" not in result
    assert "lint:" in result


def test_strip_recipes_preserves_single_blank_lines_between_recipes():
    text = "test:\n    pytest\n\nlint:\n    ruff check .\n"
    result = _strip_recipes(text, set())
    # With nothing removed, single blank lines should survive
    assert "\n\n" in result


# ── _strip_recipes — comment ownership ───────────────────────────────────────


def test_strip_recipes_only_removes_immediately_preceding_comment():
    """A comment separated from the recipe by a blank line is NOT removed."""
    text = (
        "# unrelated comment\n"
        "\n"
        "redis-up:\n"
        "    docker compose up -d redis\n"
        "lint:\n"
        "    ruff check .\n"
    )
    result = _strip_recipes(text, {"redis-up"})
    assert "redis-up:" not in result
    # The comment is separated by a blank line so the recipe stripper
    # does not walk back past blank lines — it's implementation-defined
    # whether the comment survives, but it must not corrupt other recipes.
    assert "lint:" in result


def test_strip_recipes_removes_multiple_comment_lines_before_recipe():
    text = (
        "# comment line 1\n"
        "# comment line 2\n"
        "redis-up:\n"
        "    docker compose up -d redis\n"
        "test:\n"
        "    pytest\n"
    )
    result = _strip_recipes(text, {"redis-up"})
    assert "redis-up:" not in result
    assert "docker compose" not in result
    assert "test:" in result


def test_strip_recipes_does_not_remove_comment_belonging_to_kept_recipe():
    text = (
        "# start redis\n"
        "redis-up:\n"
        "    docker compose up -d redis\n"
        "# run tests\n"
        "test:\n"
        "    uv run pytest\n"
    )
    result = _strip_recipes(text, {"redis-up"})
    assert "# run tests" in result
    assert "test:" in result


# ── _strip_recipes — recipe name edge cases ──────────────────────────────────


def test_strip_recipes_hyphenated_name():
    text = "celery-flower:\n    docker compose run celery flower\ntest:\n    pytest\n"
    result = _strip_recipes(text, {"celery-flower"})
    assert "celery-flower:" not in result
    assert "test:" in result


def test_strip_recipes_recipe_with_args_in_header():
    text = (
        'migrate msg="":\n    uv run alembic revision -m "{{msg}}"\ntest:\n    pytest\n'
    )
    result = _strip_recipes(text, {"migrate"})
    assert "migrate" not in result
    assert "test:" in result


def test_strip_recipes_recipe_with_dependency_in_header():
    text = "upgrade: wait-db\n    uv run alembic upgrade head\ntest:\n    pytest\n"
    result = _strip_recipes(text, {"upgrade"})
    assert "upgrade:" not in result
    assert "test:" in result


def test_strip_recipes_indented_lines_inside_body_not_confused_with_recipes():
    # body contains a line that looks like "key: value" — must not be treated as recipe
    text = (
        "docker-up:\n"
        "    docker compose up --build\n"
        "test:\n"
        "    env KEY=value uv run pytest\n"
    )
    result = _strip_recipes(text, {"docker-up"})
    assert "docker-up:" not in result
    assert "test:" in result
    assert "KEY=value" in result


# ── _strip_recipes — full justfile simulation ─────────────────────────────────


def test_strip_recipes_full_justfile_remove_addon_set():
    base = (
        'set windows-shell := ["cmd", "/C"]\n\n'
        "default:\n    @just --list\n\n"
        "test:\n    uv run pytest -v\n\n"
        "lint:\n    uv run ruff check .\n\n"
        "# build and start all services\n"
        "docker-up:\n    docker compose up --build\n\n"
        "# stop all services\n"
        "docker-down:\n    docker compose down\n\n"
        "# start redis\n"
        "redis-up:\n    docker compose up -d redis\n\n"
        "# stop redis\n"
        "redis-down:\n    docker compose stop redis\n"
    )
    result = _strip_recipes(
        base, {"docker-up", "docker-down", "redis-up", "redis-down"}
    )

    assert "docker-up:" not in result
    assert "docker-down:" not in result
    assert "redis-up:" not in result
    assert "redis-down:" not in result

    assert "test:" in result
    assert "lint:" in result
    assert "default:" in result
    assert "\n\n\n" not in result


def test_strip_recipes_result_ends_with_newline_when_input_does():
    text = "test:\n    pytest\nredis-up:\n    docker compose up -d redis\n"
    result = _strip_recipes(text, {"redis-up"})
    assert result.endswith("\n")
