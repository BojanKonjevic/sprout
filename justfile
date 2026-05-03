lint:
    ruff check .
fmt:
    ruff format .
check:
    mypy src/
fix:
    ruff check --fix .
    ruff format .
