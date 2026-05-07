"""Interactive prompt — arrow keys and space to select, enter to confirm.

Works on Unix (termios) and Windows (msvcrt).  Falls back to numbered input
when stdin is not a tty (CI / piped input).
"""

from __future__ import annotations

import sys

from scaffolder.schema import AddonConfig
from scaffolder.ui import BOLD, CYAN, DIM, GREEN, MAGENTA, RESET, YELLOW, warn

TEMPLATES: list[tuple[str, str]] = [
    ("blank", "dev tools only  (pytest, ruff, mypy)"),
    ("fastapi", "FastAPI + SQLAlchemy + Alembic + asyncpg"),
]

# Templates that force certain addons to be pre-selected and locked.
TEMPLATE_REQUIRES: dict[str, list[str]] = {
    "fastapi": ["docker"],
}

# ── ANSI helpers ──────────────────────────────────────────────────────────────

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


# ── Cross-platform key reader ─────────────────────────────────────────────────


def _read_key() -> str:
    """Return a key identifier string such as ``'\r'``, ``' '``, or ``'\x1b[A'``."""
    if sys.platform == "win32":
        import msvcrt

        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):  # arrow / function key prefix
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


# ── Visual symbols ────────────────────────────────────────────────────────────

_ARROW = f"{MAGENTA}›{RESET}"
_SPACER = " "
_CHECK = f"{GREEN}[✓]{RESET}"
_EMPTY = f"{DIM}[ ]{RESET}"
_LOCKED = f"{YELLOW}[~]{RESET}"


# ── Single selection (template) ───────────────────────────────────────────────


def _render_single(
    items: list[tuple[str, str]],
    cursor: int,
    default_name: str | None = None,
) -> int:
    lines = 0
    for i, (name, desc) in enumerate(items):
        if i == cursor:
            prefix = f"  {_ARROW} "
            label = f"{CYAN}{BOLD}{name}{RESET}"
        else:
            prefix = f"  {_SPACER}  "
            label = name
        default_marker = f"  {DIM}(default){RESET}" if name == default_name else ""
        sys.stdout.write(f"{prefix}{label:<12}{DIM}  {desc}{RESET}{default_marker}\n")
        lines += 1
    sys.stdout.write(f"\n  {DIM}↑↓ move · space / enter select{RESET}\n")
    lines += 2
    sys.stdout.flush()
    return lines


def _tui_single(
    prompt: str,
    items: list[tuple[str, str]],
    default: str | None = None,
) -> str:
    # Start cursor at the default template if one is configured.
    cursor = 0
    if default is not None:
        for i, (name, _) in enumerate(items):
            if name == default:
                cursor = i
                break

    print(f"\n  {BOLD}{prompt}{RESET}\n")
    sys.stdout.write(_HIDE_CURSOR)

    n_items = len(items)
    rendered = _render_single(items, cursor, default_name=default)

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
            rendered = _render_single(items, cursor, default_name=default)
    finally:
        sys.stdout.write(_SHOW_CURSOR)
        sys.stdout.flush()

    name, desc = items[cursor]
    _clear_lines(rendered)
    print(f"  {GREEN}✓{RESET}  {BOLD}{name}{RESET}  {DIM}{desc}{RESET}\n")
    return name


# ── Multi selection (addons) ──────────────────────────────────────────────────


def _render_multi(
    items: list[tuple[str, str]],
    cursor: int,
    selected: set[int],
    requires_map: dict[str, list[str]],
    locked: set[int] | None = None,
    flash: str = "",
    default_selected: set[int] | None = None,
) -> int:
    locked = locked or set()
    default_selected = default_selected or set()
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

        reqs = requires_map.get(name, [])
        extra = (
            f"  {DIM}(needs {', '.join(reqs)}){RESET}"
            if reqs and i not in locked
            else ""
        )
        # Show a dim "(default)" hint only on items that are pre-selected from
        # config but not locked by the template — so the user knows why it's
        # already checked without being told it's mandatory.
        default_hint = (
            f"  {DIM}(default){RESET}"
            if i in default_selected and i not in locked
            else ""
        )
        sys.stdout.write(
            f"{prefix}{tick} {label:<18}{DIM}  {desc}{RESET}{extra}{default_hint}\n"
        )
        lines += 1

    if flash:
        sys.stdout.write(f"\n  {YELLOW}⚠  {flash}{RESET}\n")
    else:
        sys.stdout.write(f"\n  {DIM}↑↓ move · space toggle · enter confirm{RESET}\n")
    lines += 2
    sys.stdout.flush()
    return lines


def _tui_multi(
    prompt: str,
    items: list[tuple[str, str]],
    requires_map: dict[str, list[str]],
    always_locked: set[int],
    default_selected: set[int] | None = None,
) -> list[str]:
    print(f"\n  {BOLD}{prompt}{RESET}\n")
    sys.stdout.write(_HIDE_CURSOR)

    cursor = 0
    n_items = len(items)
    # Start with always_locked plus any config defaults.
    selected: set[int] = set(always_locked)
    if default_selected:
        selected |= default_selected
    name_to_idx = {name: i for i, (name, _) in enumerate(items)}

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
    rendered = _render_multi(
        items,
        cursor,
        selected,
        requires_map,
        locked,
        flash,
        default_selected=default_selected,
    )

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
                    # Also remove any addon that depended on this one.
                    for i, (name, _) in enumerate(items):
                        if (
                            item_name in requires_map.get(name, [])
                            and i not in always_locked
                        ):
                            selected.discard(i)
                else:
                    selected.add(cursor)
                    # Auto-select transitive requirements.
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
            rendered = _render_multi(
                items,
                cursor,
                selected,
                requires_map,
                locked,
                flash,
                default_selected=default_selected,
            )
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


# ── Fallback (non-tty) ────────────────────────────────────────────────────────


def _fallback_template(default: str | None = None) -> str:
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


def _fallback_addons(
    items: list[tuple[str, str]],
    requires_map: dict[str, list[str]],
    always_locked_names: set[str],
    default_addon_names: set[str] | None = None,
) -> list[str]:
    if not items:
        return list(always_locked_names)

    default_addon_names = default_addon_names or set()
    has_defaults = bool(default_addon_names - always_locked_names)

    print(
        f"\n  Select addons: {DIM}("
        + (
            "enter for defaults"
            if has_defaults
            else "space-separated numbers, or enter to skip"
        )
        + f"){RESET}\n"
    )
    for i, (addon_id, desc) in enumerate(items, 1):
        locked_mark = (
            f" {DIM}(required){RESET}" if addon_id in always_locked_names else ""
        )
        default_mark = (
            f" {DIM}(default){RESET}"
            if addon_id in default_addon_names and addon_id not in always_locked_names
            else ""
        )
        print(
            f"    {CYAN}{i}){RESET} {addon_id:<18} {DIM}—{RESET} {desc}{locked_mark}{default_mark}"
        )
    print()

    # Build the default selection list: locked first, then config defaults.
    def _build_defaults() -> list[str]:
        result: list[str] = list(always_locked_names)
        for name in default_addon_names:
            if name not in result:
                result.append(name)
        return result

    while True:
        try:
            raw = input(
                "  Addons [e.g. 1 3"
                + (", or enter for defaults" if has_defaults else ", or leave blank")
                + "]: "
            ).strip()
        except EOFError, KeyboardInterrupt:
            print()
            sys.exit(0)

        if not raw:
            return _build_defaults()

        selected: list[str] = list(always_locked_names)
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
                        warn(f"Auto-selected '{req}' (required by '{addon_id}').")
        if valid:
            return selected


# ── Public API ────────────────────────────────────────────────────────────────


def prompt_template(default: str | None = None) -> str:
    if _tty_available():
        return _tui_single("Select a base template:", TEMPLATES, default=default)
    return _fallback_template(default=default)


def prompt_addons(
    available: list[AddonConfig],
    template: str = "",
    default_addons: list[str] | None = None,
) -> list[str]:
    if not available:
        return []

    items = [(cfg.id, cfg.description) for cfg in available]
    requires_map = {cfg.id: cfg.requires for cfg in available}
    name_to_idx = {cfg.id: i for i, cfg in enumerate(available)}

    always_locked: set[int] = set()
    for req in TEMPLATE_REQUIRES.get(template, []):
        if req in name_to_idx:
            always_locked.add(name_to_idx[req])

    # Resolve config defaults → indices, then auto-select their direct requirements
    # (matching the same one-level resolution the TUI does on manual toggle).
    default_selected: set[int] = set()
    if default_addons:
        for addon_id in default_addons:
            if addon_id in name_to_idx:
                default_selected.add(name_to_idx[addon_id])
        # One-level requirement resolution so e.g. celery→redis is pre-filled.
        for idx in list(default_selected):
            for req in requires_map.get(items[idx][0], []):
                if req in name_to_idx:
                    default_selected.add(name_to_idx[req])

    if _tty_available():
        return _tui_multi(
            "Select addons:",
            items,
            requires_map,
            always_locked,
            default_selected=default_selected,
        )

    always_locked_names = {items[i][0] for i in always_locked}
    default_addon_names = {items[i][0] for i in default_selected}
    return _fallback_addons(
        items,
        requires_map,
        always_locked_names,
        default_addon_names=default_addon_names,
    )
