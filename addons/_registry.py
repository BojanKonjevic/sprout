# Each entry: (id, description)
# The id must match a folder under addons/ that contains an apply.py
ADDONS: list[tuple[str, str]] = [
    ("docker", "Dockerfile + compose.yml + .dockerignore"),
    ("redis", "Redis service + connection helper + compose service"),
    ("celery", "Celery worker + beat scheduler, backed by Redis"),
    ("sentry", "Sentry error tracking + performance monitoring"),
    ("github-actions", "CI workflow (lint, type-check, test on push/PR)"),
]
