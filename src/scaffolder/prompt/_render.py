"""Shared rendering helpers for TUI prompts."""

from __future__ import annotations

import sys

from scaffolder.ui import BOLD, CYAN, DIM, GREEN, MAGENTA, RESET, YELLOW

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


def reserve_lines(n: int) -> None:
    """Print blank lines to ensure the menu has room without causing scroll during redraw."""
    sys.stdout.write("\n" * n)
    sys.stdout.flush()


def render_single(
    items: list[tuple[str, str]],
    cursor: int,
    *,
    default_name: str | None = None,
    unavailable: set[int] | None = None,
    full_items: list[tuple[str, str, list[str]]] | None = None,
    flash: str = "",
) -> int:
    """Render a single-select TUI list. Returns the number of lines written."""
    unavailable = unavailable or set()
    lines = 0

    for i, (name, desc) in enumerate(items):
        is_unavailable = i in unavailable
        is_cursor = i == cursor

        prefix = f"  {ARROW} " if is_cursor else "     "

        if is_unavailable:
            tick = f"{CROSS}  "
        elif is_cursor:
            tick = f"{CHECK} "
        else:
            tick = f"{EMPTY} "

        if is_unavailable:
            label = f"{DIM}{name}{RESET}"
        elif is_cursor:
            label = f"{CYAN}{BOLD}{name}{RESET}"
        else:
            label = name
        padded_label = f"{label:<{LABEL_WIDTH}}"

        desc_text = f"{DIM}{desc}{RESET}"

        extra = ""
        if not is_cursor and name == default_name:
            extra = f"  {DIM}(default){RESET}"
        elif is_unavailable and full_items and i < len(full_items):
            reqs = full_items[i][2]
            if reqs:
                extra = f"  {DIM}(needs {', '.join(reqs)}){RESET}"

        sys.stdout.write(
            f"{prefix}{tick}{padded_label}{DESC_INDENT}{desc_text}{extra}\n"
        )
        lines += 1

    if flash:
        sys.stdout.write(f"\n  {YELLOW}⚠  {flash}{RESET}\n")
    else:
        sys.stdout.write(f"\n  {DIM}↑↓ move · space / enter select{RESET}\n")
    lines += 2
    sys.stdout.flush()
    return lines


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
