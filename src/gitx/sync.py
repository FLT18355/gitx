"""push / pull / sync 流程 (命令行解析交给 cli.py 的 typer 层)."""

from __future__ import annotations

from . import accel, config, console, gitcmd, github


def do_pull(path: str = ".", rebase: bool = False, no_proxy: bool = False) -> None:
    if not gitcmd.is_repo(path):
        console.error(f"{path} 不是 git 仓库")
    if not gitcmd.remote_url("origin", path):
        console.error("没有远程仓库, 用: gitx push to <仓库地址> 先关联")
    prefix = config.active_proxy(no_proxy=no_proxy)
    branch = gitcmd.current_branch(path)
    if branch and not gitcmd.has_upstream(path):
        if gitcmd.remote_branch_exists("origin", branch, path):
            gitcmd.set_upstream("origin", branch, path)
            console.info(f"已关联上游: origin/{branch}")
        else:
            console.info(f"远端还没有分支 {branch}, 无需拉取 (直接 gitx push 即可)")
            return
    console.step("正在拉取..." + (" [加速]" if prefix else ""))
    if not gitcmd.pull(path, rebase, prefix):
        console.error("拉取失败 (可尝试 --no-proxy 直连)")
    console.done("拉取完成!")


def do_push(path: str = ".", message: str = "", force: bool = False,
            no_proxy: bool = False, to_url: str = "", branch: str = "") -> None:
    if not gitcmd.is_repo(path):
        console.error(f"{path} 不是 git 仓库 (先 gitx <github-url> 下载, 或 gitx init)")
    branch = branch or gitcmd.current_branch(path)
    if not branch:
        console.error('无法确定当前分支 (仓库还没有提交, 请先: gitx push -m "初始提交")')

    prefix = config.active_proxy(no_proxy=no_proxy)

    if to_url:
        try:
            info = github.parse_url(to_url)
        except ValueError as exc:
            console.error(str(exc))
        direct = github.repo_clone_url(info["owner"], info["repo"])
        fetch = accel.wrap(direct, prefix)
        changed = gitcmd.ensure_remote("origin", fetch, push_url=gitcmd.github_push_url(direct), path=path)
        console.info(f"远程: {info['owner']}/{info['repo']}"
                     + (" [拉取加速]" if prefix else "")
                     + (" (已更新)" if changed else ""))
    elif not gitcmd.remote_url("origin", path):
        console.error("没有远程仓库, 用: gitx push to <仓库地址> 先关联")

    gitcmd.ensure_identity(path)
    if not message:
        message = str(config.load().get("message", "日常同步更新"))
    if not gitcmd.commit_all(message, path):
        console.info("没有需要提交的变更")
    else:
        console.done(f"已提交: {message}")

    console.step("正在推送 (推送走直连, 不走加速)...")
    if not gitcmd.push(path, "origin", branch, force=force):
        # 推送失败时先同步远端跟踪引用, 才能准确判断是"远端领先"还是网络问题
        gitcmd.fetch(path)
        behind, _ahead = gitcmd.behind_ahead(path)
        if behind > 0:
            console.error(f"推送失败: 远端有 {behind} 个新提交\n"
                          "提示: 先 gitx pull --rebase (或 gitx sync) 再推送")
        console.error("推送失败\n提示: 加速镜像不支持推送, 推送为直连; 检查网络或运行 gitx doctor")
    console.done("推送成功!")


def do_sync(path: str = ".", message: str = "", force: bool = False,
            no_proxy: bool = False, rebase: bool = True) -> None:
    """先拉取(默认变基)再推送, 一步完成日常同步."""
    console.step("同步: 先拉取, 再推送")
    do_pull(path, rebase, no_proxy)
    do_push(path=path, message=message, force=force, no_proxy=no_proxy)