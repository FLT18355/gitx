"""gitx —— 给中国人用的 GitHub 加速与同步工具."""

from __future__ import annotations

import sys

__version__ = "1.0.6"  # 与 pyproject.toml 的 version 必须一致 (发版流程第 1 步)


def main(argv: list[str] | None = None) -> None:
    """入口: 先走快速分发 (git 透传 / --version), 需要时才加载 typer 应用.

    快速分发只依赖标准库, 省掉 typer + rich 约 1 秒的导入:
    `gitx status` / `gitx --version` 因此几乎瞬时完成。

    再往后是"召唤守护进程"(配置 daemon = true 才启用, 默认关闭): 后台有守护进程就把
    这条命令交给它 fork 出的预热子进程执行 (省掉重复导入); 没有就先召唤一个, 本次照常
    本地执行 —— 任何环节出问题都静默回退, 最坏只是没变快, 功能不受影响。
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    from .dispatch import handle

    code, argv = handle(argv)
    if code is None:
        from . import daemon

        if daemon.enabled() and not daemon.in_daemon():
            if daemon.running():
                served = daemon.run(argv)
                if served is not None:
                    if served:
                        raise SystemExit(served)
                    return
            else:
                daemon.spawn()  # 顺手召唤: 这条命令之后, 后续命令就有预热进程可用
        from .cli import main as run_cli

        run_cli(argv)
    elif code:
        raise SystemExit(code)


__all__ = ["__version__", "main"]
