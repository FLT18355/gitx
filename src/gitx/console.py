"""终端输出: 颜色、符号与交互提示."""

from __future__ import annotations

import sys
from typing import NoReturn

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
DIM = "\033[2m"
NC = "\033[0m"


def info(msg: str) -> None:
    print(f"{GREEN}[+]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[!]{NC} {msg}", file=sys.stderr)


def error(msg: str, code: int = 1) -> NoReturn:
    print(f"{RED}[-]{NC} {msg}", file=sys.stderr)
    sys.exit(code)


def step(msg: str) -> None:
    print(f"{CYAN}[*]{NC} {msg}")


def done(msg: str) -> None:
    print(f"{GREEN}[ok]{NC} {msg}")


def human_size(n: float) -> str:
    """字节数 -> 人类可读大小."""
    units = ("B", "KB", "MB", "GB", "TB")
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.0f} {units[i]}" if i == 0 else f"{n:.1f} {units[i]}"


def ask(question: str, default: bool | None = None) -> bool:
    """询问 y/n; 非交互环境使用 default(没有 default 视为 False)."""
    if default is True:
        suffix = " [Y/n] "
    elif default is False:
        suffix = " [y/N] "
    else:
        suffix = " [y/n] "
    try:
        answer = input(f"{CYAN}[?]{NC} {question}{suffix}").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return bool(default)
    if not answer and default is not None:
        return default
    return answer in ("y", "yes", "是", "对", "1")
