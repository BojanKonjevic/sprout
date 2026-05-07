"""Single-selection TUI (template picker and `zenit add` picker)."""

from __future__ import annotations

import sys

from scaffolder.ui import BOLD, CYAN, DIM, GREEN, RESET, YELLOW

from ._keys import read_key, tty_available
from ._render import (
    ARROW,
    CHECK,
    CROSS,
    DESC_INDENT,
    EMPTY,
    LABEL_WIDTH,
    TEMPLATES,
    clear_lines,
    hide_cursor,
    show_cursor,
)


def _render_single(
    items: list[tuple[str, str]],
    cursor: int,
    default_name: str | None = None,
) -> int:
    """Render the single-selection TUI with fixed-width prefixes.

    Every line has identical structure so text never shifts horizontally:
      prefix(5) + tick(5) + label(LABEL_WIDTH) + desc_indent(2) + desc
    """
    lines = 0
    for i, (name, desc) in enumerate(items):
        # Build prefix: "  › " (cursor) or "    " (not cursor) — both 5 chars
        prefix = f"  {ARROW} " if i == cursor else "     "

        # Build tick: "[✓]" or "[ ]" — both 5 chars (with trailing space)
        tick = f"{CHECK} " if i == cursor else f"{EMPTY} "

        # Build label: colored+bold if cursor, plain otherwise
        label = f"{CYAN}{BOLD}{name}{RESET}" if i == cursor else name
        padded_label = f"{label:<{LABEL_WIDTH}}"

        # Description
        desc_text = f"{DIM}{desc}{RESET}"

        # Default marker (only on non-cursor rows to avoid width mismatch)
        default_marker = ""
        if name == default_name and i != cursor:
            default_marker = f"  {DIM}(default){RESET}"

        sys.stdout.write(
            f"{prefix}{tick}{padded_label}{DESC_INDENT}{desc_text}{default_marker}\n"
        )
        lines += 1

    sys.stdout.write(f"\n  {DIM}↑↓ move · space / enter select{RESET}\n")
    lines += 2
    sys.stdout.flush()
    return lines


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
    hide_cursor()

    n_items = len(TEMPLATES)
    rendered = _render_single(TEMPLATES, cursor, default_name=default)

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
            rendered = _render_single(TEMPLATES, cursor, default_name=default)
    finally:
        show_cursor()

    name, desc = TEMPLATES[cursor]
    clear_lines(rendered)
    print(f"  {GREEN}✓{RESET}  {BOLD}{name}{RESET}  {DIM}{desc}{RESET}\n")
    return name


def _render_single_add(
    items: list[tuple[str, str]],
    cursor: int,
    full_items: list[tuple[str, str, list[str]]],
    unavailable_indices: set[int],
    flash: str = "",
) -> int:
    """Render the `zenit add` single-select TUI with fixed-width prefixes.

    Same fixed-width layout as _render_single, with an extra column for
    dependency warnings on unavailable items.
    """
    lines = 0
    for i, (name, desc) in enumerate(items):
        is_unavailable = i in unavailable_indices

        # Fixed prefix: 5 chars
        prefix = f"  {ARROW} " if i == cursor else "     "

        # Fixed tick: 5 chars
        if is_unavailable:
            tick = f"{CROSS}  "  # "✗  " (✗ is 1 char in terminal)
        elif i == cursor:
            tick = f"{CHECK} "
        else:
            tick = f"{EMPTY} "

        # Label: 20 chars
        if is_unavailable:
            label = f"{DIM}{name}{RESET}"
        elif i == cursor:
            label = f"{CYAN}{BOLD}{name}{RESET}"
        else:
            label = name
        padded_label = f"{label:<{LABEL_WIDTH}}"

        # Description
        desc_text = f"{DIM}{desc}{RESET}"

        # Dependency warning
        reqs = full_items[i][2] if i < len(full_items) else []
        extra = ""
        if is_unavailable and reqs:
            extra = f"  {DIM}(needs {', '.join(reqs)}){RESET}"

        sys.stdout.write(
            f"{prefix}{tick}{padded_label}{DESC_INDENT}{desc_text}{extra}\n"
        )
        lines += 1

    if flash:
        sys.stdout.write(f"\n  {YELLOW}⚠  {flash}{RESET}\n")
    else:
        sys.stdout.write(f"\n  {DIM}↑↓ move · enter select · ctrl+c cancel{RESET}\n")
    lines += 2
    sys.stdout.flush()
    return lines


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
    hide_cursor()

    cursor = 0
    n_items = len(display_items)
    rendered = _render_single_add(display_items, cursor, items, unavailable_indices)

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
                    rendered = _render_single_add(
                        display_items,
                        cursor,
                        items,
                        unavailable_indices,
                        flash=flash,
                    )
                    continue
                break
            elif key == "\x03":
                show_cursor()
                print()
                sys.exit(0)

            clear_lines(rendered)
            rendered = _render_single_add(
                display_items, cursor, items, unavailable_indices
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
