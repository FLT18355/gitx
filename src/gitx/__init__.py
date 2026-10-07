"""gitx —— 给中国人用的 GitHub 加速与同步工具."""

from __future__ import annotations

import sys

__version__ = "1.0.5-pre2"


def main(argv: list[str] | None = None) -> None:
    """入口: 先走快速分发 (git 透传 / --version), 需要时才加载 typer 应用.

    快速分发只依赖标准库, 省掉 typer + rich 约 1 秒的导入:
    `gitx status` / `gitx --version` 因此几乎瞬时完成。
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    from .dispatch import handle

    code, argv = handle(argv)
    if code is None:
        from .cli import main as run_cli

        run_cli(argv)
    elif code:
        raise SystemExit(code)


__all__ = ["main", "__version__"]