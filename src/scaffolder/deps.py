"""Dependency injection into an existing pyproject.toml.

Uses tomlkit for round-trip parsing so that the user's formatting, comments,
and ordering are preserved. Only appends — never removes or reorders existing
entries.
"""

from __future__ import annotations

from pathlib import Path

import tomlkit


def inject_deps(
    project_dir: Path,
    deps: list[str],
    dev_deps: list[str],
) -> tuple[list[str], list[str]]:
    """Append missing deps into pyproject.toml.

    Returns (added_deps, added_dev_deps) — the deps that were actually written.
    Deps that are already present (by package name, ignoring version specifiers)
    are skipped silently.
    """
    pyproject_path = project_dir / "pyproject.toml"
    if not pyproject_path.exists():
        raise FileNotFoundError(
            "pyproject.toml not found — cannot inject dependencies."
        )

    doc = tomlkit.parse(pyproject_path.read_text(encoding="utf-8"))

    added_deps: list[str] = []
    added_dev_deps: list[str] = []

    # ── runtime deps ──────────────────────────────────────────────────────────
    project_table = doc.get("project", {})
    existing_deps: list[str] = list(project_table.get("dependencies", []))

    existing_names = {_pkg_name(d) for d in existing_deps}
    for dep in deps:
        if _pkg_name(dep) not in existing_names:
            existing_deps.append(dep)
            existing_names.add(_pkg_name(dep))
            added_deps.append(dep)

    if added_deps:
        doc["project"]["dependencies"] = tomlkit.array()  # type: ignore[index]
        doc["project"]["dependencies"].extend(existing_deps)  # type: ignore[index]

    # ── dev deps ──────────────────────────────────────────────────────────────
    # Support both [dependency-groups] dev (PEP 735 / uv style) and
    # [project.optional-dependencies] dev.
    if "dependency-groups" in doc:
        group = doc["dependency-groups"]
        existing_dev: list[str] = list(group.get("dev", []))
        existing_dev_names = {_pkg_name(d) for d in existing_dev}
        for dep in dev_deps:
            if _pkg_name(dep) not in existing_dev_names:
                existing_dev.append(dep)
                existing_dev_names.add(_pkg_name(dep))
                added_dev_deps.append(dep)
        if added_dev_deps:
            doc["dependency-groups"]["dev"] = tomlkit.array()  # type: ignore[index]
            doc["dependency-groups"]["dev"].extend(existing_dev)  # type: ignore[index]

    elif "project" in doc and "optional-dependencies" in doc["project"]:
        opt = doc["project"]["optional-dependencies"]
        existing_dev = list(opt.get("dev", []))
        existing_dev_names = {_pkg_name(d) for d in existing_dev}
        for dep in dev_deps:
            if _pkg_name(dep) not in existing_dev_names:
                existing_dev.append(dep)
                existing_dev_names.add(_pkg_name(dep))
                added_dev_deps.append(dep)
        if added_dev_deps:
            doc["project"]["optional-dependencies"]["dev"] = tomlkit.array()  # type: ignore[index]
            doc["project"]["optional-dependencies"]["dev"].extend(existing_dev)  # type: ignore[index]

    pyproject_path.write_text(tomlkit.dumps(doc), encoding="utf-8")
    return added_deps, added_dev_deps


def _pkg_name(dep: str) -> str:
    """Extract the bare package name from a dependency specifier.

    Examples:
        "redis>=5"          -> "redis"
        "celery[redis]>=5"  -> "celery"
        "sentry-sdk[fastapi]" -> "sentry-sdk"
        "fakeredis[aioredis]" -> "fakeredis"
    """
    # Strip extras and version specifiers.
    name = dep.split("[")[0]
    for op in (">=", "<=", "!=", "==", ">", "<", "~=", "@"):
        name = name.split(op)[0]
    return name.strip().lower()
