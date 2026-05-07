"""Shared rendering helpers for TUI prompts."""

from __future__ import annotations

import sys

from scaffolder.ui import DIM, GREEN, MAGENTA, RESET, YELLOW

# ── ANSI escape sequences ─────────────────────────────────────────────────────

_HIDE_CURSOR = "\033[?25l"
_SHOW_CURSOR = "\033[?25h"
_CLEAR_LINE = "\033[2K\r"
_UP = "\033[A"


def hide_cursor() -> None:
    sys.stdout.write(_HIDE_CURSOR)
    sys.stdout.flush()


def show_cursor() -> None:
    sys.stdout.write(_SHOW_CURSOR)
    sys.stdout.flush()


def clear_lines(n: int) -> None:
    for _ in range(n):
        sys.stdout.write(_CLEAR_LINE)
        sys.stdout.write(_UP)
    sys.stdout.write(_CLEAR_LINE)
    sys.stdout.flush()


ARROW = f"{MAGENTA}›{RESET}"
CHECK = f"{GREEN}[✓]{RESET}"
EMPTY = f"{DIM}[ ]{RESET}"
LOCKED = f"{YELLOW}[~]{RESET}"
CROSS = f"{YELLOW}✗{RESET}"

# Width constants
LABEL_WIDTH = 20
DESC_INDENT = "  "

TEMPLATES: list[tuple[str, str]] = [
    ("blank", "dev tools only  (pytest, ruff, mypy)"),
    ("fastapi", "FastAPI + SQLAlchemy + Alembic + asyncpg"),
]

TEMPLATE_REQUIRES: dict[str, list[str]] = {
    "fastapi": ["docker"],
}
