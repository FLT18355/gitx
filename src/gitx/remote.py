"""远程仓库管理: 查看 / 添加 / 删除 / 重命名 / 改地址.

添加或改地址时按 gitx 的策略自动拆分: **拉取指向加速镜像, 推送直连 GitHub**
(镜像对 push 返回 405)。非 GitHub 地址原样使用, 不做改写。
底层的 URL 推导复用 `gitcmd.github_push_url` (存在 insteadOf 规则时推送自动走 SSH)。
"""

from __future__ import annotations

from . import accel, config, console, gitcmd, github


def _split(url: str, push_url: str = "", *, path: str = ".") -> tuple[str, str]:
    """返回 (拉取地址, 推送地址): GitHub 地址走加速 + 直连推送."""
    parsed = github.owner_repo(url)
    if not parsed:
        return url, push_url
    owner, repo = parsed
    direct = github.repo_clone_url(owner, repo)
    prefix = config.active_proxy()
    fetch = accel.wrap(direct, prefix) or direct
    push = push_url or gitcmd.github_push_url(direct, path)
    return fetch, push


def list_remotes(path: str = ".") -> None:
    """查看全部远程 (拉取 / 推送地址)."""
    gitcmd.require_repo(path)
    names = gitcmd.remote_names(path)
    if not names:
        console.info("没有配置远程仓库 (添加: gitx remote add origin <仓库地址>)")
        return
    table = console.table("远程", "拉取", "推送", title="远程仓库")
    for name in names:
        fetch = gitcmd.remote_url(name, path)
        push = gitcmd.remote_push_url(name, path) or fetch
        table.add_row(console.txt(name), console.txt(fetch),
                      console.txt(push + ("" if push != fetch else "  (同上)")))
    console.print(table)
    console.info("添加: gitx remote add <名> <地址>   |   改址: gitx remote set-url <名> <地址>")


def add(name: str, url: str, *, push_url: str = "", path: str = ".") -> None:
    """添加远程; GitHub 地址默认拉取走加速、推送直连."""
    gitcmd.require_repo(path)
    if name in gitcmd.remote_names(path):
        console.error(f"远程 {name} 已存在 (改地址用: gitx remote set-url {name} <地址>)")
    fetch, push = _split(url, push_url, path=path)
    gitcmd.ensure_remote(name, fetch, push, path)
    console.done(f"已添加远程 {name}: 拉取 {fetch}" + (f"  推送 {push}" if push != fetch else ""))


def remove(name: str, *, yes: bool = False, path: str = ".") -> None:
    """删除远程."""
    gitcmd.require_repo(path)
    if name not in gitcmd.remote_names(path):
        console.error(f"没有名为 {name} 的远程")
    if not yes and not console.ask(f"删除远程 {name}?", default=False):
        console.error("已取消")
    if gitcmd.run_capture(["git", "-C", path, "remote", "remove", name])[0] != 0:
        console.error(f"删除远程 {name} 失败")
    console.done(f"已删除远程 {name}")


def rename(old: str, new: str, *, path: str = ".") -> None:
    """重命名远程."""
    gitcmd.require_repo(path)
    if old not in gitcmd.remote_names(path):
        console.error(f"没有名为 {old} 的远程")
    if new in gitcmd.remote_names(path):
        console.error(f"远程 {new} 已存在")
    rc, out = gitcmd.run_capture(["git", "-C", path, "remote", "rename", old, new])
    if rc != 0:
        console.error(f"重命名失败: {out or old}")
    console.done(f"远程 {old} 已重命名为 {new}")


def set_url(name: str, url: str, *, push_only: bool = False, path: str = ".") -> None:
    """修改远程地址; GitHub 地址默认同步改好推送地址."""
    gitcmd.require_repo(path)
    if name not in gitcmd.remote_names(path):
        console.error(f"没有名为 {name} 的远程 (现有: {', '.join(gitcmd.remote_names(path))})")
    fetch, push = _split(url, path=path)
    if push_only:
        fetch = gitcmd.remote_url(name, path)
    if not gitcmd.set_remote_urls(name, fetch, push, path):
        console.error(f"修改远程 {name} 地址失败")
    console.done(f"远程 {name}: 拉取 {fetch}" + (f"  推送 {push}" if push != fetch else ""))


def show(name: str, path: str = ".") -> None:
    """查看单个远程的详细地址与形态."""
    gitcmd.require_repo(path)
    if name not in gitcmd.remote_names(path):
        console.error(f"没有名为 {name} 的远程")
    fetch = gitcmd.remote_url(name, path)
    push = gitcmd.remote_push_url(name, path) or fetch
    table = console.table("项目", "值", title=f"远程 {name}")
    table.add_row("拉取", console.txt(fetch))
    table.add_row("推送", console.txt(push))
    table.add_row("形态", console.styled(_label(fetch, push)))
    console.print(table)


def _label(fetch: str, push: str) -> str:
    if fetch.startswith("git@"):
        return "[tag]ssh[/tag]"
    if "github.com" not in fetch:
        return "[dim]非 GitHub 远端[/dim]"
    if fetch.startswith("https://github.com/"):
        return "[ok]https 直连[/ok]"
    return f"[num]加速[/num]{' (推送走 ssh)' if push.startswith('git@') else ''}"
