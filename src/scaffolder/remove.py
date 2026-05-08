"""Remove-addon pipeline — undoes a single addon applied to an existing project."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import typer

from scaffolder.schema import ExtensionPoint
from scaffolder.ui import (
    BOLD,
    CYAN,
    DIM,
    RED,
    RESET,
    YELLOW,
    info,
    success,
    warn,
)


def remove_addon(addon_id: str, dry_run: bool = False) -> None:
    """Remove a single addon from an existing zenit project."""
    import os

    from scaffolder.addons._registry import get_available_addons
    from scaffolder.checks_remove import check_can_remove
    from scaffolder.exceptions import ScaffoldError
    from scaffolder.lockfile import write_lockfile

    project_dir = Path.cwd()
    available = get_available_addons()

    try:
        lockfile = check_can_remove(project_dir, addon_id, available)
    except ScaffoldError as exc:
        from scaffolder.ui import error

        error(str(exc))
        raise typer.Exit(1) from exc

    template = lockfile.template
    pkg_name = project_dir.name.replace("-", "_")
    scaffolder_root = Path(os.environ.get("SCAFFOLDER_ROOT", Path(__file__).parent))

    addon_cfg = next(cfg for cfg in available if cfg.id == addon_id)

    if dry_run:
        _dry_remove(project_dir, addon_id, addon_cfg, lockfile, pkg_name)
        return

    print(f"\n  {BOLD}Ready to remove addon:{RESET}")
    print(f"\n    {'addon':<12}  {BOLD}{addon_id}{RESET}")
    print(f"    {'project':<12}  {DIM}{project_dir}{RESET}")
    print(f"    {'template':<12}  {CYAN}{template}{RESET}")
    print()

    if sys.stdin.isatty():
        try:
            raw = input(f"  Proceed? {DIM}[Y/n]{RESET}  ").strip().lower()
        except EOFError, KeyboardInterrupt:
            print()
            raise typer.Exit(0) from None
        if raw not in ("", "y", "yes"):
            print(f"\n  {YELLOW}Aborted.{RESET}\n")
            raise typer.Exit(0)
    else:
        warn("Non-interactive mode — proceeding automatically.")

    from scaffolder.templates._load_config import load_template_config

    template_config = load_template_config(scaffolder_root, template)

    render_vars: dict[str, object] = {
        "name": project_dir.name,
        "pkg_name": pkg_name,
        "template": template,
        "secret_key": "",
        "has_postgres": template == "fastapi",
        "has_redis": "redis" in lockfile.addons,
    }

    # ── files ──────────────────────────────────────────────────────────────
    removed_files = _remove_files(project_dir, addon_cfg, pkg_name)

    # ── injections ──────────────────────────────────────────────────────────
    _undo_injections(
        project_dir,
        addon_cfg,
        template_config.extension_points,
        pkg_name,
    )

    # ── compose services ────────────────────────────────────────────────────
    removed_services = _remove_compose_services(project_dir, addon_cfg)
    _remove_compose_volumes(project_dir, addon_cfg)

    # ── env vars ─────────────────────────────────────────────────────────────
    _remove_env_vars(project_dir, addon_cfg)

    # ── deps ──────────────────────────────────────────────────────────────
    removed_deps, removed_dev_deps = _remove_deps(project_dir, addon_cfg)

    # ── justfile recipes ──────────────────────────────────────────────────
    removed_recipes = _remove_just_recipes(project_dir, addon_cfg, render_vars)

    # ── lockfile ──────────────────────────────────────────────────────────
    new_addons = [a for a in lockfile.addons if a != addon_id]
    write_lockfile(project_dir, template, new_addons)

    # ── output ────────────────────────────────────────────────────────────
    print()
    success(f"Addon '{addon_id}' removed from '{project_dir.name}'.")

    if removed_files:
        print()
        print(f"  {BOLD}Files removed:{RESET}")
        for f in removed_files:
            print(f"    {RED}-{RESET} {f}")

    if removed_deps or removed_dev_deps:
        print()
        print(f"  {BOLD}Dependencies removed from pyproject.toml:{RESET}")
        for dep in removed_deps:
            print(f"    {RED}-{RESET} {dep}")
        for dep in removed_dev_deps:
            print(f"    {RED}-{RESET} {dep}  {DIM}(dev){RESET}")
        info("Run 'uv sync' to uninstall them.")

    if removed_recipes:
        print()
        print(f"  {BOLD}Just recipes removed:{RESET}")
        for name in removed_recipes:
            print(f"    {RED}-{RESET} {name}")

    if removed_services:
        print()
        print(f"  {BOLD}Compose services removed:{RESET}")
        for svc in removed_services:
            print(f"    {RED}-{RESET} {svc}")

    print()


# ── Removal helpers ───────────────────────────────────────────────────────────


def _remove_files(project_dir: Path, addon_cfg: object, pkg_name: str) -> list[str]:
    """Delete files that were created by this addon. Returns list of removed paths."""
    from scaffolder.schema import AddonConfig

    assert isinstance(addon_cfg, AddonConfig)

    # Resolve all destination paths this addon owns.
    all_dests = {fc.dest.replace("{{pkg_name}}", pkg_name) for fc in addon_cfg.files}

    removed: list[str] = []

    for fc in addon_cfg.files:
        dest = fc.dest.replace("{{pkg_name}}", pkg_name)
        full = project_dir / dest

        # Empty __init__.py stubs are only safe to delete when every sibling
        # file in that directory is also being removed by this addon — meaning
        # the whole directory is ours and will be pruned anyway.  If any
        # sibling file survives (belongs to the template or another addon),
        # keep the stub so the package remains importable.
        if dest.endswith("__init__.py") and fc.content == "":
            parent = full.parent
            siblings_on_disk = (
                {
                    p.relative_to(project_dir).as_posix()
                    for p in parent.iterdir()
                    if p.is_file() and p != full
                }
                if parent.exists()
                else set()
            )
            surviving_siblings = siblings_on_disk - all_dests
            if surviving_siblings:
                continue  # other files remain → keep __init__.py

        if full.exists():
            full.unlink()
            removed.append(dest)

            # Prune empty parent directories up to project_dir.
            _prune_empty_parents(full.parent, project_dir)

    return removed


def _prune_empty_parents(directory: Path, stop_at: Path) -> None:
    """Remove empty directories walking upward, stopping at stop_at."""
    while directory != stop_at and directory.is_relative_to(stop_at):
        try:
            if not any(directory.iterdir()):
                directory.rmdir()
                directory = directory.parent
            else:
                break
        except OSError:
            break


def _undo_injections(
    project_dir: Path,
    addon_cfg: object,
    extension_points: dict[str, ExtensionPoint],
    pkg_name: str,
) -> None:
    """Remove lines injected by this addon from extension-point files."""
    from scaffolder.schema import AddonConfig

    assert isinstance(addon_cfg, AddonConfig)

    # Group injected content by target file so we touch each file once.
    by_file: dict[str, list[str]] = {}
    for inj in addon_cfg.injections:
        if inj.point not in extension_points:
            continue
        ep = extension_points[inj.point]
        rel_path = ep.file.replace("{{pkg_name}}", pkg_name)
        by_file.setdefault(rel_path, []).append(inj.content)

    for rel_path, contents in by_file.items():
        target = project_dir / rel_path
        if not target.exists():
            continue
        text = target.read_text(encoding="utf-8")
        for content in contents:
            # Strip the injected block exactly as written (plus surrounding newlines).
            text = _strip_injected_block(text, content)
        target.write_text(text, encoding="utf-8")


def _strip_injected_block(text: str, block: str) -> str:
    """Remove *block* from *text*, cleaning up the surrounding blank lines."""
    # Escape the block for use in a regex, then look for it with
    # optional leading/trailing newline so we don't leave double blank lines.
    escaped = re.escape(block)
    pattern = re.compile(r"\n?" + escaped + r"\n?")
    return pattern.sub("", text)


def _remove_compose_services(
    project_dir: Path,
    addon_cfg: object,
) -> list[str]:
    """Remove compose services that belong to this addon. Returns removed service names."""
    import yaml

    from scaffolder.schema import AddonConfig

    assert isinstance(addon_cfg, AddonConfig)

    compose_path = project_dir / "compose.yml"
    if not compose_path.exists() or not addon_cfg.compose_services:
        return []

    data: dict[str, Any] = (
        yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
    )
    services: dict[str, Any] = data.get("services", {})
    removed: list[str] = []

    for svc in addon_cfg.compose_services:
        if svc.name in services:
            del services[svc.name]
            removed.append(svc.name)

    data["services"] = services
    compose_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return removed


def _remove_compose_volumes(
    project_dir: Path,
    addon_cfg: object,
) -> None:
    """Remove named volumes that belong solely to this addon."""
    import yaml

    from scaffolder.schema import AddonConfig

    assert isinstance(addon_cfg, AddonConfig)

    compose_path = project_dir / "compose.yml"
    if not compose_path.exists() or not addon_cfg.compose_volumes:
        return

    data: dict[str, Any] = (
        yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
    )
    volumes: dict[str, Any] = data.get("volumes", {})

    for vol_name in addon_cfg.compose_volumes:
        volumes.pop(vol_name, None)

    if volumes:
        data["volumes"] = volumes
    else:
        data.pop("volumes", None)

    compose_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def _remove_env_vars(project_dir: Path, addon_cfg: object) -> list[str]:
    """Remove env var lines added by this addon. Returns list of removed keys."""
    from scaffolder.schema import AddonConfig

    assert isinstance(addon_cfg, AddonConfig)

    if not addon_cfg.env_vars:
        return []

    removed: list[str] = []
    for fname in (".env", ".env.example"):
        env_path = project_dir / fname
        if not env_path.exists():
            continue
        lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines: list[str] = []
        for line in lines:
            key = line.split("=")[0].strip()
            if any(ev.key == key for ev in addon_cfg.env_vars):
                if fname == ".env":
                    removed.append(key)
            else:
                new_lines.append(line)
        env_path.write_text("".join(new_lines), encoding="utf-8")

    return removed


def _remove_deps(project_dir: Path, addon_cfg: object) -> tuple[list[str], list[str]]:
    """Remove addon deps from pyproject.toml. Returns (removed_deps, removed_dev_deps)."""
    import re as _re

    import tomlkit

    from scaffolder.schema import AddonConfig

    assert isinstance(addon_cfg, AddonConfig)

    pyproject_path = project_dir / "pyproject.toml"
    if not pyproject_path.exists():
        return [], []

    doc = tomlkit.parse(pyproject_path.read_text(encoding="utf-8"))

    def pkg_name(dep: str) -> str:
        m = _re.match(r"^([a-zA-Z0-9_.-]+)", dep)
        return m.group(1).lower() if m else dep.lower()

    addon_dep_names = {pkg_name(d) for d in addon_cfg.deps}
    addon_dev_names = {pkg_name(d) for d in addon_cfg.dev_deps}

    removed_deps: list[str] = []
    removed_dev_deps: list[str] = []

    # Runtime deps
    project_table = doc.get("project", {})
    if isinstance(project_table, dict):
        existing = list(project_table.get("dependencies") or [])
        new_deps = []
        for dep in existing:
            if pkg_name(str(dep)) in addon_dep_names:
                removed_deps.append(str(dep))
            else:
                new_deps.append(dep)
        if removed_deps:
            arr = tomlkit.array()
            arr.extend(new_deps)
            project_table["dependencies"] = arr

    # Dev deps
    if "dependency-groups" in doc:
        group = doc["dependency-groups"]
        if isinstance(group, dict):
            existing_dev = list(group.get("dev") or [])
            new_dev = []
            for dep in existing_dev:
                if pkg_name(str(dep)) in addon_dev_names:
                    removed_dev_deps.append(str(dep))
                else:
                    new_dev.append(dep)
            if removed_dev_deps:
                arr = tomlkit.array()
                arr.extend(new_dev)
                group["dev"] = arr

    pyproject_path.write_text(tomlkit.dumps(doc), encoding="utf-8")
    return removed_deps, removed_dev_deps


def _remove_just_recipes(
    project_dir: Path,
    addon_cfg: object,
    render_vars: dict[str, object],
) -> list[str]:
    """Remove just recipes contributed by this addon. Returns list of removed recipe names."""
    from scaffolder.render import make_env
    from scaffolder.schema import AddonConfig

    assert isinstance(addon_cfg, AddonConfig)

    justfile_path = project_dir / "justfile"
    if not justfile_path.exists() or not addon_cfg.just_recipes:
        return []

    string_env = make_env()
    rendered_recipes = [
        string_env.from_string(r).render(**render_vars) for r in addon_cfg.just_recipes
    ]

    recipe_names_to_remove = {
        _recipe_name(r) for r in rendered_recipes if _recipe_name(r)
    }

    text = justfile_path.read_text(encoding="utf-8")
    new_text = _strip_recipes(text, recipe_names_to_remove)
    justfile_path.write_text(new_text, encoding="utf-8")

    return sorted(recipe_names_to_remove)


def _recipe_name(recipe: str) -> str:
    """Return the bare recipe name (first non-comment word before the colon)."""
    for line in recipe.strip().splitlines():
        if not line.startswith("#"):
            return line.split(":")[0].strip().split()[0]
    return ""


def _strip_recipes(text: str, names: set[str]) -> str:
    """Remove named recipe blocks from a justfile string.

    A recipe block consists of:
    - Optional leading comment lines (``# ...``)
    - The recipe header line (``name:``)
    - All indented body lines that follow

    The function removes the entire block (comments + header + body) for
    each recipe name in *names*, then collapses any resulting triple-blank
    lines down to a single blank line.
    """
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Detect whether this line starts a recipe block we want to remove.
        # A recipe header is a non-indented, non-comment line with a colon.
        if line and not line[0].isspace() and not line.startswith("#") and ":" in line:
            name = line.split(":")[0].strip().split()[0]
            if name in names:
                # Walk back to eat any immediately preceding comment lines
                # that belong to this recipe (no blank lines between them).
                j = len(result) - 1
                while j >= 0 and result[j].startswith("#"):
                    j -= 1
                # j now points to the last non-comment line before the recipe
                del result[j + 1 :]

                # Skip the header line
                i += 1
                # Skip all indented body lines
                while i < len(lines) and lines[i] and lines[i][0].isspace():
                    i += 1
                continue

        result.append(line)
        i += 1

    # Collapse runs of more than one blank line into a single blank line
    collapsed: list[str] = []
    blank_run = 0
    for line in result:
        if line.strip() == "":
            blank_run += 1
            if blank_run <= 1:
                collapsed.append(line)
        else:
            blank_run = 0
            collapsed.append(line)

    return "".join(collapsed)


# ── Dry run ───────────────────────────────────────────────────────────────────


def _dry_remove(
    project_dir: Path,
    addon_id: str,
    addon_cfg: object,
    lockfile: object,
    pkg_name: str,
) -> None:
    """Print what `zenit remove` would do without writing anything."""
    from scaffolder.lockfile import ZenitLockfile
    from scaffolder.render import make_env
    from scaffolder.schema import AddonConfig
    from scaffolder.ui import BOLD, DIM, MAGENTA, RED, RESET, dry_header

    assert isinstance(addon_cfg, AddonConfig)
    assert isinstance(lockfile, ZenitLockfile)

    print(
        f"\n  {BOLD}{MAGENTA}Dry run:{RESET} zenit remove {addon_id}"
        f"  {DIM}(nothing will be written){RESET}\n"
    )

    render_vars: dict[str, object] = {
        "name": project_dir.name,
        "pkg_name": pkg_name,
        "template": lockfile.template,
        "addons": lockfile.addons,
    }

    all_dests = {fc.dest.replace("{{pkg_name}}", pkg_name) for fc in addon_cfg.files}

    dry_header("Files that would be removed")
    for fc in addon_cfg.files:
        dest = fc.dest.replace("{{pkg_name}}", pkg_name)
        full = project_dir / dest
        if dest.endswith("__init__.py") and fc.content == "":
            parent = full.parent
            siblings_on_disk = (
                {
                    p.relative_to(project_dir).as_posix()
                    for p in parent.iterdir()
                    if p.is_file() and p != full
                }
                if parent.exists()
                else set()
            )
            if siblings_on_disk - all_dests:
                continue
        if full.exists():
            print(f"  {RED}-{RESET} {dest}")
        else:
            print(f"  {DIM}  {dest}  (already missing){RESET}")

    if addon_cfg.deps or addon_cfg.dev_deps:
        dry_header("Dependencies that would be removed from pyproject.toml")
        for dep in addon_cfg.deps:
            print(f"  {RED}-{RESET} {dep}")
        for dep in addon_cfg.dev_deps:
            print(f"  {RED}-{RESET} {dep}  {DIM}(dev){RESET}")

    if addon_cfg.just_recipes:
        dry_header("Just recipes that would be removed")
        string_env = make_env()
        for recipe in addon_cfg.just_recipes:
            rendered = string_env.from_string(recipe).render(**render_vars)
            name = _recipe_name(rendered)
            if name:
                print(f"  {RED}-{RESET} {name}")

    if addon_cfg.compose_services:
        dry_header("Compose services that would be removed")
        for svc in addon_cfg.compose_services:
            print(f"  {RED}-{RESET} {svc.name}")

    if addon_cfg.env_vars:
        dry_header("Env vars that would be removed")
        for ev in addon_cfg.env_vars:
            print(f"  {RED}-{RESET} {ev.key}")

    if addon_cfg.injections:
        dry_header("Injected code that would be removed")
        for inj in addon_cfg.injections:
            preview = inj.content.strip().splitlines()[0][:60]
            print(f"  {RED}-{RESET} [{inj.point}] {DIM}{preview}…{RESET}")

    print()
