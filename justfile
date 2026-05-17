lint:
    ruff check .
fmt:
    ruff format .
check:
    uv run python -m mypy src/
fix:
    ruff check --fix .
    ruff format .
test:
    uv run python -m pytest -v -m "not slow"
test-full:
    uv run python -m pytest -v
test-cov:
    uv run python -m pytest --cov=src --cov-report=term-missing -v
re:
    uv tool install --reinstall .
publish:
    rm -f dist/*.tar.gz dist/*.whl
    uv build
    uv publish --token "$UV_PUBLISH_TOKEN"
    uv tool install --reinstall zenit
