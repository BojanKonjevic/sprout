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
    from scaffolder.lockfile import read_lockfile

    lockfile = read_lockfile(project_dir)
    if lockfile is None:
        return [_check_metadata(project_dir)]

    results: list[HealthResult] = []
    results.append(_check_metadata(project_dir))
    results.append(_check_dependencies(project_dir, lockfile))
    results.append(_check_files(project_dir, lockfile))
    results.append(_check_sentinels(project_dir, lockfile))
    results.append(_check_addon_health(project_dir, lockfile))
    results.append(_check_compose(project_dir, lockfile))
    results.append(_check_env(project_dir, lockfile))
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

    all_files = [("template", fc) for fc in template_config.files] + [
        (addon.id, fc) for addon in selected_addon_configs for fc in addon.files
    ]

    missing: list[tuple[str, str]] = []
    checked = 0

    for source, fc in all_files:
        dest = fc.dest.replace("{{pkg_name}}", pkg_name)
        if dest.endswith("__init__.py"):
            continue
        checked += 1
        if not (project_dir / dest).exists():
            missing.append((source, dest))

    if not missing:
        result.ok(f"All {checked} expected files are present.")
    else:
        if checked > len(missing):
            result.ok(
                f"{checked - len(missing)} of {checked} expected files are present."
            )
        for source, dest in missing:
            label = "template" if source == "template" else f"addon '{source}'"
            result.error(
                f"'{dest}' is missing (generated by {label}).",
                hint=f"This file was generated at scaffold time. "
                f"Restore it or re-run 'zenit add {source}' if it was an addon.",
            )

    common_files = [".gitignore", ".gitattributes", ".pre-commit-config.yaml"]
    for fname in common_files:
        if not (project_dir / fname).exists():
            result.warn(
                f"'{fname}' is missing.",
                hint="This file is generated for all zenit projects. It may have been deleted.",
            )

    return result


def _check_sentinels(project_dir: Path, lockfile: object) -> HealthResult:
    """Check that extension point sentinels are still present in generated files."""
    import os

    from scaffolder.lockfile import ZenitLockfile
    from scaffolder.templates._load_config import load_template_config

    assert isinstance(lockfile, ZenitLockfile)
    result = HealthResult("Extension points")

    scaffolder_root = Path(os.environ.get("SCAFFOLDER_ROOT", Path(__file__).parent))
    pkg_name = project_dir.name.replace("-", "_")

    try:
        template_config = load_template_config(scaffolder_root, lockfile.template)
    except Exception:
        result.warn(
            f"Could not load template '{lockfile.template}' to verify sentinels.",
            hint="The template may have changed since this project was scaffolded.",
        )
        return result

    if not template_config.extension_points:
        result.ok("No extension points defined for this template.")
        return result

    checked = 0
    missing = 0

    for point_name, ep in template_config.extension_points.items():
        rel_path = ep.file.replace("{{pkg_name}}", pkg_name)

        # sentinels in .py files are stripped at scaffold time — nothing to check
        if rel_path.endswith(".py"):
            continue

        file_path = project_dir / rel_path
        if not file_path.exists():
            continue

        checked += 1
        text = file_path.read_text(encoding="utf-8")

        if ep.sentinel in text:
            result.ok(f"Sentinel for '{point_name}' is present in '{rel_path}'.")
        else:
            missing += 1
            result.error(
                f"Sentinel for '{point_name}' is missing from '{rel_path}'.",
                hint=f"Add '{ep.sentinel}' back to '{rel_path}' to restore injection support.",
            )

    if checked == 0:
        result.ok("No sentinel files found to check.")

    return result


def _check_addon_health(project_dir: Path, lockfile: object) -> HealthResult:
    """Call each installed addon's health_check hook if it defines one."""
    from scaffolder.addons._registry import get_available_addons
    from scaffolder.lockfile import ZenitLockfile

    assert isinstance(lockfile, ZenitLockfile)
    result = HealthResult("Addon integrity")

    if not lockfile.addons:
        result.ok("No addons installed.")
        return result

    available = get_available_addons()
    addon_map = {cfg.id: cfg for cfg in available}

    any_checks = False
    for addon_id in lockfile.addons:
        cfg = addon_map.get(addon_id)
        if cfg is None:
            continue
        module = getattr(cfg, "_module", None)
        if module is None or not hasattr(module, "health_check"):
            continue

        any_checks = True
        try:
            issues: list[HealthIssue] = module.health_check(project_dir, lockfile)
            for issue in issues:
                result.issues.append(issue)
        except Exception as e:
            result.warn(
                f"health_check for '{addon_id}' raised an error: {e}",
                hint="This is a bug in the addon's health_check function.",
            )

    if not any_checks:
        result.ok("No addon integrity checks defined.")

    return result


def _check_compose(project_dir: Path, lockfile: object) -> HealthResult:
    """Check compose.yml for expected services and duplicate definitions."""
    from scaffolder.addons._registry import get_available_addons
    from scaffolder.collect import collect_all
    from scaffolder.lockfile import ZenitLockfile
    from scaffolder.templates._load_config import load_template_config
    import os
    import yaml

    assert isinstance(lockfile, ZenitLockfile)
    result = HealthResult("Compose")

    compose_path = project_dir / "compose.yml"
    if not compose_path.exists():
        if "docker" in lockfile.addons:
            result.error(
                "compose.yml is missing but docker addon is installed.",
                hint="Restore compose.yml or re-run 'zenit add docker'.",
            )
        else:
            result.ok("No compose.yml — docker addon not installed.")
        return result

    try:
        data = yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        result.error(
            f"compose.yml could not be parsed: {e}",
            hint="Fix the YAML syntax error and re-run 'zenit doctor'.",
        )
        return result

    services: dict = data.get("services", {})

    # check for duplicate service names (yaml.safe_load deduplicates keys silently,
    # so we detect this by counting raw occurrences in the file text)
    raw_text = compose_path.read_text(encoding="utf-8")
    import re

    service_name_counts: dict[str, int] = {}
    in_services = False
    for line in raw_text.splitlines():
        if line.strip() == "" or line.strip().startswith("#"):
            continue
        if line == "services:":
            in_services = True
            continue
        if in_services:
            # top-level key at 0 indent means we left the services block
            if line[0] != " ":
                in_services = False
                continue
            # service names are at exactly 2 spaces indent
            m = re.match(r"^  ([a-zA-Z0-9_-]+):$", line)
            if m:
                name = m.group(1)
                service_name_counts[name] = service_name_counts.get(name, 0) + 1

    duplicates = [n for n, c in service_name_counts.items() if c > 1]
    if duplicates:
        for name in duplicates:
            result.error(
                f"Service '{name}' is defined more than once in compose.yml.",
                hint="Remove the duplicate service definition.",
            )
    else:
        result.ok("No duplicate service definitions in compose.yml.")

    # check expected services are present
    scaffolder_root = Path(os.environ.get("SCAFFOLDER_ROOT", Path(__file__).parent))
    try:
        template_config = load_template_config(scaffolder_root, lockfile.template)
        available = get_available_addons()
        selected_addon_configs = [cfg for cfg in available if cfg.id in lockfile.addons]
        contributions = collect_all(template_config, selected_addon_configs)
    except Exception:
        result.warn(
            "Could not load template/addon config to verify compose services.",
        )
        return result

    all_services = [svc.name for svc in template_config.compose_services] + [
        svc.name for svc in contributions.compose_services
    ]

    missing_services = [s for s in all_services if s not in services]
    if missing_services:
        for name in missing_services:
            result.error(
                f"Expected compose service '{name}' is missing from compose.yml.",
                hint=f"Restore the '{name}' service or re-scaffold the relevant addon.",
            )
    else:
        if all_services:
            result.ok(
                f"All expected compose services are present: {', '.join(all_services)}."
            )

    return result


def _check_env(project_dir: Path, lockfile: object) -> HealthResult:
    """Check that expected env vars are present in .env and .env.example."""
    import os

    from scaffolder.addons._registry import get_available_addons
    from scaffolder.collect import collect_all
    from scaffolder.lockfile import ZenitLockfile
    from scaffolder.templates._load_config import load_template_config

    assert isinstance(lockfile, ZenitLockfile)
    result = HealthResult("Environment variables")

    scaffolder_root = Path(os.environ.get("SCAFFOLDER_ROOT", Path(__file__).parent))

    try:
        template_config = load_template_config(scaffolder_root, lockfile.template)
        available = get_available_addons()
        selected_addon_configs = [cfg for cfg in available if cfg.id in lockfile.addons]
        contributions = collect_all(template_config, selected_addon_configs)
    except Exception:
        result.warn("Could not load template/addon config to verify env vars.")
        return result

    expected_vars = [
        ev.key for ev in (template_config.env_vars + contributions.env_vars)
    ]

    if not expected_vars:
        result.ok("No env vars expected for this template and addons.")
        return result

    for fname in (".env", ".env.example"):
        env_path = project_dir / fname
        if not env_path.exists():
            result.warn(
                f"'{fname}' is missing.",
                hint=f"Create '{fname}' with the required env vars.",
            )
            continue

        text = env_path.read_text(encoding="utf-8")
        missing = [key for key in expected_vars if f"{key}=" not in text]
        if missing:
            for key in missing:
                result.error(
                    f"'{key}' is missing from '{fname}'.",
                    hint=f"Add '{key}=<value>' to '{fname}'.",
                )
        else:
            result.ok(
                f"All {len(expected_vars)} expected env vars are present in '{fname}'."
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
