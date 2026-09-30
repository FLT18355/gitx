"""push / pull / sync 流程."""

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


def push(argv: list[str]) -> None:
    message = ""
    force = False
    to_url = ""
    branch = ""
    path = "."
    no_proxy = False
    free: list[str] = []

    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-f", "--force"):
            force = True
        elif a in ("-m", "--message") and i + 1 < len(argv):
            i += 1
            message = argv[i]
        elif a in ("-b", "--branch") and i + 1 < len(argv):
            i += 1
            branch = argv[i]
        elif a in ("-C", "--path") and i + 1 < len(argv):
            i += 1
            path = argv[i]
        elif a == "--no-proxy":
            no_proxy = True
        elif a == "to" and i + 1 < len(argv):
            i += 1
            to_url = argv[i]
        elif a in ("-h", "--help"):
            console.info("用法: gitx push [备注] [to <仓库地址>] [-f] [-m 信息] [-b 分支] [-C 路径] [--no-proxy]")
            return
        elif a.startswith("-"):
            console.error(f"未知参数: {a}")
        else:
            free.append(a)
        i += 1
    if free:
        message = message or " ".join(free)
    do_push(path=path, message=message, force=force, no_proxy=no_proxy, to_url=to_url, branch=branch)


def pull(argv: list[str]) -> None:
    path = "."
    rebase = False
    no_proxy = False
    for i, a in enumerate(argv):
        if a in ("-C", "--path") and i + 1 < len(argv):
            path = argv[i + 1]
        elif a == "--rebase":
            rebase = True
        elif a == "--no-proxy":
            no_proxy = True
        elif a in ("-h", "--help"):
            console.info("用法: gitx pull [路径] [--rebase] [--no-proxy]")
            return
        elif a.startswith("-"):
            console.error(f"未知参数: {a}")
        else:
            path = a
    do_pull(path, rebase, no_proxy)


def sync(argv: list[str]) -> None:
    """先拉取(默认变基)再推送, 一步完成日常同步."""
    message = ""
    force = False
    path = "."
    no_proxy = False
    rebase = True
    free: list[str] = []

    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-f", "--force"):
            force = True
        elif a in ("-m", "--message") and i + 1 < len(argv):
            i += 1
            message = argv[i]
        elif a in ("-C", "--path") and i + 1 < len(argv):
            i += 1
            path = argv[i]
        elif a == "--no-proxy":
            no_proxy = True
        elif a == "--merge":
            rebase = False
        elif a == "--rebase":
            rebase = True
        elif a in ("-h", "--help"):
            console.info("用法: gitx sync [备注] [--merge] [-f] [-C 路径] [--no-proxy]\n"
                         "  默认: pull --rebase 后 push")
            return
        elif a.startswith("-"):
            console.error(f"未知参数: {a}")
        else:
            free.append(a)
        i += 1
    if free:
        message = message or " ".join(free)
    console.step("同步: 先拉取, 再推送")
    do_pull(path, rebase, no_proxy)
    do_push(path=path, message=message, force=force, no_proxy=no_proxy)