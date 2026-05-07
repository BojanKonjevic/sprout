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
    return results


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
