import sys
import threading
import itertools
import time

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


# ─── Spinner ──────────────────────────────────────────────────────────────────


class _Spinner:
    """Displays an animated spinner on a single line while work runs.

    Usage:
        with spinner("Locking Nix flake inputs"):
            subprocess.run(["nix", "flake", "lock"], check=True)
    """

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
            # Non-interactive: just print the label once and let output flow
            print(f"\n{BOLD}{MAGENTA}▸{RESET} {self._label}…")
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if self._tty:
            self._stop.set()
            self._thread.join()
            # Overwrite spinner line — success() or error() will follow
            sys.stdout.write(f"\r\033[2K")
            sys.stdout.write(_SHOW_CURSOR)
            sys.stdout.flush()
        if exc_type is None:
            success(self._label)


def spinner(label: str) -> _Spinner:
    return _Spinner(label)
