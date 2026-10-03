"""快速分发: 在导入 typer / rich 之前处理 git 透传与 --version.

`import typer` 就要约 0.7 秒, 而 `gitx status` / `gitx --version` 不该付这份开销。
本模块只依赖标准库, 由 `gitx.main` 先调用:

    gitx status / gitx log --oneline / gitx git <任意 git 命令>   -> 直接 exec git
    gitx -V / --version                                        -> 直接打印版本
    gitx 自己的子命令 (含 branch / switch / stash / tag 等)       -> 交给 cli.py
    其余 (typer 子命令 / GitHub 链接)                            -> 交给 cli.py

判定"这是不是 git 命令"不再需要 `git help -a` (一次子进程 ~0.2 秒, 且输出随语言
变化): 不是 gitx 自己的子命令、也不像链接的词, 直接原样交给 git, 由 git 自己报错。
笔误提示只在 git 自己判定"不是 git 命令" (退出码 1) 时补一句, 因此 `gitx log` /
`gitx status` 这类真实 git 命令不会被提示抢走, 也不会多花一次探测的子进程。
"""

from __future__ import annotations

import subprocess
import sys

from . import __version__

# gitx 自身的子命令; 其余词一律视为 git 透传 (含用户的 git alias)
SUBCOMMANDS = frozenset({
    "download", "clone", "release",
    "push", "pull", "sync", "fetch",
    "init", "info", "undo", "graph", "lg", "branches", "tidy", "url",
    "branch", "switch", "merge", "rebase",
    "stash", "tag", "commit", "diff", "discard", "clean",
    "search", "stat", "web", "ignore",
    "proxy", "config", "doctor", "git",
})

_DOWNLOAD_PREFIXES = ("http://", "https://", "git@", "git://", "ssh://", "www.")


def is_download(token: str) -> bool:
    """看形状判断是否像可直接下载的链接 (不导入 github 模块)."""
    return token.startswith(_DOWNLOAD_PREFIXES)


def _close_subcommand(name: str) -> str:
    """形近的 gitx 子命令 (用于 `gitx dowload` 这类笔误); 没有则返回空串."""
    import difflib

    hit = difflib.get_close_matches(name, SUBCOMMANDS, n=1, cutoff=0.72)
    return hit[0] if hit else ""


def _run_git(argv: list[str]) -> int:
    try:
        return subprocess.run(["git", *argv]).returncode
    except FileNotFoundError:
        print("gitx: 未找到 git, 请先安装 git 并确保在 PATH 中", file=sys.stderr)
        return 127


def handle(argv: list[str]) -> tuple[int | None, list[str]]:
    """已由快速通道处理 -> (退出码, argv); 需要 typer -> (None, 交给 typer 的 argv)."""
    if not argv:
        return None, argv
    first = argv[0]
    if first in ("-V", "--version"):
        print(f"gitx {__version__}")
        return 0, argv
    if first == "git":  # 显式透传: gitx git init --bare
        return _run_git(argv[1:]), argv
    if first in ("-h", "--help", "help") or first in SUBCOMMANDS:
        return None, argv
    if is_download(first):
        # GitHub 链接直接下载: 交给 typer 的 download 命令 (选项原样保留)
        return None, ["download", *argv]
    # 不是 gitx 子命令 -> 原样交给 git, 由 git 自己解析 (log / status / alias / 报错)
    code = _run_git(argv)
    if code == 1:
        # git 判定"不是 git 命令"时退出码是 1 (仓库/参数错误是 128/129), 这时才补一句笔误提示
        close = _close_subcommand(first)
        if close:
            print(f"gitx: 若想用 gitx 的自有命令, 是想用 {close} 吗? (全部命令见 gitx -h)",
                  file=sys.stderr)
    return code, argv