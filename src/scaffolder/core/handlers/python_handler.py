from __future__ import annotations

import hashlib
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING

import libcst as cst

from scaffolder.core.handlers import FileHandler
from scaffolder.core.handlers.locators import LocatorError, locate
from scaffolder.schema.exceptions import ScaffoldError

if TYPE_CHECKING:
    from scaffolder.schema.models import ManifestBlock

# ── Constants (define once) ──────────────────────────────────────────────────

FUZZY_REMOVAL_THRESHOLD: float = 0.85
FUZZY_WINDOW_LINES: int = 20
MANIFEST_SCHEMA_VERSION: int = 2


# ── Exceptions ───────────────────────────────────────────────────────────────


class InjectionError(ScaffoldError):
    """Raised when a structural injection cannot be completed."""


class RemovalError(ScaffoldError):
    """Raised when an injected block cannot be located for removal."""


# ── Fingerprinting ────────────────────────────────────────────────────────────


def _canonical(source: str) -> str:
    """Return the source with consistent trailing newline, no CR."""
    return source.replace("\r\n", "\n").replace("\r", "\n")


def _normalise(source: str) -> str:
    """Strip leading/trailing blank lines and normalise internal whitespace runs."""
    lines = _canonical(source).splitlines()
    stripped = [ln.rstrip() for ln in lines]
    # drop leading / trailing blank lines
    while stripped and not stripped[0]:
        stripped.pop(0)
    while stripped and not stripped[-1]:
        stripped.pop()
    return "\n".join(stripped)


def fingerprint(source: str) -> str:
    return "sha256:" + hashlib.sha256(_canonical(source).encode()).hexdigest()


def fingerprint_normalised(source: str) -> str:
    return "sha256:" + hashlib.sha256(_normalise(source).encode()).hexdigest()


# ── Core apply / remove ───────────────────────────────────────────────────────


def apply(
    file: Path,
    content: str,
    locator_name: str,
    locator_args: dict[str, object],
) -> tuple[str, int, int]:
    """Inject *content* into *file* at the position given by the locator.

    Returns ``(new_source, start_line, end_line)`` — 1-based, inclusive.

    Raises ``InjectionError`` if the locator cannot find an insertion point.
    """
    source = file.read_text(encoding="utf-8")
    module = cst.parse_module(source)
    try:
        insert_index = locate(module, locator_name, locator_args)
    except LocatorError as exc:
        raise InjectionError(
            f"Cannot inject at '{locator_name}' in {file}.\n  Reason: {exc}"
        ) from exc

    lines = source.splitlines(keepends=True)

    content_lines = content.splitlines(keepends=True)
    if content_lines and not content_lines[-1].endswith("\n"):
        content_lines[-1] += "\n"

    new_lines = lines[:insert_index] + content_lines + lines[insert_index:]
    new_source = "".join(new_lines)

    start_line = insert_index + 1
    end_line = insert_index + len(content_lines)

    file.write_text(new_source, encoding="utf-8")
    return new_source, start_line, end_line


def remove(
    file: Path,
    block: ManifestBlock,
) -> None:
    """Remove a previously injected block from *file*.

    Stages:
        A — exact fingerprint match on recorded lines.
        B — normalised fingerprint match (formatter-resilient).
        C — fuzzy match within FUZZY_WINDOW_LINES of recorded position.
        D — raise RemovalError with actionable instructions.
    """
    import sys

    source = file.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)

    start_str, end_str = block.lines.split("-")
    rec_start = int(start_str) - 1  # 0-based inclusive
    rec_end = int(end_str) - 1  # 0-based inclusive

    def _extract(s: int, e: int) -> str:
        return "".join(lines[s : e + 1])

    # ── Stage A: exact fingerprint ───────────────────────────────────────────
    if 0 <= rec_start < len(lines) and rec_end < len(lines):
        candidate = _extract(rec_start, rec_end)
        if fingerprint(candidate) == block.fingerprint:
            _remove_lines(file, lines, rec_start, rec_end)
            return

    # ── Stage B: normalised fingerprint ─────────────────────────────────────
    if 0 <= rec_start < len(lines) and rec_end < len(lines):
        candidate = _extract(rec_start, rec_end)
        if fingerprint_normalised(candidate) == block.fingerprint_normalised:
            _remove_lines(file, lines, rec_start, rec_end)
            return

    # ── Stage C: fuzzy match in window ──────────────────────────────────────
    block_len = rec_end - rec_start + 1
    window_start = max(0, rec_start - FUZZY_WINDOW_LINES)
    window_end = min(len(lines) - 1, rec_end + FUZZY_WINDOW_LINES)

    best_ratio = 0.0
    best_start = -1
    norm_ref = _normalise("".join(lines[rec_start : rec_end + 1]))

    for s in range(window_start, window_end - block_len + 2):
        e = s + block_len - 1
        if e > len(lines) - 1:
            break
        candidate = _normalise(_extract(s, e))
        ratio = SequenceMatcher(None, norm_ref, candidate).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_start = s

    if best_ratio >= FUZZY_REMOVAL_THRESHOLD and best_start >= 0:
        best_end = best_start + block_len - 1
        print(
            f"Warning: fuzzy removal matched '{block.point}' in {file} "
            f"at lines {best_start + 1}-{best_end + 1} "
            f"(similarity {best_ratio:.0%}). Block may have been reformatted.",
            file=sys.stderr,
        )
        _remove_lines(file, lines, best_start, best_end)
        return

    # ── Stage D: unrecoverable ───────────────────────────────────────────────
    raise RemovalError(
        f"Could not remove '{block.point}' injection for addon '{block.addon}'.\n"
        f"  File: {file}\n"
        f"  Expected block at lines {block.lines} (fingerprint {block.fingerprint}), "
        f"but the code has changed beyond the fuzzy-match threshold.\n"
        f"  Manual steps:\n"
        f"    - Open {file}\n"
        f"    - Find the code added by the '{block.addon}' addon for point '{block.point}'\n"
        f"    - Remove it, then run: zenit doctor"
    )


def _remove_lines(
    file: Path,
    lines: list[str],
    start: int,
    end: int,
) -> None:
    """Delete lines[start:end+1] from *file*, cleaning up surrounding blank lines."""
    new_lines = lines[:start] + lines[end + 1 :]

    # clean up double blank lines left by removal
    cleaned: list[str] = []
    prev_blank = False
    for ln in new_lines:
        is_blank = ln.strip() == ""
        if is_blank and prev_blank:
            continue
        cleaned.append(ln)
        prev_blank = is_blank

    file.write_text("".join(cleaned), encoding="utf-8")


class PythonHandler(FileHandler):
    def can_handle(self, path: Path) -> bool:
        return path.suffix == ".py"

    def apply(
        self,
        file: Path,
        content: str,
        locator_name: str,
        locator_args: dict[str, object],
    ) -> tuple[str, int, int]:
        return apply(file, content, locator_name, locator_args)

    def remove(self, file: Path, block: ManifestBlock) -> None:
        remove(file, block)
