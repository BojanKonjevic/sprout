"""Apply collected contributions to the project directory."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from scaffolder.render import make_env
from scaffolder.schema import InjectionMode

if TYPE_CHECKING:
    from scaffolder.context import Context
    from scaffolder.schema import (
        ComposeService,
        Contributions,
        EnvVar,
        ExtensionPoint,
        Injection,
    )


def apply_contributions(
    ctx: Context,
    contributions: Contributions,
    extension_points: dict[str, ExtensionPoint],
    render_vars: dict[str, object],
) -> None:
    """Modify the generated project directory in‑place according to *contributions*.

    Assumes common files have already been placed via ``_common/apply.py``.
    Steps (in order):

    1. Create directories.
    2. Write / copy / render individual files.
    3. Apply sentinel‑based injections.
    4. Merge compose services and volumes into ``compose.yml`` (if present).
    5. Append env vars to ``.env`` and ``.env.example`` (if present).
    6. Run each addon's optional ``post_apply`` hook.
    """
    project_dir = ctx.project_dir
    pkg_name = str(render_vars["pkg_name"])

    for d in contributions.dirs:
        ctx.create_dir(d.replace("{{pkg_name}}", pkg_name))

    # Pre‑render {{pkg_name}} placeholders in compose service fields
    for svc in contributions.compose_services:
        if svc.command and "{{pkg_name}}" in svc.command:
            svc.command = svc.command.replace("{{pkg_name}}", pkg_name)
        if svc.environment:
            svc.environment = {
                k: v.replace("{{pkg_name}}", pkg_name) if isinstance(v, str) else v
                for k, v in svc.environment.items()
            }
        if svc.develop_watch:
            for watch in svc.develop_watch:
                if "path" in watch and isinstance(watch["path"], str):
                    watch["path"] = watch["path"].replace("{{pkg_name}}", pkg_name)

    for fc in contributions.files:
        dest = fc.dest.replace("{{pkg_name}}", pkg_name)
        if fc.content is not None:
            if fc.template:
                string_env = make_env()
                rendered = string_env.from_string(fc.content).render(**render_vars)
                ctx.write_file(dest, rendered)
            else:
                ctx.write_file(dest, fc.content)
        elif fc.source is not None:
            src_path = Path(fc.source)
            if not src_path.is_absolute():
                raise ValueError(f"source path for {fc.dest!r} must be absolute")
            if fc.template:
                env = make_env(src_path.parent)
                content = env.get_template(src_path.name).render(**render_vars)
                ctx.write_file(dest, content)
            else:
                ctx.copy_file(src_path, dest)

    _apply_injections(
        project_dir, contributions.injections, extension_points, render_vars
    )

    if contributions.compose_services and (project_dir / "compose.yml").exists():
        _merge_compose_services(project_dir, contributions.compose_services)
        _merge_compose_volumes(project_dir, contributions.compose_volumes)

    for file_name in (".env", ".env.example"):
        env_path = project_dir / file_name
        if env_path.exists() and contributions.env_vars:
            _merge_env_vars(env_path, contributions.env_vars)

    for addon_cfg in contributions._addon_configs:
        module = getattr(addon_cfg, "_module", None)
        if module is not None and hasattr(module, "post_apply"):
            module.post_apply(ctx)


# ── Internal helpers ──────────────────────────────────────────────────────────


def _apply_injections(
    project_dir: Path,
    injections: list[Injection],
    extension_points: dict[str, ExtensionPoint],
    render_vars: dict[str, object],
) -> None:
    """Group injections by extension‑point name, then apply each group."""
    by_point: dict[str, list[str]] = {}
    for inj in injections:
        by_point.setdefault(inj.point, []).append(inj.content)

    for point_name, contents in by_point.items():
        if point_name not in extension_points:
            continue
        ep = extension_points[point_name]
        rel_path = ep.file.replace("{{pkg_name}}", str(render_vars["pkg_name"]))
        _apply_to_file(project_dir / rel_path, ep, contents)


def _apply_to_file(
    file_path: Path,
    ep: ExtensionPoint,
    contents: list[str],
) -> None:
    """Insert *contents* into *file_path* according to *ep*'s mode and sentinel."""
    if not file_path.exists():
        return
    text = file_path.read_text(encoding="utf-8")
    if ep.sentinel not in text:
        return

    joined = "\n".join(contents)

    if ep.mode == InjectionMode.AFTER_SENTINEL:
        text = text.replace(ep.sentinel, ep.sentinel + "\n" + joined, 1)
    elif ep.mode == InjectionMode.APPEND:
        text = text.rstrip("\n") + "\n" + joined + "\n"
    else:
        return

    file_path.write_text(text, encoding="utf-8")


def _merge_compose_services(project_dir: Path, services: list[ComposeService]) -> None:
    """Add *services* to ``compose.yml``, skipping any that already exist."""
    compose_path = project_dir / "compose.yml"
    data: dict[str, object] = (
        yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
    )
    existing: dict[str, object] = data.setdefault("services", {})  # type: ignore[assignment]

    for svc in services:
        if svc.name in existing:
            continue
        block: dict[str, object] = {}
        if svc.image:
            block["image"] = svc.image
        if svc.build:
            block["build"] = svc.build
        if svc.ports:
            block["ports"] = svc.ports
        if svc.volumes:
            block["volumes"] = svc.volumes
        if svc.environment:
            block["environment"] = svc.environment
        if svc.env_file:
            block["env_file"] = svc.env_file
        if svc.command:
            block["command"] = svc.command
        if svc.depends_on:
            block["depends_on"] = svc.depends_on
        if svc.develop_watch:
            block.setdefault("develop", {})["watch"] = svc.develop_watch  # type: ignore[index]
        if svc.healthcheck:
            block["healthcheck"] = svc.healthcheck
        existing[svc.name] = block

    compose_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def _merge_compose_volumes(project_dir: Path, volumes: list[str]) -> None:
    """Add named volumes to ``compose.yml``, skipping duplicates."""
    compose_path = project_dir / "compose.yml"
    data: dict[str, object] = (
        yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
    )
    vols_section: dict[str, None] = data.setdefault("volumes", {})  # type: ignore[assignment]
    for vol_name in volumes:
        if vol_name not in vols_section:
            vols_section[vol_name] = None
    compose_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def _merge_env_vars(env_path: Path, env_vars: list[EnvVar]) -> None:
    """Append missing env vars after the ``# [zenit: env_vars]`` sentinel."""
    sentinel = "# [zenit: env_vars]"
    text = env_path.read_text(encoding="utf-8")
    if sentinel not in text:
        return

    new_lines: list[str] = []
    for v in env_vars:
        if f"{v.key}=" not in text:
            line = f"{v.key}={v.default}"
            if v.comment:
                line += f"  # {v.comment}"
            new_lines.append(line)

    if new_lines:
        joined = "\n".join(new_lines)
        text = text.replace(sentinel, sentinel + "\n" + joined, 1)
        env_path.write_text(text, encoding="utf-8")
