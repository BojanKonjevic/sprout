lint:
    ruff check .
fmt:
    ruff format .
check:
    uv run python -m mypy src/
fix:
    ruff check --fix .
    ruff format .
publish:
    rm -f dist/*.tar.gz dist/*.whl
    uv build
    uv publish
    uv tool install --reinstall zenit

