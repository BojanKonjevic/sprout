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
    results: list[HealthResult] = []
    results.append(_check_metadata(project_dir))
    return results


def _check_metadata(project_dir: Path) -> HealthResult:
    """Check .zenit.toml validity, addon compatibility, and version skew."""
    from importlib.metadata import version as get_version

    from scaffolder.addons._registry import get_available_addons
    from scaffolder.lockfile import read_lockfile

    result = HealthResult("Metadata")
    lockfile = read_lockfile(project_dir)

    # lockfile validity — already checked in cmd_doctor but be defensive
    if lockfile is None:
        result.error(
            ".zenit.toml is missing.",
            hint="Re-scaffold the project or create .zenit.toml manually.",
        )
        return result
    result.ok(".zenit.toml is present and valid.")

    # template field
    if not lockfile.template:
        result.error(
            ".zenit.toml has no template field.",
            hint="Add 'template = \"blank\"' or 'template = \"fastapi\"' to [project].",
        )
    else:
        result.ok(f"Template is '{lockfile.template}'.")

    # known addons
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

    # addon dependency satisfaction
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

    # version skew
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
