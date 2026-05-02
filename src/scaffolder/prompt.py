from scaffolder.ui import CYAN, RESET, warn

TEMPLATES = {
    "1": ("blank", "dev tools only (pytest, ruff, mypy)"),
    "2": ("fastapi", "FastAPI + SQLAlchemy + Alembic + asyncpg"),
}


def prompt_template() -> str:
    print()
    print("  Select a template:\n")
    for key, (name, desc) in TEMPLATES.items():
        print(f"    {CYAN}{key}){RESET} {name:<10} — {desc}")
    print()

    while True:
        choice = input("  Template [1/2]: ").strip().lower()
        for key, (name, _) in TEMPLATES.items():
            if choice in (key, name):
                return name
        warn("Please enter 1 or 2.")
