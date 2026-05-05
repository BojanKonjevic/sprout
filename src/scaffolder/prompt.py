"""Interactive prompts using questionary (cross-platform, arrow-key TUI).

Falls back to number-input style when stdin is not a tty (CI, piped input).
"""

from __future__ import annotations

import sys

import questionary
from questionary import Style

TEMPLATES: list[tuple[str, str]] = [
    ("blank", "dev tools only  (pytest, ruff, mypy)"),
    ("fastapi", "FastAPI + SQLAlchemy + Alembic + asyncpg"),
]

TEMPLATE_REQUIRES: dict[str, list[str]] = {
    "fastapi": ["docker"],
}

# ── Catppuccin Mocha palette ──────────────────────────────────────────────────

SPROUT_STYLE = Style(
    [
        ("qmark", "fg:#cba6f7 bold"),  # purple  question mark
        ("question", "bold"),
        ("answer", "fg:#a6e3a1 bold"),  # green   confirmed answer
        ("pointer", "fg:#cba6f7 bold"),  # purple  arrow pointer
        ("highlighted", "fg:#89dceb bold"),  # teal    cursor item
        ("selected", "fg:#a6e3a1"),  # green   checked items
        ("separator", "fg:#6c7086"),  # overlay separator
        ("instruction", "fg:#6c7086 italic"),  # dim     key hints
        ("text", ""),
        ("disabled", "fg:#585b70 italic"),  # dim     locked items
    ]
)


# ── TUI prompts (questionary) ─────────────────────────────────────────────────


def _tui_template() -> str:
    choices = [
        questionary.Choice(title=f"{name:<12}  {desc}", value=name) for name, desc in TEMPLATES
    ]
    result = questionary.select(
        "Select a base template:",
        choices=choices,
        style=SPROUT_STYLE,
    ).ask()
    if result is None:
        print()
        sys.exit(0)
    return result  # type: ignore[return-value]


def _tui_addons(
    items: list[tuple[str, str]],
    requires_map: dict[str, list[str]],
    always_locked_names: set[str],
) -> list[str]:
    choices: list[questionary.Choice] = []
    for aid, desc in items:
        if aid in always_locked_names:
            choices.append(
                questionary.Choice(
                    title=f"{aid:<20}  {desc}",
                    value=aid,
                    checked=True,
                    disabled="required by template",
                )
            )
        else:
            choices.append(
                questionary.Choice(
                    title=f"{aid:<20}  {desc}",
                    value=aid,
                )
            )

    def _validate(selected: list[str]) -> bool | str:
        all_selected = set(selected) | always_locked_names
        for name in all_selected:
            for req in requires_map.get(name, []):
                if req not in all_selected:
                    return f"'{name}' requires '{req}' — please select it too"
        return True

    result = questionary.checkbox(
        "Select addons:",
        choices=choices,
        style=SPROUT_STYLE,
        validate=_validate,
    ).ask()

    if result is None:
        print()
        sys.exit(0)

    # questionary does not include disabled items in the result even when checked,
    # so we add the always-locked ones back manually.
    for name in always_locked_names:
        if name not in result:
            result.append(name)

    return result  # type: ignore[return-value]


# ── Fallback (non-tty / piped input / CI) ────────────────────────────────────


def _fallback_template() -> str:
    from scaffolder.ui import CYAN, DIM, RESET, warn

    print(f"\n  Select a base template:\n")
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
    from scaffolder.ui import CYAN, DIM, RESET, warn

    if not items:
        return list(always_locked_names)

    print(f"\n  Select addons: {DIM}(space-separated numbers, or enter to skip){RESET}\n")
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
                        warn(f"Auto-selected '{req}' (required by '{addon_id}').")
        if valid:
            return selected


# ── Public API ────────────────────────────────────────────────────────────────


def prompt_template() -> str:
    if sys.stdin.isatty():
        return _tui_template()
    return _fallback_template()


def prompt_addons(available: list[tuple[str, str, list[str]]], template: str = "") -> list[str]:
    if not available:
        return []

    items = [(aid, desc) for aid, desc, _ in available]
    requires_map = {aid: reqs for aid, _, reqs in available}
    always_locked_names: set[str] = set(TEMPLATE_REQUIRES.get(template, []))

    if sys.stdin.isatty():
        return _tui_addons(items, requires_map, always_locked_names)
    return _fallback_addons(items, requires_map, always_locked_names)
