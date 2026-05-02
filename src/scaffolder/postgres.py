import subprocess
import sys

from scaffolder.ui import error, success, warn


def _psql_available() -> bool:
    try:
        subprocess.run(["psql", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def create_databases(name: str) -> None:
    if not _psql_available():
        error("psql not found — cannot create Postgres databases.")
        sys.exit(1)

    for dbname in [name, f"{name}_test"]:
        result = subprocess.run(
            [
                "psql",
                "-d",
                "postgres",
                "-tAc",
                f"SELECT 1 FROM pg_database WHERE datname='{dbname}'",
            ],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip() == "1":
            warn(f"Postgres database '{dbname}' already exists, skipping.")
        else:
            subprocess.run(["createdb", dbname], check=True)
            success(f"Created Postgres database '{dbname}'.")
