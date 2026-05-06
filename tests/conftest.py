"""Shared pytest fixtures and helpers."""

import pytest
from click.exceptions import Exit as ClickExit


def raises_exit(code: int = 1):
    """Context manager that expects a typer.Exit(code) to be raised."""
    return pytest.raises(ClickExit, match="")


class ExitAssertion:
    """Use as a context manager to assert a typer.Exit(1) was raised."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            raise AssertionError("Expected a typer.Exit to be raised but nothing was raised")
        if not isinstance(exc_val, ClickExit):
            return False  # let other exceptions propagate
        assert exc_val.exit_code == 1, f"Expected exit code 1, got {exc_val.exit_code}"
        return True  # suppress the exception


@pytest.fixture
def assert_exits():
    """Fixture that returns an ExitAssertion context manager."""
    return ExitAssertion
