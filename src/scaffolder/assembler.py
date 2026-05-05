"""Assembles contributions from addons and applies them to the generated project."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from scaffolder.render import make_env
from scaffolder.schema import (
    Contributions,
    ExtensionPoint,
    InjectionMode,
)

if TYPE_CHECKING:
    from scaffolder.context import Context
    from scaffolder.schema import AddonConfig, ComposeService, EnvVar, Injection


def collect_contributions(addon_configs: list[AddonConfig]) -> Contributions:
    """Merge contributions from all selected addons into a single bag."""
    c = Contributions()
    for addon in addon_configs:
        c.files.extend(addon.files)
        c.compose_services.extend(addon.compose_services)
        c.compose_volumes.extend(addon.compose_volumes)
        c.env_vars.extend(addon.env_vars)
        c.deps.extend(addon.deps)
        c.dev_deps.extend(addon.dev_deps)
        c.just_recipes.extend(addon.just_recipes)
        for inj in addon.injections:
            inj.addon_id = addon.id
            c.injections.append(inj)
    # Store the actual addon configs for post_apply hooks
    c._addon_configs = addon_configs
    return c


def apply_contributions(
    ctx: Context,
    contributions: Contributions,
    extension_points: dict[str, ExtensionPoint],
    render_vars: dict[str, str],
) -> None:
    """
    Modify the generated project directory in-place according to the contributions.
    Assumes the template apply functions have already placed all base files.
    """
    project_dir = ctx.project_dir

    # --- Pre‑render dynamic fields in compose services ---
    for svc in contributions.compose_services:
        if svc.command and "{{pkg_name}}" in svc.command:
            svc.command = svc.command.replace("{{pkg_name}}", render_vars["pkg_name"])
        if svc.environment:
            svc.environment = {
                k: v.replace("{{pkg_name}}", render_vars["pkg_name"]) if isinstance(v, str) else v
                for k, v in svc.environment.items()
            }
        if svc.develop_watch:
            for watch in svc.develop_watch:
                if "path" in watch and isinstance(watch["path"], str):
                    watch["path"] = watch["path"].replace("{{pkg_name}}", render_vars["pkg_name"])

    for fc in contributions.files:
        dest = fc.dest.replace("{{pkg_name}}", render_vars["pkg_name"])
        if fc.content is not None:
            ctx.write_file(dest, fc.content)
        elif fc.source is not None:
            src_path = Path(fc.source)
            if not src_path.is_absolute():
                raise ValueError(f"source path for {fc.dest} is not absolute")
            if fc.template:
                env = make_env(src_path.parent)
                content = env.get_template(src_path.name).render(
                    name=ctx.name,
                    pkg_name=ctx.pkg_name,
                    template=ctx.template,
                )
                ctx.write_file(dest, content)
            else:
                ctx.copy_file(src_path, dest)

    _apply_injections_rendered(
        project_dir,
        contributions.injections,
        extension_points,
        render_vars,
    )

    if contributions.compose_services and (project_dir / "compose.yml").exists():
        _merge_compose_services(project_dir, contributions.compose_services)
        _merge_compose_volumes(project_dir, contributions.compose_volumes)

    for file_name in (".env", ".env.example"):
        env_path = project_dir / file_name
        if env_path.exists() and contributions.env_vars:
            _merge_env_vars(env_path, contributions.env_vars)

    for addon_cfg in contributions._addon_configs:
        if hasattr(addon_cfg, "_module") and hasattr(addon_cfg._module, "post_apply"):
            addon_cfg._module.post_apply(ctx)


def _apply_injections_rendered(
    project_dir: Path,
    injections: list[Injection],
    extension_points: dict[str, ExtensionPoint],
    render_vars: dict[str, str],
) -> None:
    """Group and apply injections, rendering file paths with pkg_name."""
    by_point: dict[str, list[str]] = {}
    for inj in injections:
        by_point.setdefault(inj.point, []).append(inj.content)

    for point_name, contents in by_point.items():
        if point_name not in extension_points:
            continue
        ep = extension_points[point_name]
        rel_path = ep.file.replace("{{pkg_name}}", render_vars["pkg_name"])
        file_path = project_dir / rel_path
        _apply_to_file(file_path, ep, contents)


def _apply_to_file(
    file_path: Path,
    ep: ExtensionPoint,
    contents: list[str],
) -> None:
    """Perform the actual text injection for one extension point."""
    if not file_path.exists():
        return
    text = file_path.read_text(encoding="utf-8")
    sentinel = ep.sentinel
    if sentinel not in text:
        return

    joined = "\n".join(contents)

    if ep.mode == InjectionMode.AFTER_SENTINEL:
        text = text.replace(sentinel, sentinel + "\n" + joined, 1)
    elif ep.mode == InjectionMode.APPEND:
        text = text.rstrip("\n") + "\n" + joined + "\n"
    else:
        return

    file_path.write_text(text, encoding="utf-8")


def _merge_compose_services(project_dir: Path, services: list[ComposeService]) -> None:
    compose_path = project_dir / "compose.yml"
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
    existing = data.setdefault("services", {})

    for svc in services:
        if svc.name in existing:
            continue
        block: dict = {}
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
            block.setdefault("develop", {})["watch"] = svc.develop_watch
        existing[svc.name] = block

    compose_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def _merge_compose_volumes(project_dir: Path, volumes: list[str]) -> None:
    compose_path = project_dir / "compose.yml"
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
    vols_section = data.setdefault("volumes", {})
    for vol_name in volumes:
        if vol_name not in vols_section:
            vols_section[vol_name] = None
    compose_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def _merge_env_vars(env_path: Path, env_vars: list[EnvVar]) -> None:
    text = env_path.read_text(encoding="utf-8")
    sentinel = "# [jumpstart: env_vars]"
    if sentinel not in text:
        return

    new_lines = []
    for v in env_vars:
        if v.key + "=" not in text:
            line = f"{v.key}={v.default}"
            if v.comment:
                line += f"  # {v.comment}"
            new_lines.append(line)

    if new_lines:
        joined = "\n".join(new_lines)
        text = text.replace(sentinel, sentinel + "\n" + joined, 1)
        env_path.write_text(text, encoding="utf-8")
