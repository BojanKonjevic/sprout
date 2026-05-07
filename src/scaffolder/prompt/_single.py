"""Single-selection TUI (template picker and `zenit add` picker)."""

from __future__ import annotations

import sys

from scaffolder.ui import BOLD, CYAN, DIM, GREEN, RESET

from ._keys import read_key, tty_available
from ._render import (
    TEMPLATES,
    clear_lines,
    hide_cursor,
    render_single,
    reserve_lines,
    show_cursor,
)


def prompt_template(default: str | None = None) -> str:
    """Interactive single-select for project template."""
    if not tty_available():
        return _fallback_template(default)

    cursor = 0
    if default is not None:
        for i, (name, _) in enumerate(TEMPLATES):
            if name == default:
                cursor = i
                break

    print(f"\n  {BOLD}Select a base template:{RESET}\n")
    reserve_lines(len(TEMPLATES) + 2)
    clear_lines(len(TEMPLATES) + 2)
    hide_cursor()

    n_items = len(TEMPLATES)
    rendered = render_single(TEMPLATES, cursor, default_name=default)

    try:
        while True:
            key = read_key()
            if key in ("\x1b[A", "k"):
                cursor = (cursor - 1) % n_items
            elif key in ("\x1b[B", "j"):
                cursor = (cursor + 1) % n_items
            elif key in ("\r", "\n", " "):
                break
            elif key == "\x03":
                show_cursor()
                print()
                sys.exit(0)

            clear_lines(rendered)
            rendered = render_single(TEMPLATES, cursor, default_name=default)
    finally:
        show_cursor()

    name, desc = TEMPLATES[cursor]
    clear_lines(rendered)
    print(f"  {GREEN}✓{RESET}  {BOLD}{name}{RESET}  {DIM}{desc}{RESET}\n")
    return name


def prompt_single_addon(
    items: list[tuple[str, str, list[str]]],
    unavailable_indices: set[int] | None = None,
    already_installed: list[str] | None = None,
) -> str | None:
    """Interactive single-select for `zenit add`.

    Parameters
    ----------
    items : list of (id, description, requires)
    unavailable_indices : indices that cannot be selected (missing deps)
    already_installed : list of already-installed addon ids to show
    """
    if not tty_available():
        return _fallback_single_add(items, unavailable_indices or set())

    unavailable_indices = unavailable_indices or set()
    display_items = [(name, desc) for name, desc, _ in items]

    # Show already installed
    if already_installed:
        print(f"\n  {DIM}Already installed: {', '.join(already_installed)}{RESET}")

    print(f"\n  {BOLD}Select an addon to add:{RESET}\n")
    reserve_lines(len(display_items) + 2)
    clear_lines(len(display_items) + 2)
    hide_cursor()

    cursor = 0
    n_items = len(display_items)
    rendered = render_single(
        display_items, cursor, unavailable=unavailable_indices, full_items=items
    )

    try:
        while True:
            key = read_key()
            if key in ("\x1b[A", "k"):
                cursor = (cursor - 1) % n_items
            elif key in ("\x1b[B", "j"):
                cursor = (cursor + 1) % n_items
            elif key in ("\r", "\n", " "):
                if cursor in unavailable_indices:
                    addon_id, _, reqs = items[cursor]
                    flash = (
                        f"{addon_id} requires: {', '.join(reqs)} "
                        f"— install first with 'zenit add'"
                    )
                    clear_lines(rendered)
                    rendered = render_single(
                        display_items,
                        cursor,
                        unavailable=unavailable_indices,
                        full_items=items,
                        flash=flash,
                    )
                    continue
                break
            elif key == "\x03":
                show_cursor()
                print()
                sys.exit(0)

            clear_lines(rendered)
            rendered = render_single(
                display_items, cursor, unavailable=unavailable_indices, full_items=items
            )
    finally:
        show_cursor()

    if cursor in unavailable_indices:
        clear_lines(rendered)
        print(f"  {DIM}No addon selected.{RESET}\n")
        return None

    name, desc = display_items[cursor]
    clear_lines(rendered)
    print(f"  {GREEN}✓{RESET}  {BOLD}{name}{RESET}  {DIM}{desc}{RESET}\n")
    return name


# ── Fallbacks (non-tty) ───────────────────────────────────────────────────────


def _fallback_template(default: str | None = None) -> str:
    from scaffolder.ui import warn

    print("\n  Select a base template:\n")
    for i, (name, desc) in enumerate(TEMPLATES, 1):
        marker = f"  {DIM}(default){RESET}" if name == default else ""
        print(f"    {CYAN}{i}){RESET} {name:<10} {DIM}—{RESET} {desc}{marker}")
    print()

    hint = "/".join(str(k) for k in range(1, len(TEMPLATES) + 1))
    if default is not None:
        hint += f", or enter for {default}"

    while True:
        try:
            choice = input(f"  Template [{hint}]: ").strip().lower()
        except EOFError, KeyboardInterrupt:
            print()
            sys.exit(0)

        if not choice and default is not None:
            return default

        for key, (name, _) in enumerate(TEMPLATES, 1):
            if choice in (str(key), name):
                return name
        warn("Please enter a number or template name.")


def _fallback_single_add(
    items: list[tuple[str, str, list[str]]],
    unavailable_indices: set[int],
) -> str | None:
    from scaffolder.ui import warn

    print("\n  Select an addon to add:\n")
    for i, (name, desc, reqs) in enumerate(items, 1):
        unavailable = (i - 1) in unavailable_indices
        marker = f" {DIM}(needs {', '.join(reqs)}){RESET}" if unavailable else ""
        print(f"    {CYAN}{i}){RESET} {name:<18} {DIM}—{RESET} {desc}{marker}")
    print()

    while True:
        try:
            choice = input("  Addon [number or name, or enter to cancel]: ").strip()
        except EOFError, KeyboardInterrupt:
            print()
            sys.exit(0)

        if not choice:
            return None

        for key, (name, _, _) in enumerate(items, 1):
            if choice.lower() in (str(key), name.lower()):
                if (key - 1) in unavailable_indices:
                    warn(f"'{name}' cannot be installed yet — missing dependencies.")
                    continue
                return name
        warn("Please enter a valid number or addon name.")
