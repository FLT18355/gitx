"""gh CLI 共用层: 定位 / 登录态 / 调用 / JSON 解析 / 仓库参数.

gitx 不自己实现 GitHub 的写操作与账号管理, 一律交给已安装并登录的 `gh`
(https://cli.github.com): 本工具只拼参数、不接触令牌, 权限由 gh 自己的登录态决定。
发行版 (publish) / 工作流 (actions) / 登录态 (auth) / 我的仓库 (repos) / 创建 PR 都走这一层。
"""

from __future__ import annotations

import json
import shutil
import subprocess

from . import console, gitcmd, github


def find(feature: str) -> str:
    """已安装的 gh 绝对路径; 没装就给中文提示并退出."""
    path = shutil.which("gh")
    if not path:
        console.error(f"{feature}需要已安装的 gh CLI (https://cli.github.com)\n"
                      "提示: 装好 gh 并 gitx auth login 之后重试")
    return path


def logged_in(path: str) -> bool:
    """gh 是否已登录 (`gh auth status` 非 0 即未登录)."""
    return gitcmd.capture([path, "auth", "status"])[0] == 0


def require(feature: str, *, login: bool = True, hint: str = "") -> str:
    """已装 (默认还要求已登录) 的 gh 路径; 不满足就中文提示并退出."""
    path = shutil.which("gh")
    if not path:
        tail = f"; {hint}" if hint else ""
        console.error(f"{feature}需要已安装的 gh CLI (https://cli.github.com)\n"
                      f"提示: 安装并 gh auth login 之后重试{tail}")
    if login and not logged_in(path):
        console.error(f"gh 未登录, 无法{feature}\n"
                      "提示: 先执行 gitx auth login (写操作需要仓库写权限)")
    return path


def run(path: str, args: list[str], action: str) -> None:
    """跑一条 gh 命令并透传它自己的输出; 失败时补一句中文提示."""
    if subprocess.run([path, *args]).returncode != 0:
        console.error(f"{action}失败 (gh 已打印原因)")


def capture(path: str, args: list[str]) -> tuple[int, str, str]:
    """跑 gh 并同时拿到 stdout / stderr (gh 的报错都写在 stderr)."""
    try:
        done = subprocess.run([path, *args], capture_output=True, text=True)
    except FileNotFoundError:
        return 127, "", "未找到 gh"
    return done.returncode, done.stdout or "", (done.stderr or "").strip()


def json_out(path: str, args: list[str], action: str) -> object:
    """跑一条 gh 命令并按 JSON 解析输出."""
    code, out, err = capture(path, args)
    if code != 0:
        console.error(f"{action}失败\n{err}" if err else f"{action}失败")
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        console.error(f"{action}失败: gh 的输出不是有效 JSON")


def repo_args(target: str) -> list[str]:
    """--repo 参数: 接受 owner/repo 或 GitHub 链接; 留空表示当前仓库."""
    if not target:
        return []
    if "://" in target or "github.com" in target:
        parsed = github.owner_repo(target)
        if not parsed:
            console.error(f"无法识别仓库: {target} (形如 owner/repo)")
    else:
        try:
            parsed = github.parse_repo(target)
        except ValueError as exc:
            console.error(f"{exc}\n用法: --repo owner/repo")
    return ["--repo", f"{parsed[0]}/{parsed[1]}"]
