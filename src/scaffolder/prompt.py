"""Interactive TUI prompt — arrow keys, space-to-toggle, enter to confirm.

Uses only stdlib: sys, tty, termios (Unix). Falls back gracefully to the
original number-input style on Windows or when stdin is not a tty (e.g.
piped input / CI).
"""

from __future__ import annotations

import sys

from scaffolder.ui import BOLD, CYAN, DIM, GREEN, MAGENTA, RESET, YELLOW, warn

TEMPLATES: list[tuple[str, str]] = [
    ("blank", "dev tools only  (pytest, ruff, mypy)"),
    ("fastapi", "FastAPI + SQLAlchemy + Alembic + asyncpg"),
]

# ─── ANSI helpers ────────────────────────────────────────────────────────────

_HIDE_CURSOR = "\033[?25l"
_SHOW_CURSOR = "\033[?25h"
_CLEAR_LINE = "\033[2K\r"
_UP = "\033[A"


def _move_up(n: int) -> str:
    return f"\033[{n}A" if n > 0 else ""


def _clear_lines(n: int) -> None:
    for _ in range(n):
        sys.stdout.write(_CLEAR_LINE)
        sys.stdout.write(_UP)
    sys.stdout.write(_CLEAR_LINE)
    sys.stdout.flush()


# ─── Raw keypress reader ─────────────────────────────────────────────────────


def _read_key() -> str:
    """Read a single keypress from stdin (Unix raw mode)."""
    import tty, termios  # noqa: E401

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch2 = sys.stdin.read(1)
            ch3 = sys.stdin.read(1)
            return ch + ch2 + ch3
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _tty_available() -> bool:
    try:
        import tty, termios  # noqa: F401,E401

        return sys.stdin.isatty()
    except ImportError:
        return False


# ─── Rendering ───────────────────────────────────────────────────────────────

_ARROW = f"{MAGENTA}›{RESET}"
_SPACER = " "
_CHECK = f"{GREEN}[✓]{RESET}"
_EMPTY = f"{DIM}[ ]{RESET}"


def _render_single(items: list[tuple[str, str]], cursor: int) -> int:
    """Draw a single-select list. Returns number of lines written."""
    lines = 0
    for i, (name, desc) in enumerate(items):
        if i == cursor:
            prefix = f"  {_ARROW} "
            label = f"{CYAN}{BOLD}{name}{RESET}"
        else:
            prefix = f"  {_SPACER}  "
            label = name
        sys.stdout.write(f"{prefix}{label:<12}{DIM}  {desc}{RESET}\n")
        lines += 1
    sys.stdout.write(f"\n  {DIM}↑↓ move · enter select{RESET}\n")
    lines += 2
    sys.stdout.flush()
    return lines


def _render_multi(items: list[tuple[str, str]], cursor: int, selected: set[int]) -> int:
    """Draw a multi-select list. Returns number of lines written."""
    lines = 0
    for i, (name, desc) in enumerate(items):
        tick = _CHECK if i in selected else _EMPTY
        if i == cursor:
            prefix = f"  {_ARROW} "
            label = f"{CYAN}{BOLD}{name}{RESET}"
        else:
            prefix = f"  {_SPACER}  "
            label = name
        sys.stdout.write(f"{prefix}{tick} {label:<18}{DIM}  {desc}{RESET}\n")
        lines += 1
    sys.stdout.write(f"\n  {DIM}↑↓ move · space toggle · enter confirm{RESET}\n")
    lines += 2
    sys.stdout.flush()
    return lines


# ─── TUI selectors ───────────────────────────────────────────────────────────


def _tui_single(prompt: str, items: list[tuple[str, str]]) -> str:
    """Arrow-key single select. Returns the chosen item name."""
    print(f"\n  {BOLD}{prompt}{RESET}\n")
    sys.stdout.write(_HIDE_CURSOR)

    cursor = 0
    n_items = len(items)
    rendered = _render_single(items, cursor)

    try:
        while True:
            key = _read_key()
            if key in ("\x1b[A", "k"):  # up
                cursor = (cursor - 1) % n_items
            elif key in ("\x1b[B", "j"):  # down
                cursor = (cursor + 1) % n_items
            elif key in ("\r", "\n", " "):  # enter / space → confirm
                break
            elif key == "\x03":  # ctrl-c
                sys.stdout.write(_SHOW_CURSOR)
                print()
                sys.exit(0)

            _clear_lines(rendered)
            rendered = _render_single(items, cursor)
    finally:
        sys.stdout.write(_SHOW_CURSOR)
        sys.stdout.flush()

    name, desc = items[cursor]
    _clear_lines(rendered)
    # Print a tidy confirmation line
    print(f"  {GREEN}✓{RESET}  {BOLD}{name}{RESET}  {DIM}{desc}{RESET}\n")
    return name


def _tui_multi(prompt: str, items: list[tuple[str, str]]) -> list[str]:
    """Arrow-key multi-select. Returns list of selected item names."""
    print(f"\n  {BOLD}{prompt}{RESET}\n")
    sys.stdout.write(_HIDE_CURSOR)

    cursor = 0
    n_items = len(items)
    selected: set[int] = set()
    rendered = _render_multi(items, cursor, selected)

    try:
        while True:
            key = _read_key()
            if key in ("\x1b[A", "k"):
                cursor = (cursor - 1) % n_items
            elif key in ("\x1b[B", "j"):
                cursor = (cursor + 1) % n_items
            elif key == " ":
                if cursor in selected:
                    selected.discard(cursor)
                else:
                    selected.add(cursor)
            elif key in ("\r", "\n"):
                break
            elif key == "\x03":
                sys.stdout.write(_SHOW_CURSOR)
                print()
                sys.exit(0)

            _clear_lines(rendered)
            rendered = _render_multi(items, cursor, selected)
    finally:
        sys.stdout.write(_SHOW_CURSOR)
        sys.stdout.flush()

    chosen = [items[i][0] for i in sorted(selected)]
    _clear_lines(rendered)

    if chosen:
        names = ", ".join(f"{GREEN}{n}{RESET}" for n in chosen)
        print(f"  {GREEN}✓{RESET}  {names}\n")
    else:
        print(f"  {DIM}No addons selected.{RESET}\n")
    return chosen


# ─── Fallback (non-tty / Windows) ────────────────────────────────────────────


def _fallback_template() -> str:
    print(f"\n  {BOLD}Select a base template:{RESET}\n")
    for i, (name, desc) in enumerate(TEMPLATES, 1):
        print(f"    {CYAN}{i}){RESET} {name:<10} {DIM}—{RESET} {desc}")
    print()
    while True:
        try:
            choice = input("  Template [1/2]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        for key, (name, _) in enumerate(TEMPLATES, 1):
            if choice in (str(key), name):
                return name
        warn("Please enter 1 or 2.")


def _fallback_addons(available: list[tuple[str, str]]) -> list[str]:
    if not available:
        return []
    print(
        f"\n  {BOLD}Select addons:{RESET}  {DIM}(space-separated numbers, or enter to skip){RESET}\n"
    )
    for i, (addon_id, desc) in enumerate(available, 1):
        print(f"    {CYAN}{i}){RESET} {addon_id:<18} {DIM}—{RESET} {desc}")
    print()
    while True:
        try:
            raw = input("  Addons [e.g. 1 3, or leave blank]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if not raw:
            return []
        selected: list[str] = []
        valid = True
        for token in raw.split():
            if not token.isdigit():
                warn(f"'{token}' is not a number.")
                valid = False
                break
            idx = int(token) - 1
            if idx < 0 or idx >= len(available):
                warn(f"{token} is out of range — pick between 1 and {len(available)}.")
                valid = False
                break
            addon_id = available[idx][0]
            if addon_id not in selected:
                selected.append(addon_id)
        if valid:
            return selected


# ─── Public API ──────────────────────────────────────────────────────────────


def prompt_template() -> str:
    if _tty_available():
        return _tui_single("Select a base template:", TEMPLATES)
    return _fallback_template()


def prompt_addons(available: list[tuple[str, str]]) -> list[str]:
    if not available:
        return []
    if _tty_available():
        return _tui_multi("Select addons:", available)
    return _fallback_addons(available)
