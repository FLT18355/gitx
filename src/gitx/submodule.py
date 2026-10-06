"""子模组: 添加 / 更新 / 查看 / 同步 / 删除, 拉取时同样走加速.

关键点: 用 `git -c url.<加速前缀>/.insteadOf=<原地址>` 让 git 在拉取子模组时
把 github.com 的地址重写到镜像 —— 规则只在本次命令内生效, 不落盘、不改远程 URL
(与 download.py 拉子模组用的是同一手法)。
"""

from __future__ import annotations

import os
import shutil
import subprocess

from . import config, console, gitcmd


def _accel() -> tuple[str | None, list[str]]:
    """当前生效的加速前缀与对应的 git -c 参数."""
    prefix = config.active_proxy()
    return prefix, gitcmd.proxy_args(prefix)


def _uses_github(path: str) -> bool:
    """当前仓库的子模组里是否有 GitHub 地址 (决定要不要提示 [加速])."""
    if not os.path.exists(os.path.join(path, ".gitmodules")):
        return False
    try:
        with open(os.path.join(path, ".gitmodules"), encoding="utf-8") as handle:
            return "github.com" in handle.read()
    except OSError:
        return False


def _run(args: list[str], *, path: str = ".") -> int:
    return subprocess.run(["git", "-C", path, *args]).returncode


def add(url: str, sub_path: str = "", *, name: str = "", branch: str = "",
        depth: int = 0, force: bool = False, path: str = ".") -> None:
    """添加子模组 (建议同时给 url 与 路径)."""
    gitcmd.require_repo(path)
    prefix, accel_args = _accel()
    args = [*accel_args, "submodule", "add"]
    if name:
        args += ["--name", name]
    if branch:
        args += ["--branch", branch]
    if depth > 0:
        args += ["--depth", str(depth)]
    if force:
        args.append("--force")
    args.append(url)
    if sub_path:
        args.append(sub_path)
    console.step(f"添加子模组 {url}" + (f" -> {sub_path}" if sub_path else "")
                 + (" [加速]" if prefix and "github.com" in url else ""))
    if _run(args, path=path) != 0:
        console.error("添加子模组失败\n提示: 检查地址是否正确、路径是否已被占用")
    console.done("子模组已添加 (已写入 .gitmodules, 记得随提交一起推送)")


def update(paths: tuple[str, ...] = (), *, init: bool = True, remote: bool = False,
           depth: int = 0, jobs: int = 0, path: str = ".") -> None:
    """拉取子模组内容 (默认 --init --recursive)."""
    gitcmd.require_repo(path)
    prefix, accel_args = _accel()
    args = [*accel_args, "submodule", "update", "--recursive"]
    if init:
        args.append("--init")
    if remote:
        args.append("--remote")
    if depth > 0:
        args += ["--depth", str(depth)]
    if jobs > 0:
        args += ["--jobs", str(jobs)]
    args += list(paths)
    console.step("更新子模组" + (f" ({', '.join(paths)})" if paths else "")
                 + (" [加速]" if prefix and _uses_github(path) else ""))
    if _run(args, path=path) != 0:
        console.error("更新子模组失败\n提示: 用 gitx submodule status 查看状态, 或 --no-proxy 直连重试")
    console.done("子模组已更新")


def list_submodules(path: str = ".") -> None:
    """列出子模组状态 (等价 gitx submodule status)."""
    gitcmd.require_repo(path)
    rc, out = gitcmd.capture(["git", "-C", path, "submodule", "status", "--recursive"])
    if rc != 0 or not out:
        console.info("没有子模组 (添加: gitx submodule add <链接> <路径>)")
        return
    table = console.table("状态", "提交", "子模组", "说明", title="子模组")
    for line in out.splitlines():
        mark, rest = (line[0], line[1:]) if line[:1] in " +-U" else (" ", line)
        parts = rest.strip().split(None, 2)
        sha = parts[0][:8] if parts else ""
        sub = parts[1] if len(parts) > 1 else ""
        note = parts[2].strip("()") if len(parts) > 2 else ""
        table.add_row(console.txt(_mark_label(mark)), console.txt(sha), console.txt(sub), console.txt(note))
    console.print(table)
    console.info("拉取: gitx submodule update   |   同步地址: gitx submodule sync")


def _mark_label(mark: str) -> str:
    return {" ": "已就绪", "+": "提交不一致", "-": "未初始化", "U": "有冲突"}.get(mark, mark)


def sync(path: str = ".") -> None:
    """把子模组的远端地址同步成 .gitmodules 里的配置 (--recursive)."""
    gitcmd.require_repo(path)
    if _run(["submodule", "sync", "--recursive"], path=path) != 0:
        console.error("同步子模组地址失败")
    console.done("子模组地址已同步")


def _module_name(sub_path: str, path: str) -> str:
    """在 .gitmodules 里按路径反查子模组名 (删 .git/modules/<名> 要用)."""
    rc, out = gitcmd.capture(["git", "-C", path, "config", "-f", ".gitmodules",
                              "--get-regexp", r"^submodule\..*\.path$"])
    if rc != 0:
        return ""
    want = sub_path.strip("/")
    for line in out.splitlines():
        key, _, value = line.partition(" ")
        if value.strip().strip("/") == want:
            return key.split(".")[1]
    return ""


def remove(sub_path: str, *, yes: bool = False, path: str = ".") -> None:
    """删除子模组: deinit -> git rm -> 清掉 .git/modules 里的缓存."""
    gitcmd.require_repo(path)
    if not sub_path:
        console.error("请给出子模组路径 (见 gitx submodule status)")
    if not yes and not console.ask(f"删除子模组 {sub_path} (含 .gitmodules 条目与本地缓存)?", default=False):
        console.error("已取消")
    name = _module_name(sub_path, path)
    if _run(["submodule", "deinit", "-f", "--", sub_path], path=path) != 0:
        console.error(f"deinit 失败: {sub_path}")
    if _run(["rm", "-f", "--", sub_path], path=path) != 0:
        console.error(f"git rm 失败: {sub_path}")
    if name:
        shutil.rmtree(os.path.join(path, ".git", "modules", name), ignore_errors=True)
    console.done(f"已删除子模组 {sub_path} (改动已暂存, 记得提交)")
