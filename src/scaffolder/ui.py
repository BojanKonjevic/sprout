import itertools
import sys
import threading
import time

# ── Windows: enable VT100 / ANSI escape processing ───────────────────────────
# Required on older Windows builds; a no-op on Windows 10 1511+ and all
# Unix systems.  Must run before any ANSI codes are written.

if sys.platform == "win32":
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        # ENABLE_PROCESSED_OUTPUT | ENABLE_WRAP_AT_EOL_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass  # non-fatal; colours just won't render on very old Windows

# ─────────────────────────────────────────────────────────────────────────────

BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
CYAN = "\033[0;36m"
MAGENTA = "\033[1;35m"
BLUE = "\033[0;34m"
RESET = "\033[0m"

_HIDE_CURSOR = "\033[?25l"
_SHOW_CURSOR = "\033[?25h"


def step(msg: str) -> None:
    print(f"\n{BOLD}{MAGENTA}▸{RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {CYAN}ℹ{RESET}  {msg}")


def success(msg: str) -> None:
    print(f"  {GREEN}✓{RESET}  {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET}  {msg}", file=sys.stderr)


def error(msg: str) -> None:
    print(f"\n  {RED}✗  {msg}{RESET}", file=sys.stderr)


# ─── Dry-run display helpers ──────────────────────────────────────────────────


def dry_header(msg: str) -> None:
    print(f"\n{BOLD}{BLUE}❯ {msg}{RESET}")


def dry_file(path: str, note: str = "") -> None:
    suffix = f"  {DIM}{note}{RESET}" if note else ""
    print(f"  {GREEN}+{RESET} {path}{suffix}")


def dry_cmd(cmd: str) -> None:
    print(f"  {CYAN}${RESET} {DIM}{cmd}{RESET}")


def dry_dep(dep: str, group: str = "") -> None:
    suffix = f"  {DIM}[{group}]{RESET}" if group else ""
    print(f"  {YELLOW}·{RESET} {dep}{suffix}")


def dry_section(title: str) -> None:
    print(f"\n  {BOLD}{DIM}{title}{RESET}")


# ─── Confirm prompt ───────────────────────────────────────────────────────────


def confirm(ctx: object) -> bool:
    from scaffolder.context import Context

    assert isinstance(ctx, Context)

    template_line = f"{CYAN}{ctx.template}{RESET}"
    addon_line = (
        "  ".join(f"{GREEN}{a}{RESET}" for a in ctx.addons) if ctx.addons else f"{DIM}none{RESET}"
    )

    print(f"\n  {BOLD}Ready to scaffold:{RESET}")
    print(f"\n    {'name':<12}  {BOLD}{ctx.name}{RESET}")
    print(f"    {'directory':<12}  {DIM}{ctx.project_dir}{RESET}")
    print(f"    {'template':<12}  {template_line}")
    print(f"    {'addons':<12}  {addon_line}")
    print()

    steps = ["copy common files + template"]
    for a in ctx.addons:
        steps.append(f"apply addon: {a}")
    steps += [
        "generate pyproject.toml, justfile",
        "git init + initial commit",
    ]
    for s in steps:
        print(f"    {CYAN}·{RESET}  {DIM}{s}{RESET}")

    print()

    if not sys.stdin.isatty():
        return True

    try:
        raw = input(f"  Proceed? {DIM}[Y/n]{RESET}  ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False

    return raw in ("", "y", "yes")


# ─── Spinner ──────────────────────────────────────────────────────────────────


class _Spinner:
    _FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
    _INTERVAL = 0.08

    def __init__(self, label: str) -> None:
        self._label = label
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._tty = sys.stdout.isatty()

    def _spin(self) -> None:
        frames = itertools.cycle(self._FRAMES)
        sys.stdout.write(_HIDE_CURSOR)
        while not self._stop.is_set():
            frame = next(frames)
            sys.stdout.write(f"\r  {MAGENTA}{frame}{RESET}  {self._label}…")
            sys.stdout.flush()
            time.sleep(self._INTERVAL)

    def __enter__(self) -> "_Spinner":
        if self._tty:
            self._thread.start()
        else:
            print(f"\n{BOLD}{MAGENTA}▸{RESET} {self._label}…")
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if self._tty:
            self._stop.set()
            self._thread.join()
            sys.stdout.write("\r\033[2K")
            sys.stdout.write(_SHOW_CURSOR)
            sys.stdout.flush()
        if exc_type is None:
            success(self._label)


def spinner(label: str) -> _Spinner:
    return _Spinner(label)
