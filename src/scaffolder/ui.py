import sys

BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
CYAN = "\033[0;36m"
MAGENTA = "\033[1;35m"
BLUE = "\033[0;34m"
RESET = "\033[0m"


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


# ---------------------------------------------------------------------------
# Dry-run display helpers
# ---------------------------------------------------------------------------


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
