import sys

from scaffolder.ui import BOLD, CYAN, DIM, GREEN, RESET, YELLOW, warn

TEMPLATES: dict[str, tuple[str, str]] = {
    "1": ("blank", "dev tools only  (pytest, ruff, mypy)"),
    "2": ("fastapi", "FastAPI + SQLAlchemy + Alembic + asyncpg"),
}


def prompt_template() -> str:
    print()
    print(f"  {BOLD}Select a base template:{RESET}\n")
    for key, (name, desc) in TEMPLATES.items():
        print(f"    {CYAN}{key}){RESET} {name:<10} {DIM}—{RESET} {desc}")
    print()

    while True:
        try:
            choice = input("  Template [1/2]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

        for key, (name, _) in TEMPLATES.items():
            if choice in (key, name):
                return name
        warn("Please enter 1 or 2.")


def prompt_addons(available: list[tuple[str, str]]) -> list[str]:
    """Multi-select addon picker. Returns list of selected addon ids."""
    if not available:
        return []

    print()
    print(
        f"  {BOLD}Select addons:{RESET}  {DIM}(space-separated numbers, or enter to skip){RESET}\n"
    )
    for i, (addon_id, desc) in enumerate(available, start=1):
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
                warn(f"'{token}' is not a number — enter space-separated numbers.")
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
            _confirm_addons(selected)
            return selected


def _confirm_addons(selected: list[str]) -> None:
    if not selected:
        print(f"\n  {DIM}No addons selected.{RESET}")
        return
    names = ", ".join(f"{GREEN}{a}{RESET}" for a in selected)
    print(f"\n  Adding: {names}")
