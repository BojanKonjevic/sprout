# src/scaffolder/prompt.py
"""Interactive prompt – arrow keys, space to toggle, enter to confirm.

Works on Unix (termios) and Windows (msvcrt). Falls back to number
input when stdin is not a tty (CI / piped input).
"""

from __future__ import annotations

import sys

from scaffolder.ui import BOLD, CYAN, DIM, GREEN, MAGENTA, RESET, YELLOW, warn

TEMPLATES: list[tuple[str, str]] = [
    ("blank", "dev tools only  (pytest, ruff, mypy)"),
    ("fastapi", "FastAPI + SQLAlchemy + Alembic + asyncpg"),
]

TEMPLATE_REQUIRES: dict[str, list[str]] = {
    "fastapi": ["docker"],
}

_REGISTRY_REQUIRES: dict[str, list[str]] = {}

# ── ANSI helpers ─────────────────────────────────────────────────────────

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


# ── Cross‑platform key reader ───────────────────────────────────────────


def _read_key() -> str:
    """Return a key identifier string, e.g. '\r', ' ', '\x1b[A', etc."""
    if sys.platform == "win32":
        import msvcrt

        ch = msvcrt.getwch()
        if ch == "\x00" or ch == "\xe0":  # arrow / function prefix
            ch2 = msvcrt.getwch()
            if ch2 == "H":
                return "\x1b[A"  # up arrow
            if ch2 == "P":
                return "\x1b[B"  # down arrow
            return ch + ch2
        if ch == "\x03":
            raise KeyboardInterrupt
        return ch
    else:
        import termios
        import tty

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
    return sys.stdin.isatty()


# ── Visual symbols ──────────────────────────────────────────────────────

_ARROW = f"{MAGENTA}›{RESET}"
_SPACER = " "
_CHECK = f"{GREEN}[✓]{RESET}"
_EMPTY = f"{DIM}[ ]{RESET}"
_LOCKED = f"{YELLOW}[~]{RESET}"


# ── Single selection (template) ─────────────────────────────────────────


def _render_single(items: list[tuple[str, str]], cursor: int) -> int:
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
    sys.stdout.write(f"\n  {DIM}↑↓ move · space / enter select{RESET}\n")
    lines += 2
    sys.stdout.flush()
    return lines


def _tui_single(prompt: str, items: list[tuple[str, str]]) -> str:
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
            elif key == "\x03":  # ctrl+c
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
    print(f"  {GREEN}✓{RESET}  {BOLD}{name}{RESET}  {DIM}{desc}{RESET}\n")
    return name


# ── Multi selection (addons) ────────────────────────────────────────────


def _render_multi(
    items: list[tuple[str, str]],
    cursor: int,
    selected: set[int],
    locked: set[int] | None = None,
    flash: str = "",
) -> int:
    locked = locked or set()
    lines = 0
    for i, (name, desc) in enumerate(items):
        if i in locked:
            tick = _LOCKED
        elif i in selected:
            tick = _CHECK
        else:
            tick = _EMPTY
        if i == cursor:
            prefix = f"  {_ARROW} "
            label = f"{CYAN}{BOLD}{name}{RESET}"
        else:
            prefix = f"  {_SPACER}  "
            label = name
        # Append dependency hint to description for non‑locked items
        extra = ""
        if i not in locked:
            reqs = _requires_of(items[i][0])
            if reqs:
                extra = f"  {DIM}(needs {', '.join(reqs)}){RESET}"
        sys.stdout.write(f"{prefix}{tick} {label:<18}{DIM}  {desc}{RESET}{extra}\n")
        lines += 1
    if flash:
        sys.stdout.write(f"\n  {YELLOW}⚠  {flash}{RESET}\n")
    else:
        sys.stdout.write(f"\n  {DIM}↑↓ move · space toggle · enter confirm{RESET}\n")
    lines += 2
    sys.stdout.flush()
    return lines


def _requires_of(addon_id: str) -> list[str]:
    # Look up the requirement from the addon registry.
    # This function will be called with the actual registry data,
    # so we pass it as a global or closure. We'll set a module‑level
    # variable before calling prompt_addons.
    try:
        return _REGISTRY_REQUIRES.get(addon_id, [])
    except NameError:
        return []


def _tui_multi(
    prompt: str,
    items: list[tuple[str, str]],
    requires_map: dict[str, list[str]],
    always_locked: set[int],
) -> list[str]:
    print(f"\n  {BOLD}{prompt}{RESET}\n")
    sys.stdout.write(_HIDE_CURSOR)

    cursor = 0
    n_items = len(items)
    selected: set[int] = set(always_locked)
    name_to_idx = {name: i for i, (name, _) in enumerate(items)}

    # Save registry for _requires_of
    global _REGISTRY_REQUIRES
    _REGISTRY_REQUIRES = requires_map

    def _compute_locked() -> set[int]:
        locked = set(always_locked)
        for sel_idx in selected:
            sel_name = items[sel_idx][0]
            for req in requires_map.get(sel_name, []):
                if req in name_to_idx:
                    locked.add(name_to_idx[req])
        return locked

    flash = ""
    locked = _compute_locked()
    rendered = _render_multi(items, cursor, selected, locked, flash)

    try:
        while True:
            key = _read_key()
            flash = ""
            if key in ("\x1b[A", "k"):
                cursor = (cursor - 1) % n_items
            elif key in ("\x1b[B", "j"):
                cursor = (cursor + 1) % n_items
            elif key == " ":
                item_name = items[cursor][0]
                if cursor in locked:
                    if cursor in always_locked:
                        flash = f"{item_name} is required by the template"
                    else:
                        dependents = [
                            items[i][0]
                            for i in selected
                            if item_name in requires_map.get(items[i][0], [])
                        ]
                        flash = f"{item_name} is required by {', '.join(dependents)}"
                elif cursor in selected:
                    selected.discard(cursor)
                    # Also discard any addon that depends on this one
                    for i, (name, _) in enumerate(items):
                        if item_name in requires_map.get(name, []) and i not in always_locked:
                            selected.discard(i)
                else:
                    selected.add(cursor)
                    # Auto‑select required addons
                    for req in requires_map.get(item_name, []):
                        if req in name_to_idx:
                            selected.add(name_to_idx[req])
            elif key in ("\r", "\n"):
                break
            elif key == "\x03":  # ctrl+c
                sys.stdout.write(_SHOW_CURSOR)
                print()
                sys.exit(0)

            locked = _compute_locked()
            _clear_lines(rendered)
            rendered = _render_multi(items, cursor, selected, locked, flash)
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


# ── Fallback (non‑tty) ─────────────────────────────────────────────────


def _fallback_template() -> str:
    from scaffolder.ui import CYAN, DIM, RESET

    print("\n  Select a base template:\n")
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


def _fallback_addons(
    items: list[tuple[str, str]],
    requires_map: dict[str, list[str]],
    always_locked_names: set[str],
) -> list[str]:
    from scaffolder.ui import CYAN, DIM, RESET

    if not items:
        return list(always_locked_names)

    print(f"\n  Select addons: {DIM}(space‑separated numbers, or enter to skip){RESET}\n")
    for i, (addon_id, desc) in enumerate(items, 1):
        locked = " (required)" if addon_id in always_locked_names else ""
        print(f"    {CYAN}{i}){RESET} {addon_id:<18} {DIM}—{RESET} {desc}{locked}")
    print()

    while True:
        try:
            raw = input("  Addons [e.g. 1 3, or leave blank]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

        selected: list[str] = list(always_locked_names)
        if not raw:
            return selected

        valid = True
        for token in raw.split():
            if not token.isdigit():
                warn(f"'{token}' is not a number.")
                valid = False
                break
            idx = int(token) - 1
            if idx < 0 or idx >= len(items):
                warn(f"{token} is out of range — pick between 1 and {len(items)}.")
                valid = False
                break
            addon_id = items[idx][0]
            if addon_id not in selected:
                selected.append(addon_id)
                for req in requires_map.get(addon_id, []):
                    if req not in selected:
                        selected.append(req)
                        warn(f"Auto‑selected '{req}' (required by '{addon_id}').")
        if valid:
            return selected


# ── Public API ──────────────────────────────────────────────────────────


def prompt_template() -> str:
    if _tty_available():
        return _tui_single("Select a base template:", TEMPLATES)
    return _fallback_template()


def prompt_addons(available: list[tuple[str, str, list[str]]], template: str = "") -> list[str]:
    if not available:
        return []

    items = [(aid, desc) for aid, desc, _ in available]
    requires_map = {aid: reqs for aid, _, reqs in available}
    name_to_idx = {aid: i for i, (aid, _) in enumerate(items)}

    always_locked: set[int] = set()
    for req in TEMPLATE_REQUIRES.get(template, []):
        if req in name_to_idx:
            always_locked.add(name_to_idx[req])

    if _tty_available():
        return _tui_multi("Select addons:", items, requires_map, always_locked)
    return _fallback_addons(items, requires_map, {items[i][0] for i in always_locked})
