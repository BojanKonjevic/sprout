# Each entry: (id, description, requires)
# requires is a list of addon ids that must also be selected
ADDONS: list[tuple[str, str, list[str]]] = [
    ("docker", "Dockerfile + compose.yml + .dockerignore", []),
    ("redis", "Redis service + connection helper + compose service", []),
    ("celery", "Celery worker + beat scheduler, backed by Redis", ["redis"]),
    ("sentry", "Sentry error tracking + performance monitoring", []),
    ("github-actions", "CI workflow (lint, type-check, test on push/PR)", []),
]
