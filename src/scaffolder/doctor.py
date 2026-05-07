"""zenit doctor — inspect a project's health against zenit's expectations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Severity(Enum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"


@dataclass
class HealthIssue:
    severity: Severity
    message: str
    hint: str = ""


@dataclass
class HealthResult:
    category: str
    issues: list[HealthIssue] = field(default_factory=list)

    def ok(self, message: str) -> None:
        self.issues.append(HealthIssue(Severity.OK, message))

    def warn(self, message: str, hint: str = "") -> None:
        self.issues.append(HealthIssue(Severity.WARN, message, hint))

    def error(self, message: str, hint: str = "") -> None:
        self.issues.append(HealthIssue(Severity.ERROR, message, hint))

    @property
    def has_errors(self) -> bool:
        return any(i.severity == Severity.ERROR for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == Severity.WARN for i in self.issues)


def run_doctor(project_dir: Path) -> list[HealthResult]:
    """Run all health checks against *project_dir* and return the results."""
    from scaffolder.lockfile import read_lockfile

    lockfile = read_lockfile(project_dir)
    if lockfile is None:
        return [_check_metadata(project_dir)]

    results: list[HealthResult] = []
    results.append(_check_metadata(project_dir))
    results.append(_check_dependencies(project_dir, lockfile))
    results.append(_check_files(project_dir, lockfile))
    return results


def _check_metadata(project_dir: Path) -> HealthResult:
    """Check .zenit.toml validity, addon compatibility, and version skew."""
    from importlib.metadata import version as get_version

    from scaffolder.addons._registry import get_available_addons
    from scaffolder.lockfile import read_lockfile

    result = HealthResult("Metadata")
    lockfile = read_lockfile(project_dir)

    if lockfile is None:
        result.error(
            ".zenit.toml is missing.",
            hint="Re-scaffold the project or create .zenit.toml manually.",
        )
        return result
    result.ok(".zenit.toml is present and valid.")

    if not lockfile.template:
        result.error(
            ".zenit.toml has no template field.",
            hint="Add 'template = \"blank\"' or 'template = \"fastapi\"' to [project].",
        )
    else:
        result.ok(f"Template is '{lockfile.template}'.")

    available = get_available_addons()
    known_ids = {cfg.id for cfg in available}
    unknown = [a for a in lockfile.addons if a not in known_ids]
    if unknown:
        result.error(
            f"Unknown addon(s) in .zenit.toml: {', '.join(unknown)}.",
            hint="These addons are not recognised by the current zenit version. "
            "You may need to upgrade zenit or remove them from .zenit.toml.",
        )
    else:
        if lockfile.addons:
            result.ok(f"All installed addons are known: {', '.join(lockfile.addons)}.")
        else:
            result.ok("No addons installed.")

    requires_map = {cfg.id: cfg.requires for cfg in available}
    for addon_id in lockfile.addons:
        for req in requires_map.get(addon_id, []):
            if req not in lockfile.addons:
                result.error(
                    f"Addon '{addon_id}' requires '{req}' but it is not installed.",
                    hint=f"Run 'zenit add {req}' to install the missing dependency.",
                )
            else:
                result.ok(f"Addon '{addon_id}' dependency '{req}' is satisfied.")

    if lockfile.zenit_version:
        try:
            current = get_version("zenit")
            if current != lockfile.zenit_version:
                result.warn(
                    f"Project was scaffolded with zenit {lockfile.zenit_version}, "
                    f"current version is {current}.",
                    hint="Run 'zenit doctor' after upgrading to check for compatibility issues.",
                )
            else:
                result.ok(f"Zenit version matches: {current}.")
        except Exception:
            result.warn(
                "Could not determine current zenit version.",
                hint="Install zenit as a package to enable version checks.",
            )
    else:
        result.warn(
            ".zenit.toml has no zenit_version field.",
            hint="This project was scaffolded with an older version of zenit.",
        )

    return result


def _check_dependencies(project_dir: Path, lockfile: object) -> HealthResult:
    """Check that pyproject.toml contains all deps expected by the template and addons."""
    import re

    from scaffolder.addons._registry import get_available_addons
    from scaffolder.collect import collect_all
    from scaffolder.lockfile import ZenitLockfile
    from scaffolder.templates._load_config import load_template_config

    assert isinstance(lockfile, ZenitLockfile)
    result = HealthResult("Dependencies")

    pyproject_path = project_dir / "pyproject.toml"
    if not pyproject_path.exists():
        result.error(
            "pyproject.toml is missing.",
            hint="zenit cannot verify dependencies without pyproject.toml.",
        )
        return result
    result.ok("pyproject.toml is present.")

    try:
        import tomllib

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        result.error(
            f"pyproject.toml could not be parsed: {e}",
            hint="Fix the TOML syntax error and re-run 'zenit doctor'.",
        )
        return result

    raw_deps: list[str] = data.get("project", {}).get("dependencies", [])
    dev_group: list[str] = data.get("dependency-groups", {}).get("dev", []) or data.get(
        "project", {}
    ).get("optional-dependencies", {}).get("dev", [])

    def _pkg_name(dep: str) -> str:
        match = re.match(r"^([a-zA-Z0-9_.-]+)", dep)
        return match.group(1).lower().replace("-", "_") if match else dep.lower()

    installed_deps = {_pkg_name(d) for d in raw_deps}
    installed_dev_deps = {_pkg_name(d) for d in dev_group}

    import os

    scaffolder_root = Path(os.environ.get("SCAFFOLDER_ROOT", Path(__file__).parent))

    try:
        template_config = load_template_config(scaffolder_root, lockfile.template)
    except Exception:
        result.warn(
            f"Could not load template '{lockfile.template}' to verify deps.",
            hint="The template may have changed since this project was scaffolded.",
        )
        return result

    available = get_available_addons()
    selected_addon_configs = [cfg for cfg in available if cfg.id in lockfile.addons]
    contributions = collect_all(template_config, selected_addon_configs)

    expected_deps = contributions.deps
    expected_dev_deps = template_config.dev_deps + contributions.dev_deps

    missing_deps = [d for d in expected_deps if _pkg_name(d) not in installed_deps]
    missing_dev_deps = [
        d for d in expected_dev_deps if _pkg_name(d) not in installed_dev_deps
    ]

    if missing_deps:
        for dep in missing_deps:
            result.error(
                f"Runtime dependency '{dep}' is missing from pyproject.toml.",
                hint="Add it under [project] dependencies or run 'zenit add' again.",
            )
    else:
        result.ok("All expected runtime dependencies are present.")

    if missing_dev_deps:
        for dep in missing_dev_deps:
            result.warn(
                f"Dev dependency '{dep}' is missing from pyproject.toml.",
                hint="Add it under [dependency-groups] dev.",
            )
    else:
        result.ok("All expected dev dependencies are present.")

    return result


def _check_files(project_dir: Path, lockfile: object) -> HealthResult:
    """Check that all files generated by the template and addons still exist."""
    import os

    from scaffolder.addons._registry import get_available_addons
    from scaffolder.lockfile import ZenitLockfile
    from scaffolder.templates._load_config import load_template_config

    assert isinstance(lockfile, ZenitLockfile)
    result = HealthResult("Generated files")

    scaffolder_root = Path(os.environ.get("SCAFFOLDER_ROOT", Path(__file__).parent))
    pkg_name = project_dir.name.replace("-", "_")

    try:
        template_config = load_template_config(scaffolder_root, lockfile.template)
    except Exception:
        result.warn(
            f"Could not load template '{lockfile.template}' to verify files.",
            hint="The template may have changed since this project was scaffolded.",
        )
        return result

    available = get_available_addons()
    selected_addon_configs = [cfg for cfg in available if cfg.id in lockfile.addons]

    # collect all expected file destinations from template and addons
    all_files = [("template", fc) for fc in template_config.files] + [
        (addon.id, fc) for addon in selected_addon_configs for fc in addon.files
    ]

    missing: list[tuple[str, str]] = []
    checked = 0

    for source, fc in all_files:
        dest = fc.dest.replace("{{pkg_name}}", pkg_name)

        # skip __init__.py stubs — they're trivial and often intentionally removed
        if dest.endswith("__init__.py"):
            continue

        checked += 1
        full_path = project_dir / dest
        if not full_path.exists():
            missing.append((source, dest))

    if not missing:
        result.ok(f"All {checked} expected files are present.")
    else:
        result.ok(
            f"{checked - len(missing)} of {checked} expected files are present."
        ) if checked > len(missing) else None
        for source, dest in missing:
            label = "template" if source == "template" else f"addon '{source}'"
            result.error(
                f"'{dest}' is missing (generated by {label}).",
                hint=f"This file was generated at scaffold time. "
                f"Restore it or re-run 'zenit add {source}' if it was an addon.",
            )

    # check common files
    common_files = [".gitignore", ".gitattributes", ".pre-commit-config.yaml"]
    for fname in common_files:
        if not (project_dir / fname).exists():
            result.warn(
                f"'{fname}' is missing.",
                hint="This file is generated for all zenit projects. It may have been deleted.",
            )

    return result


def print_results(results: list[HealthResult]) -> bool:
    """Print health check results. Returns True if any errors were found."""
    from scaffolder.ui import BOLD, CYAN, DIM, GREEN, RED, RESET, YELLOW

    any_errors = False

    for result in results:
        print(f"\n  {BOLD}{CYAN}{result.category}{RESET}")
        for issue in result.issues:
            if issue.severity == Severity.OK:
                icon = f"{GREEN}✓{RESET}"
            elif issue.severity == Severity.WARN:
                icon = f"{YELLOW}⚠{RESET}"
            else:
                icon = f"{RED}✗{RESET}"
                any_errors = True

            print(f"    {icon}  {issue.message}")
            if issue.hint:
                print(f"       {DIM}{issue.hint}{RESET}")

    return any_errors
