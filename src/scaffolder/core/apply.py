"""Apply collected contributions to the project directory."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from scaffolder.core.handlers.base import HandlerDispatcher
from scaffolder.core.manifest import (
    add_compose_service,
    add_compose_volume,
    add_dependency,
    add_env_entry,
    add_just_recipe,
    add_python_block,
    fingerprint,
    read_manifest,
    write_manifest,
)
from scaffolder.core.render import make_env
from scaffolder.schema.models import ManifestBlock

if TYPE_CHECKING:
    from scaffolder.core.context import Context
    from scaffolder.schema.models import (
        ComposeService,
        Contributions,
        EnvVar,
        InjectionPoint,
    )

_RECIPE_NAME_RE = re.compile(r"^([a-zA-Z0-9_-]+)\s*:", re.MULTILINE)


def apply_contributions(
    ctx: Context,
    contributions: Contributions,
    injection_points: dict[str, InjectionPoint],
    render_vars: dict[str, object],
) -> None:
    """Modify the generated project directory in-place according to *contributions*.

    Assumes common files have already been placed via ``_common/apply.py``.
    Steps (in order):

    1. Create directories.
    2. Write / copy / render individual files.
    3. Apply structural injections (via HandlerDispatcher) and record in manifest.
    4. Merge compose services and volumes into ``compose.yml`` (if present).
    5. Append env vars to ``.env`` and ``.env.example`` (if present).
    6. Run each addon's optional ``post_apply`` hook.
    7. Write updated manifest to .zenit.toml.
    """
    project_dir = ctx.project_dir
    pkg_name = str(render_vars["pkg_name"])

    for d in contributions.dirs:
        ctx.create_dir(d.replace("{{pkg_name}}", pkg_name))

    # Pre-render {{pkg_name}} placeholders in compose service fields
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

    manifest = read_manifest(project_dir)
    dispatcher = HandlerDispatcher()

    for inj in contributions.injections:
        point = injection_points.get(inj.point)
        if point is None:
            continue

        resolved_file = point.file.replace("{{pkg_name}}", pkg_name)
        file_path = project_dir / resolved_file

        if not file_path.exists():
            continue

        string_env = make_env()
        rendered_content = string_env.from_string(inj.content).render(**render_vars)

        _, start_line, end_line = dispatcher.apply(
            file_path,
            rendered_content,
            point.locator.name,
            dict(point.locator.args),
        )

        # Only Python files get fingerprint-tracked ManifestBlocks.
        if file_path.suffix == ".py":
            # Extract the actual injected lines from the file so libcst has
            # full module context (class body fragments are not valid modules).
            fresh_lines = file_path.read_text(encoding="utf-8").splitlines(
                keepends=True
            )
            block_text = "".join(fresh_lines[start_line - 1 : end_line])
            fp, fp_norm = fingerprint(block_text)
            block = ManifestBlock(
                addon=inj.addon_id,
                point=inj.point,
                file=resolved_file,
                lines=f"{start_line}-{end_line}",
                fingerprint=fp,
                fingerprint_normalised=fp_norm,
                locator={
                    "name": point.locator.name,
                    "args": dict(point.locator.args),
                },
            )
            add_python_block(manifest, block)

    if contributions.compose_services and (project_dir / "compose.yml").exists():
        _merge_compose_services(project_dir, contributions.compose_services)
        _merge_compose_volumes(project_dir, contributions.compose_volumes)

    for file_name in (".env", ".env.example"):
        env_path = project_dir / file_name
        if env_path.exists() and contributions.env_vars:
            _merge_env_vars(env_path, contributions.env_vars)

    # Record non-Python manifest entries.
    source = "addon" if contributions._addon_configs else "template"
    addon_id = (
        contributions._addon_configs[0].id if contributions._addon_configs else ""
    )

    for ev in contributions.env_vars:
        add_env_entry(manifest, ev.key, source, addon_id)

    for svc in contributions.compose_services:
        add_compose_service(manifest, svc.name, source, addon_id)

    for vol in contributions.compose_volumes:
        add_compose_volume(manifest, vol, source, addon_id)

    for dep in contributions.deps:
        pkg = dep.split(">=")[0].split("==")[0].split("[")[0].strip()
        add_dependency(manifest, pkg, dep, source, addon_id, dev=False)

    for dep in contributions.dev_deps:
        pkg = dep.split(">=")[0].split("==")[0].split("[")[0].strip()
        add_dependency(manifest, pkg, dep, source, addon_id, dev=True)

    string_env = make_env()
    recipe_render_vars: dict[str, object] = dict(render_vars)
    for recipe_raw in contributions.just_recipes:
        rendered_recipe = string_env.from_string(recipe_raw).render(
            **recipe_render_vars
        )
        m = _RECIPE_NAME_RE.search(rendered_recipe)
        if m:
            add_just_recipe(manifest, m.group(1), source, addon_id)

    for addon_cfg in contributions._addon_configs:
        hooks = addon_cfg._module
        if hooks is not None and hooks.post_apply is not None:
            hooks.post_apply(ctx)

    write_manifest(project_dir, manifest)


# ── Internal helpers ──────────────────────────────────────────────────────────


def _merge_compose_services(project_dir: Path, services: list[ComposeService]) -> None:
    """Add *services* to ``compose.yml``, skipping any that already exist."""
    compose_path = project_dir / "compose.yml"
    data: dict[str, Any] = (
        yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
    )
    existing: dict[str, Any] = data.setdefault("services", {})

    for svc in services:
        if svc.name in existing:
            continue
        block: dict[str, Any] = {}
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
            develop = block.setdefault("develop", {})
            if isinstance(develop, dict):
                develop["watch"] = svc.develop_watch
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
    data: dict[str, Any] = (
        yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
    )
    vols_section: dict[str, Any] = data.setdefault("volumes", {})
    for vol_name in volumes:
        if vol_name not in vols_section:
            vols_section[vol_name] = None
    compose_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def _merge_env_vars(env_path: Path, env_vars: list[EnvVar]) -> None:
    """Append missing env vars to the end of the file."""
    text = env_path.read_text(encoding="utf-8")

    new_lines: list[str] = []
    for v in env_vars:
        if f"{v.key}=" not in text:
            line = f"{v.key}={v.default}"
            if v.comment:
                line += f"  # {v.comment}"
            new_lines.append(line)

    if new_lines:
        text = text.rstrip("\n") + "\n" + "\n".join(new_lines) + "\n"
        env_path.write_text(text, encoding="utf-8")
